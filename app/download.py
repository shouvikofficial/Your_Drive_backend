from fastapi import APIRouter, HTTPException
import requests, os

router = APIRouter()

BOT_TOKEN = os.getenv("BOT_TOKEN")

@router.get("/file/{file_id}")
def get_file(file_id: str):
    # Ask Telegram where the file lives
    r = requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
        params={"file_id": file_id},
        timeout=10,
    ).json()

    if not r.get("ok"):
        raise HTTPException(status_code=404, detail="File not found")

    file_path = r["result"]["file_path"]

    # Return a REAL image URL
    return {
        "url": f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    }
