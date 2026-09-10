from unittest.mock import patch

from app.core.http_client import (
    OPENCODE_OPENAI_USER_AGENT,
    create_http_client,
    create_openai_client,
)


def test_create_openai_client_sets_opencode_user_agent():
    with patch("app.core.http_client.AsyncOpenAI") as mock_cls:
        client = create_openai_client(api_key="sk-test", base_url="https://opencode.ai/zen/v1")

        mock_cls.assert_called_once()
        kwargs = mock_cls.call_args.kwargs
        assert kwargs["api_key"] == "sk-test"
        assert kwargs["base_url"] == "https://opencode.ai/zen/v1"
        assert kwargs["default_headers"] == {"User-Agent": OPENCODE_OPENAI_USER_AGENT}
        assert client == mock_cls.return_value


def test_create_openai_client_user_agent_matches_opencode_cli():
    assert OPENCODE_OPENAI_USER_AGENT == ("opencode/1.18.23 ai-sdk/provider-utils/4.0.23 runtime/bun/1.3.14")


def test_create_http_client_disables_env_proxies():
    with patch("app.core.http_client.httpx.AsyncClient") as mock_cls:
        client = create_http_client()
        mock_cls.assert_called_once()
        assert mock_cls.call_args.kwargs["trust_env"] is False
        assert client == mock_cls.return_value
