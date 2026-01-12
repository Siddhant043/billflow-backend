from fastapi import APIRouter

router = APIRouter()

@router.get("/analytics")
async def get_analytics():
    return {"message": "Get analytics"}
