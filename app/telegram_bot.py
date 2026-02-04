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
    file_type = detect_type(file.filename)

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
        r = await client.post(
            url,
            data={"chat_id": CHAT_ID},
            files=files,
        )

    r.raise_for_status()
    data = r.json()

    if not data.get("ok"):
        raise RuntimeError(data)

    result = data["result"]

    # 🔥 RETURN BOTH FILE_ID AND THUMBNAIL_ID
    if "video" in result:
        return {
            "file_id": result["video"]["file_id"],
            "thumbnail_id": result["video"]["thumb"]["file_id"],
            "type": "video",
        }

    if "photo" in result:
        return {
            "file_id": result["photo"][-1]["file_id"],
            "thumbnail_id": None,
            "type": "image",
        }

    if "document" in result:
        return {
            "file_id": result["document"]["file_id"],
            "thumbnail_id": None,
            "type": "document",
        }

    raise RuntimeError("Unknown Telegram response")
