import os
import requests
from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from dotenv import load_dotenv
from app.upload import router as upload_router
from app.database import init_db
from fastapi.middleware.cors import CORSMiddleware

# 1. Load the variables from .env file
load_dotenv()

# 2. Get the token safely
BOT_TOKEN = os.getenv("BOT_TOKEN")

# Safety check: Stop the server immediately if token is missing
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
app.include_router(upload_router)

# --- THE IMAGE BRIDGE ---
@app.get("/image/{file_id}")
def get_telegram_image(file_id: str):
    if not file_id:
        return {"error": "No file ID provided"}

    response = requests.get(
        f"https://api.telegram.org/bot{BOT_TOKEN}/getFile",
        params={"file_id": file_id},
    )
    data = response.json()

    if not data.get("ok"):
        print(f"Telegram Error: {data}")
        return {"error": "File not found on Telegram"}

    file_path = data["result"]["file_path"]

    # Redirect to the actual image
    direct_url = f"https://api.telegram.org/file/bot{BOT_TOKEN}/{file_path}"
    return RedirectResponse(direct_url)


@app.get("/files")
def get_files(request: Request):
    from app.database import get_connection

    conn = get_connection()
    cur = conn.cursor()

    # FIX: Select 'thumbnail_id' (index 4) from database
    cur.execute("SELECT id, name, file_id, type, thumbnail_id FROM files")
    rows = cur.fetchall()

    conn.close()

    # ✅ Dynamic base URL (works everywhere)
    base_url = str(request.base_url).rstrip("/")

    results = []
    for r in rows:
        # r[0]=id, r[1]=name, r[2]=file_id, r[3]=type, r[4]=thumbnail_id

        thumb_link = None

        if r[4]:
            # If we have a stored thumbnail ID (from a video), use it
            thumb_link = f"{base_url}/image/{r[4]}"
        elif r[3] == "image":
            # If it is an image, the file itself is the thumbnail
            thumb_link = f"{base_url}/image/{r[2]}"

        results.append({
            "id": r[0],
            "name": r[1],
            "type": r[3],
            # URL points to our bridge endpoint
            "url": f"{base_url}/image/{r[2]}",
            # Send the calculated thumbnail URL to frontend
            "thumbnail_url": thumb_link
        })

    return results
