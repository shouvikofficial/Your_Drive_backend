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
    returns ONLY the Telegram file_id.

    Supabase handles:
    - Auth
    - User isolation
    - Metadata storage
    """

    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    try:
        # 🔥 Upload to Telegram
        file_id = await send_to_telegram(file)

        if not file_id:
            raise Exception("Empty file_id from Telegram")

        # ✅ CRITICAL FIX:
        # Always return CLEAN plain text (no quotes, no newline)
        return str(file_id).strip().replace('"', '').replace("'", '')

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Telegram upload failed: {str(e)}"
        )
