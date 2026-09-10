from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.llm import LLMModel


class LLMSetting(Base, TimestampMixin):
    __tablename__ = "llm_settings"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    default_llm_model_id: Mapped[str | None] = mapped_column(ForeignKey("llm_models.id", ondelete="SET NULL"), nullable=True)
    user_comm_model_id: Mapped[str | None] = mapped_column(ForeignKey("llm_models.id", ondelete="SET NULL"), nullable=True)

    default_llm_model: Mapped[LLMModel | None] = relationship("LLMModel", foreign_keys=[default_llm_model_id], lazy="selectin")
    user_comm_model: Mapped[LLMModel | None] = relationship("LLMModel", foreign_keys=[user_comm_model_id], lazy="selectin")
