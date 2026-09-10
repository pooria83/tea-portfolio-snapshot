from unittest.mock import MagicMock, patch

import pytest


@pytest.mark.asyncio
async def test_send_otp_mock_mode():
    from app.services.sms_service import SmsService

    svc = SmsService()
    with patch.object(svc, "_ensure_client", return_value=None):
        result = await svc.send_otp("+966500000000", "123456")
        assert result is True


@pytest.mark.asyncio
async def test_send_otp_success():
    from app.services.sms_service import SmsService

    svc = SmsService()
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(sid="SM123")
    svc._client = mock_client
    svc._initialized = True

    result = await svc.send_otp("+966500000000", "123456")
    assert result is True


@pytest.mark.asyncio
async def test_send_otp_twilio_rest_exception():
    from twilio.base.exceptions import TwilioRestException

    from app.services.sms_service import SmsService

    svc = SmsService()
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = TwilioRestException(
        status=400,
        uri="/Messages.json",
        msg="Bad number",
    )
    svc._client = mock_client
    svc._initialized = True

    result = await svc.send_otp("+966500000000", "123456")
    assert result is False


@pytest.mark.asyncio
async def test_ensure_client_not_initialized_no_creds():
    with patch("app.services.sms_service.settings.twilio_account_sid", None), patch("app.services.sms_service.settings.twilio_auth_token", None):
        from app.services.sms_service import SmsService

        svc = SmsService()
        client = svc._ensure_client()
        assert client is None
        assert svc._initialized is True


@pytest.mark.asyncio
async def test_ensure_client_already_initialized():
    with patch("app.services.sms_service.settings.twilio_account_sid", "sid"), patch("app.services.sms_service.settings.twilio_auth_token", "token"):
        from app.services.sms_service import SmsService

        svc = SmsService()
        svc._initialized = True
        svc._client = MagicMock()
        client = svc._ensure_client()
        assert client is svc._client
