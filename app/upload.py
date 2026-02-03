import os
import shutil
import requests
from fastapi import APIRouter, UploadFile, File, HTTPException
from app.database import get_connection

router = APIRouter()

# Load token from environment (or hardcode for testing)
# Make sure your main.py loads the .env before this router is imported/used, 
# or load it here again just to be safe.
from dotenv import load_dotenv
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")

@router.post("/upload")
async def upload_file(file: UploadFile = File(...)):
    if not BOT_TOKEN:
        raise HTTPException(status_code=500, detail="Bot token not found in .env")

    # 1. Determine the file type and Telegram Endpoint
    filename = file.filename.lower()
    
    # Default to "document" (generic file)
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

    # 2. Prepare the file for upload
    # We use a buffered reader so we don't need to save it to disk first
    file_content = await file.read()
    
    # 3. Send to Telegram
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/{telegram_method}"
    
    # We send the Chat ID (you can send to your own user ID or a channel)
    # If you don't have a specific chat_id, you can often just upload to the bot 
    # without a chat_id if using certain methods, but usually sendDocument/sendVideo 
    # REQUIRE a chat_id. 
    
    # HACK: If you are just using the bot as storage, you need to send it to SOME chat.
    # Do you have your own Chat ID? 
    # If not, try sending to a channel or your personal ID.
    # For now, I will assume you have a CHAT_ID in your .env as well.
    # If you don't, the upload might fail saying "chat_id is empty".
    
    CHAT_ID = os.getenv("CHAT_ID") 
    if not CHAT_ID:
         raise HTTPException(status_code=500, detail="CHAT_ID is missing in .env")

    files_data = {
        telegram_param_name: (file.filename, file_content)
    }
    data_payload = {
        "chat_id": CHAT_ID 
    }

    try:
        response = requests.post(url, files=files_data, data=data_payload, timeout=60)
        resp_json = response.json()
    except Exception as e:
        print(f"Upload error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    if not resp_json.get("ok"):
        print(f"Telegram Error: {resp_json}")
        raise HTTPException(status_code=500, detail=f"Telegram Error: {resp_json.get('description')}")

    # 4. Extract the File ID AND Thumbnail ID
    # Telegram returns different structures for photos vs videos
    result = resp_json["result"]
    
    final_file_id = ""
    thumbnail_id = None # Default to None
    
    if file_type_db == "image":
        # Photos are an array of sizes; take the last one (largest)
        final_file_id = result["photo"][-1]["file_id"]
        # For images, the image itself is the thumbnail
        thumbnail_id = final_file_id
        
    elif file_type_db == "video":
        final_file_id = result["video"]["file_id"]
        # FIX: Check if Telegram generated a thumbnail for the video
        video_info = result["video"]
        if "thumb" in video_info:
            thumbnail_id = video_info["thumb"]["file_id"]
        elif "thumbnail" in video_info:
            thumbnail_id = video_info["thumbnail"]["file_id"]
            
    else:
        final_file_id = result["document"]["file_id"]
        # Documents sometimes have thumbnails too
        if "thumb" in result["document"]:
            thumbnail_id = result["document"]["thumb"]["file_id"]

    # 5. Save to SQLite Database
    conn = get_connection()
    cur = conn.cursor()
    # FIX: We now insert the thumbnail_id as well
    cur.execute(
        "INSERT INTO files (name, file_id, type, thumbnail_id) VALUES (?, ?, ?, ?)",
        (file.filename, final_file_id, file_type_db, thumbnail_id)
    )
    conn.commit()
    conn.close()

    return {"status": "success", "file_id": final_file_id, "type": file_type_db}