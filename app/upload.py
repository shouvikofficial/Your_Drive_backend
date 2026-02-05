from fastapi import APIRouter, UploadFile, File, HTTPException
from dotenv import load_dotenv
from fastapi.responses import JSONResponse

from app.telegram_bot import send_to_telegram

router = APIRouter()
load_dotenv()

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    """
    Uploads file to Telegram and returns:
    {
      file_id,
      thumbnail_id,
      type,
      message_id
    }
    """

    if not file:
        raise HTTPException(status_code=400, detail="No file provided")

    try:
        # 🔥 Upload to Telegram
        result = await send_to_telegram(file)

        if not result or "file_id" not in result or "message_id" not in result:
            raise Exception("Invalid Telegram response")

        return JSONResponse(
            status_code=200,
            content={
                "file_id": str(result["file_id"]),
                "thumbnail_id": (
                    str(result["thumbnail_id"])
                    if result.get("thumbnail_id")
                    else None
                ),
                "type": str(result["type"]),
                "message_id": result["message_id"],  # 🔥 REQUIRED FOR DELETE
            },
        )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Telegram upload failed: {str(e)}"
        )
