from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from app.services.embedding.models.sentence_transformer import SentenceTransformerModel


def _encode_side_effect(text, **kw):
    if isinstance(text, str):
        return np.array([0.1, 0.2, 0.3])
    return np.array([[0.1, 0.2], [0.3, 0.4]])


@pytest.fixture
def mock_st() -> MagicMock:
    with patch("app.services.embedding.models.sentence_transformer.SentenceTransformer") as m:
        model_instance = MagicMock()
        model_instance.encode.side_effect = _encode_side_effect
        m.return_value = model_instance
        yield m


class TestSentenceTransformerModel:
    def test_init(self, mock_st: MagicMock) -> None:
        model = SentenceTransformerModel(model="Qwen/Qwen3-Embedding-0.6B", dimensions=1024)
        assert model.dimensions == 1024
        assert model.model_name == "Qwen/Qwen3-Embedding-0.6B"
        mock_st.assert_called_once_with("Qwen/Qwen3-Embedding-0.6B", device="cpu")

    async def test_embed_query(self, mock_st: MagicMock) -> None:
        model = SentenceTransformerModel(model="test-model", dimensions=384)
        result = await model.embed_query("red dress")
        assert result == [0.1, 0.2, 0.3]
        call_text = model._model.encode.call_args.args[0]
        assert "Query: red dress" in call_text

    async def test_embed_query_prefix(self, mock_st: MagicMock) -> None:
        model = SentenceTransformerModel(model="test-model", dimensions=384)
        await model.embed_query("blue shirt")
        call_text = model._model.encode.call_args.args[0]
        assert call_text == "Instruct: Given a web search query, retrieve relevant passages\nQuery: blue shirt"

    async def test_embed_passage(self, mock_st: MagicMock) -> None:
        model = SentenceTransformerModel(model="test-model", dimensions=384)
        result = await model.embed_passage("Silk dress")
        assert result == [0.1, 0.2, 0.3]
        call_text = model._model.encode.call_args.args[0]
        assert call_text == "Silk dress"

    async def test_embed_passage_no_prefix(self, mock_st: MagicMock) -> None:
        model = SentenceTransformerModel(model="test-model", dimensions=384)
        await model.embed_passage("Cotton t-shirt")
        call_text = model._model.encode.call_args.args[0]
        assert "Query:" not in call_text
        assert call_text == "Cotton t-shirt"

    async def test_embed_batch(self, mock_st: MagicMock) -> None:
        model = SentenceTransformerModel(model="test-model", dimensions=384)
        results = await model.embed_batch(["a", "b"])
        assert len(results) == 2

    async def test_embed_query_failure(self, mock_st: MagicMock) -> None:
        model = SentenceTransformerModel(model="test-model", dimensions=384)
        model._model.encode.side_effect = Exception("error")
        result = await model.embed_query("test")
        assert result is None

    async def test_embed_passage_failure(self, mock_st: MagicMock) -> None:
        model = SentenceTransformerModel(model="test-model", dimensions=384)
        model._model.encode.side_effect = Exception("error")
        result = await model.embed_passage("test")
        assert result is None

    async def test_embed_batch_failure(self, mock_st: MagicMock) -> None:
        model = SentenceTransformerModel(model="test-model", dimensions=384)
        model._model.encode.side_effect = Exception("error")
        results = await model.embed_batch(["a", "b"])
        assert results == [None, None]

    async def test_health_always_true(self, mock_st: MagicMock) -> None:
        model = SentenceTransformerModel(model="test-model", dimensions=384)
        assert await model.health() is True
