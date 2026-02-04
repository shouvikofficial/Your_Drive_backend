from fastapi import APIRouter, UploadFile, File, HTTPException
from dotenv import load_dotenv

from .telegram_bot import send_to_telegram  # ✅ FIXED (relative import)

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

        # 🔥 IMPORTANT: return ONLY file_id (Flutter expects plain text)
        return file_id

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Telegram upload failed: {str(e)}"
        )
