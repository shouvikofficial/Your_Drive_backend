import os
import httpx
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

TELEGRAM_URL = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"


async def send_to_telegram(file):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("BOT_TOKEN or CHAT_ID not set")

    try:
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(
                TELEGRAM_URL,
                data={"chat_id": CHAT_ID},
                files={
                    "document": (
                        file.filename,
                        file.file,  # 🔥 STREAM FILE (NOT read into memory)
                    )
                },
            )

        response.raise_for_status()
        data = response.json()

        if not data.get("ok"):
            raise RuntimeError(f"Telegram error: {data}")

        return data["result"]["document"]["file_id"]

    except Exception as e:
        print("Telegram upload failed:", e)
        raise
