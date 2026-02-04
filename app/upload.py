import os
import requests
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, Header
from app.database import get_connection
from dotenv import load_dotenv
from jose import jwt, JWTError

# --------------------------------------------------
# INIT
# --------------------------------------------------
router = APIRouter()
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")

SECRET_KEY = os.getenv("SECRET_KEY", "SUPER_SECRET_KEY")
ALGORITHM = "HS256"

# --------------------------------------------------
# AUTH: GET CURRENT USER ID FROM TOKEN
# --------------------------------------------------
def get_current_user_id(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.replace("Bearer ", "")

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return payload["user_id"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

# --------------------------------------------------
# UPLOAD ROUTE
# --------------------------------------------------
@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    user_id: int = Depends(get_current_user_id)
):
    if not BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Bot token not found in .env")

    if not CHAT_ID:
        raise HTTPException(status_code=500, detail="CHAT_ID is missing in .env")

    filename = file.filename.lower()

    telegram_method = "sendDocument"
    file_type_db = "document"
    telegram_param_name = "document"

    if filename.endswith((".jpg", ".jpeg", ".png", ".gif")):
        telegram_method = "sendPhoto"
        file_type_db = "image"
        telegram_param_name = "photo"

    elif filename.endswith((".mp4", ".mov", ".avi", ".mkv")):
        telegram_method = "sendVideo"
        file_type_db = "video"
        telegram_param_name = "video"

    file_content = await file.read()

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{telegram_method}"

    try:
        response = requests.post(
            url,
            files={telegram_param_name: (file.filename, file_content)},
            data={"chat_id": CHAT_ID},
            timeout=60
        )
        resp_json = response.json()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if not resp_json.get("ok"):
        raise HTTPException(
            status_code=500,
            detail=f"Telegram Error: {resp_json.get('description')}"
        )

    # --------------------------------------------------
    # FILE + THUMBNAIL
    # --------------------------------------------------
    result = resp_json["result"]
    final_file_id = ""
    thumbnail_id = None

    if file_type_db == "image":
        final_file_id = result["photo"][-1]["file_id"]
        thumbnail_id = final_file_id

    elif file_type_db == "video":
        final_file_id = result["video"]["file_id"]
        thumbnail_id = result["video"].get("thumb", {}).get("file_id")

    else:
        final_file_id = result["document"]["file_id"]
        thumbnail_id = result["document"].get("thumb", {}).get("file_id")

    # --------------------------------------------------
    # DATABASE SAVE (USER ISOLATED)
    # --------------------------------------------------
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        INSERT INTO files (user_id, name, file_id, type, thumbnail_id)
        VALUES (?, ?, ?, ?, ?)
        """,
        (user_id, file.filename, final_file_id, file_type_db, thumbnail_id)
    )

    conn.commit()
    conn.close()

    return {
        "status": "success",
        "file_id": final_file_id,
        "type": file_type_db
    }
