import os
import httpx
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

BASE_URL = f"https://api.telegram.org/bot{BOT_TOKEN}"


def detect_type(filename: str):
    ext = filename.lower().split(".")[-1]

    if ext in ["jpg", "jpeg", "png", "gif"]:
        return "photo"
    if ext in ["mp4", "mkv", "avi", "mov"]:
        return "video"
    if ext in ["mp3", "wav", "ogg"]:
        return "audio"

    return "document"


async def send_to_telegram(file):
    if not BOT_TOKEN or not CHAT_ID:
        raise RuntimeError("BOT_TOKEN or CHAT_ID not set")

    file_type = detect_type(file.filename)

    # 🔥 Choose correct Telegram API
    if file_type == "photo":
        url = f"{BASE_URL}/sendPhoto"
        files = {"photo": (file.filename, file.file)}
    elif file_type == "video":
        url = f"{BASE_URL}/sendVideo"
        files = {"video": (file.filename, file.file)}
    elif file_type == "audio":
        url = f"{BASE_URL}/sendAudio"
        files = {"audio": (file.filename, file.file)}
    else:
        url = f"{BASE_URL}/sendDocument"
        files = {"document": (file.filename, file.file)}

    async with httpx.AsyncClient(timeout=None) as client:
        response = await client.post(
            url,
            data={"chat_id": CHAT_ID},
            files=files,
        )

    response.raise_for_status()
    data = response.json()

    if not data.get("ok"):
        raise RuntimeError(f"Telegram error: {data}")

    result = data["result"]

    # ✅ RETURN STRUCTURED DATA
    if "video" in result:
        return {
            "file_id": result["video"]["file_id"],
            "thumbnail_id": result["video"]["thumb"]["file_id"],
            "type": "video",
            "message_id": result["message_id"],
        }

    if "photo" in result:
        return {
            "file_id": result["photo"][-1]["file_id"],
            "thumbnail_id": None,
            "type": "image",
            "message_id": result["message_id"],
        }

    if "audio" in result:
        return {
            "file_id": result["audio"]["file_id"],
            "thumbnail_id": None,
            "type": "music",
            "message_id": result["message_id"],
        }

    if "document" in result:
        return {
            "file_id": result["document"]["file_id"],
            "thumbnail_id": None,
            "type": "document",
            "message_id": result["message_id"],
        }

    raise RuntimeError("Unknown Telegram response format")
