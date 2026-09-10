import asyncio
from concurrent.futures import ThreadPoolExecutor

from loguru import logger
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client as TwilioClient

from app.core.config import settings


class SmsService:
    def __init__(self) -> None:
        self._client: TwilioClient | None = None
        self._initialized = False
        self._executor = ThreadPoolExecutor(max_workers=1)

    def _ensure_client(self) -> TwilioClient | None:
        if self._initialized:
            return self._client
        self._initialized = True
        if settings.twilio_account_sid and settings.twilio_auth_token:
            self._client = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)
        return self._client

    async def send_otp(self, phone: str, code: str) -> bool:
        client = self._ensure_client()
        if client is None:
            logger.info("Twilio not configured — dev mock mode. OTP {} sent to {}", code, phone)
            return True
        try:
            loop = asyncio.get_running_loop()
            message = await loop.run_in_executor(
                self._executor,
                lambda: client.messages.create(
                    body=f"Your TEA verification code is: {code}",
                    from_=settings.twilio_phone_number,
                    to=phone,
                ),
            )
            logger.info("Twilio SMS sent: sid={} to={}", message.sid, phone)
            return True
        except TwilioRestException as exc:
            logger.error("Twilio send failed: {}", exc)
            return False
