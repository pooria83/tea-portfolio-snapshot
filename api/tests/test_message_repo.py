"""Regression tests for MessageRepo persistence semantics.

Guards the E11000 root cause: assistant messages (no idempotency key) must not
store `idempotencyKey: null`, because the sparse unique index on idempotencyKey
allows only one document with a null value collection-wide — a second assistant
save used to raise DuplicateKeyError and skip the whole persist/compact/title
block.
"""

from mongomock_motor import AsyncMongoMockClient

from app.core.config import settings
from app.repositories.message_repo import MessageRepo

_TEST_DB = settings.mongo_db_name + "_message_repo"


async def test_assistant_create_omits_idempotency_key(mongo_client: AsyncMongoMockClient) -> None:
    repo = MessageRepo(mongo_client[_TEST_DB])
    await repo.collection.create_index([("idempotencyKey", 1)], unique=True, sparse=True)

    first = await repo.create("conv-1", "assistant", "answer one")
    second = await repo.create("conv-1", "assistant", "answer two")

    assert "idempotencyKey" not in first
    assert "idempotencyKey" not in second
    assert first["_id"] != second["_id"]


async def test_user_create_stores_idempotency_key(mongo_client: AsyncMongoMockClient) -> None:
    repo = MessageRepo(mongo_client[_TEST_DB])
    await repo.collection.create_index([("idempotencyKey", 1)], unique=True, sparse=True)

    doc = await repo.create("conv-1", "user", "hello", idempotency_key="key-1")

    assert doc["idempotencyKey"] == "key-1"


async def test_duplicate_idempotency_key_returns_existing(mongo_client: AsyncMongoMockClient) -> None:
    repo = MessageRepo(mongo_client[_TEST_DB])
    await repo.collection.create_index([("idempotencyKey", 1)], unique=True, sparse=True)

    first = await repo.create("conv-1", "user", "hello", idempotency_key="key-1")
    duplicate = await repo.create("conv-1", "user", "hello again", idempotency_key="key-1")

    assert duplicate["_id"] == first["_id"]


async def test_assistant_create_stores_debug(mongo_client: AsyncMongoMockClient) -> None:
    repo = MessageRepo(mongo_client[_TEST_DB])

    debug = {
        "prompt": {"model": "test-model", "messages": [{"role": "user", "content": "red dress"}]},
        "response": {"choices": [{"message": {"content": "{}"}}]},
    }
    doc = await repo.create("conv-1", "assistant", "answer", debug=debug)

    assert doc["debug"] == debug


async def test_assistant_create_debug_null_when_absent(mongo_client: AsyncMongoMockClient) -> None:
    repo = MessageRepo(mongo_client[_TEST_DB])

    doc = await repo.create("conv-1", "assistant", "answer")

    assert doc["debug"] is None
