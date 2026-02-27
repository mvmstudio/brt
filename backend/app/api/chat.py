from fastapi import APIRouter

router = APIRouter()


@router.post("/chat")
async def chat():
    # Phase 5: RAG AI-assistant
    return {"message": "Chat endpoint — coming in Phase 5"}
