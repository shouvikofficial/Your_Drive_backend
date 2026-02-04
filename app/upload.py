from fastapi import APIRouter, UploadFile, File, HTTPException
from dotenv import load_dotenv

from app.telegram_bot import send_to_telegram

# --------------------------------------------------
# INIT
# --------------------------------------------------
router = APIRouter()
load_dotenv()

# --------------------------------------------------
# UPLOAD ROUTE (TELEGRAM WORKER ONLY)
# --------------------------------------------------
@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Receives file from Flutter,
    uploads it to Telegram private channel,
    returns file_id + thumbnail_id + type (JSON).

    Supabase handles:
    - Auth
    - User isolation
    - Metadata storage
    """

    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    try:
        # 🔥 Upload to Telegram
        result = await send_to_telegram(file)

        if not result or "file_id" not in result:
            raise Exception("Invalid Telegram response")

        # ✅ RETURN STRUCTURED JSON (REQUIRED FOR VIDEO THUMBNAILS)
        return {
            "file_id": str(result["file_id"]).strip(),
            "thumbnail_id": (
                str(result["thumbnail_id"]).strip()
                if result.get("thumbnail_id")
                else None
            ),
            "type": result["type"],
        }

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Telegram upload failed: {str(e)}"
        )
