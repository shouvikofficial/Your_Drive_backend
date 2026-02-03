import os
import httpx
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")


async def send_to_telegram(file):
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument"

    async with httpx.AsyncClient() as client:
        response = await client.post(
            url,
            data={"chat_id": CHAT_ID},
            files={
                "document": (
                    file.filename,
                    await file.read(),
                )
            },
        )

    data = response.json()

    return data["result"]["document"]["file_id"]
