from typing import cast

from fastapi import APIRouter, Depends, HTTPException, Request

from app.schemas.chat import SummarizeRequest, SummarizeResponse
from app.services.llm_client import LLMClient

router = APIRouter(tags=["summarize"])


async def get_comm_llm(request: Request) -> LLMClient:
    return cast(LLMClient, request.app.state.comm_llm_client)


@router.post("/summarize", response_model=SummarizeResponse)
async def summarize(
    request: SummarizeRequest,
    comm_llm: LLMClient = Depends(get_comm_llm),
) -> SummarizeResponse:
    messages = [{"role": m.role, "content": m.content} for m in request.messages if m.content]
    if not messages:
        return SummarizeResponse(summary=request.previous_summary, tokens_used=0)

    summary, tokens_used = await comm_llm.summarize(
        messages,
        previous_summary=request.previous_summary,
        locale=request.locale,
        prompt=request.prompt,
    )
    if summary is None:
        raise HTTPException(status_code=502, detail="Summarization failed")

    return SummarizeResponse(summary=summary, tokens_used=tokens_used)
