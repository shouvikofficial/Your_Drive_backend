from fastapi import APIRouter, HTTPException
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

router = APIRouter()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

TELEGRAM_DELETE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/deleteMessage"


@router.delete("/delete/{message_id}")
async def delete_file(message_id: int):
    """
    Deletes a file from:
    1️⃣ Telegram (by message_id)
    2️⃣ Supabase row should be deleted from Flutter side
    """

    if not BOT_TOKEN or not CHAT_ID:
        raise HTTPException(status_code=500, detail="Bot config missing")

    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(
                TELEGRAM_DELETE_URL,
                json={
                    "chat_id": CHAT_ID,
                    "message_id": message_id,
                },
            )

        data = res.json()

        if not data.get("ok"):
            raise Exception(data)

        return {"success": True}

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Telegram delete failed: {str(e)}",
        )
