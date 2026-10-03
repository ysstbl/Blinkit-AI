from fastapi import APIRouter

from app.models.schemas import AssistantRequest
from app.services.assistant_service import assistant_service

router = APIRouter()


@router.post("/api/blinkit-assistant")
async def blinkit_assistant(request: AssistantRequest):
    return assistant_service.handle(request.prompt)
