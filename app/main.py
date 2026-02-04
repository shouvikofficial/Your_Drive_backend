import os
import requests
from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from fastapi.middleware.cors import CORSMiddleware

from app.upload import router as upload_router
from app.files import router as files_router
from app.auth import router as auth_router
from app.database import init_db

# --------------------------------------------------
# INIT
# --------------------------------------------------
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise ValueError("Error: BOT_TOKEN is missing in .env file")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

init_db()

# --------------------------------------------------
# ROUTERS
# --------------------------------------------------
app.include_router(auth_router)   # SIGNUP + LOGIN
app.include_router(upload_router)
app.include_router(files_router)

# --------------------------------------------------
# TELEGRAM IMAGE BRIDGE
# --------------------------------------------------
@app.get("/image/{file_id}")
def get_telegram_image(file_id: str):
    response = requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
        params={"file_id": file_id},
    )

    data = response.json()

    if not data.get("ok"):
        return {"error": "File not found on Telegram"}

    file_path = data["result"]["file_path"]
    direct_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"

    return RedirectResponse(direct_url)
