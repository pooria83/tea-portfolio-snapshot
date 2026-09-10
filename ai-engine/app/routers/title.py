from typing import cast

from fastapi import APIRouter, Depends, Request

from app.schemas.chat import TitleRequest, TitleResponse
from app.services.llm_client import LLMClient

router = APIRouter(tags=["title"])


def _fallback_title(query: str) -> str:
    words = " ".join(query.split())
    if len(words) <= 50:
        return words
    cut = words[:50].rsplit(" ", 1)[0].rstrip(" ,.;:!?")
    return cut or words[:50]


async def get_comm_llm(request: Request) -> LLMClient:
    return cast(LLMClient, request.app.state.comm_llm_client)


@router.post("/title", response_model=TitleResponse)
async def title(
    request: TitleRequest,
    comm_llm: LLMClient = Depends(get_comm_llm),
) -> TitleResponse:
    if not request.need_title:
        return TitleResponse(title=_fallback_title(request.query))
    result = await comm_llm.generate_title(request.query, locale=request.locale, prompt=request.prompt)
    if result is None:
        return TitleResponse(title=_fallback_title(request.query))
    return TitleResponse(title=result)
