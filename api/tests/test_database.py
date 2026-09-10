from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import Request

from app.core.database import get_db


@pytest.mark.asyncio
async def test_get_db_yields_session():
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    mock_factory = MagicMock()
    mock_factory.return_value = mock_session

    mock_request = MagicMock(spec=Request)
    mock_request.app.state.session_factory = mock_factory

    gen = get_db(mock_request)
    session = await anext(gen)

    assert session is mock_session

    with pytest.raises(StopAsyncIteration):
        await anext(gen)


@pytest.mark.asyncio
async def test_get_db_commits_on_success():
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    mock_factory = MagicMock()
    mock_factory.return_value = mock_session

    mock_request = MagicMock(spec=Request)
    mock_request.app.state.session_factory = mock_factory

    gen = get_db(mock_request)
    await anext(gen)
    mock_session.commit.assert_not_called()

    with pytest.raises(StopAsyncIteration):
        await anext(gen)

    mock_session.commit.assert_awaited_once()
    mock_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_db_rolls_back_on_exception():
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    mock_factory = MagicMock()
    mock_factory.return_value = mock_session

    mock_request = MagicMock(spec=Request)
    mock_request.app.state.session_factory = mock_factory

    gen = get_db(mock_request)
    await anext(gen)

    with pytest.raises(RuntimeError):
        await gen.athrow(RuntimeError("test error"))

    mock_session.rollback.assert_awaited_once()
    mock_session.close.assert_awaited_once()
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_get_db_raises_if_no_factory():
    mock_request = MagicMock(spec=Request)
    mock_request.app.state.session_factory = None

    gen = get_db(mock_request)
    with pytest.raises(RuntimeError, match="Database not initialized"):
        await anext(gen)


@pytest.mark.asyncio
async def test_get_db_rollback_failure_still_closes():
    """rollback() raising must not prevent close()."""
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    mock_session.commit.side_effect = ValueError("commit failed")
    mock_session.rollback.side_effect = RuntimeError("rollback also failed")

    mock_factory = MagicMock()
    mock_factory.return_value = mock_session

    mock_request = MagicMock(spec=Request)
    mock_request.app.state.session_factory = mock_factory

    gen = get_db(mock_request)
    await anext(gen)

    with pytest.raises(ValueError, match="commit failed"):
        await gen.athrow(ValueError("commit failed"))

    mock_session.rollback.assert_awaited_once()
    mock_session.close.assert_awaited_once()
    mock_session.commit.assert_not_called()


@pytest.mark.asyncio
async def test_get_db_close_failure_does_not_leak():
    """close() raising must be suppressed — exception must not escape finally."""
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    mock_session.commit.side_effect = ValueError("commit failed")
    mock_session.close.side_effect = RuntimeError("close failed")

    mock_factory = MagicMock()
    mock_factory.return_value = mock_session

    mock_request = MagicMock(spec=Request)
    mock_request.app.state.session_factory = mock_factory

    gen = get_db(mock_request)
    await anext(gen)

    with pytest.raises(ValueError, match="commit failed"):
        await gen.athrow(ValueError("commit failed"))

    mock_session.rollback.assert_awaited_once()
    mock_session.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_db_any_exception_triggers_rollback():
    """Any exception (ValueError, MissingGreenlet, etc.) must trigger rollback."""
    mock_session = AsyncMock()
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None
    mock_session.commit.side_effect = RuntimeError("any error")

    mock_factory = MagicMock()
    mock_factory.return_value = mock_session

    mock_request = MagicMock(spec=Request)
    mock_request.app.state.session_factory = mock_factory

    gen = get_db(mock_request)
    await anext(gen)

    with pytest.raises(RuntimeError, match="any error"):
        await gen.athrow(RuntimeError("any error"))

    mock_session.rollback.assert_awaited_once()
    mock_session.close.assert_awaited_once()
    mock_session.commit.assert_not_called()
