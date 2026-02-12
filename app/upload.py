import os
import shutil
import asyncio
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body
from fastapi.responses import JSONResponse
import redis

# ✅ Import the safe telegram uploader helper
# Make sure your telegram_bot.py is in the app folder
from app.telegram_bot import send_to_telegram

router = APIRouter()

# ============================================================
# 📂 TEMP STORAGE
# ============================================================
TEMP_UPLOAD_DIR = Path("temp_uploads")
TEMP_UPLOAD_DIR.mkdir(exist_ok=True)

# ============================================================
# 🔴 REDIS CONNECTION
# ============================================================
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.Redis.from_url(REDIS_URL, decode_responses=True)

# ============================================================
# 🚀 CHUNK UPLOAD ENDPOINT
# ============================================================
@router.post("/upload-chunk")
async def upload_chunk(
    file: UploadFile = File(...),
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    file_name: str = Form(...),
    upload_id: str = Form(...),
):
    session_key = f"upload:{upload_id}"

    # 1. Check if cancelled
    if r.sismember("cancelled_uploads", upload_id):
        raise HTTPException(status_code=499, detail="Upload cancelled")

    # 2. Check if already done (Idempotency)
    # If the client retries the last chunk, return success immediately
    if r.hget(session_key, "status") == "done":
        stored_result = r.hgetall(session_key)
        return {
            "status": "done",
            "message_id": stored_result.get("message_id"),
            "file_id": stored_result.get("file_id"),
            "file_name": file_name
        }

    session_dir = TEMP_UPLOAD_DIR / upload_id
    session_dir.mkdir(exist_ok=True)

    # 3. Initialize session if new
    if not r.exists(session_key):
        r.hset(session_key, mapping={
            "total": total_chunks,
            "file_name": file_name,
            "status": "uploading",
            "uploaded_chunks": 0
        })
        # Set a safety TTL (e.g., 24 hours) in case it gets abandoned
        r.expire(session_key, 86400)

    # 4. Save the chunk
    chunk_path = session_dir / f"chunk_{chunk_index}"
    try:
        content = await file.read()
        # Only write if it doesn't exist to save I/O
        if not chunk_path.exists():
            with open(chunk_path, "wb") as f:
                f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chunk save failed: {e}")

    # 5. Mark chunk as received (Atomic)
    r.sadd(f"{session_key}:received", chunk_index)
    r.expire(f"{session_key}:received", 86400)

    received_count = r.scard(f"{session_key}:received")
    
    # 6. Check for completion
    if received_count == total_chunks:
        # Prevent race condition: multiple workers trying to finalize
        # Only the worker that sets status to 'finalizing' proceeds
        if r.hsetnx(session_key, "lock_finalize", "1"):
            r.hset(session_key, "status", "finalizing")
            return await finalize_upload(session_dir, upload_id, session_key, file_name, total_chunks)
        else:
            # Another worker is already finalizing, wait or return ignored
            return {"status": "finalizing_in_progress"}

    return {
        "status": "chunk_received",
        "uploaded": received_count,
        "total": total_chunks,
    }


# ============================================================
# 📦 FINALIZE UPLOAD (TELEGRAM INTEGRATION FIXED)
# ============================================================
async def finalize_upload(session_dir: Path, upload_id: str, session_key: str, file_name: str, total_chunks: int):
    final_file_path = TEMP_UPLOAD_DIR / f"{upload_id}_{file_name}"
    
    try:
        # 1. Assemble File
        with open(final_file_path, "wb") as final_file:
            for i in range(total_chunks):
                chunk_path = session_dir / f"chunk_{i}"
                if not chunk_path.exists():
                    raise HTTPException(status_code=500, detail=f"Missing chunk {i} during assembly")
                
                with open(chunk_path, "rb") as chunk:
                    shutil.copyfileobj(chunk, final_file)

        # 2. Upload to Telegram (Safe Method)
        # Using the improved helper function that handles retries and locking
        sent_message = await send_to_telegram(str(final_file_path), file_name)

        if sent_message is None:
            raise Exception("Telegram upload returned None (failed)")

        # 3. Prepare Success Data
        result_data = {
            "status": "done",
            "message_id": str(sent_message.id),       # ✅ Safe String ID
            "file_id": str(sent_message.id),          # ✅ Safe String ID
            "file_name": file_name,
            # Optional: Capture mime type if available
            "mime_type": sent_message.file.mime_type if sent_message.file else "application/octet-stream"
        }

        # 4. Persist Result in Redis (CRITICAL FIX)
        # Instead of deleting, we update the hash with the results
        # and set a TTL so frontend has time to poll /upload-status
        r.hset(session_key, mapping=result_data)
        r.expire(session_key, 3600) # Keep result for 1 hour so frontend can fetch it
        
        # Cleanup "received" set immediately to save RAM
        r.delete(f"{session_key}:received") 

        return JSONResponse(content=result_data)

    except Exception as e:
        r.hset(session_key, "status", "error")
        r.hset(session_key, "error_msg", str(e))
        # Release lock so retry is possible (optional)
        r.delete(f"{session_key}:lock_finalize")
        raise HTTPException(status_code=500, detail=f"Finalization failed: {e}")

    finally:
        # 5. Cleanup Disk (Always)
        if session_dir.exists():
            shutil.rmtree(session_dir, ignore_errors=True)
        
        if final_file_path.exists():
            try:
                os.remove(final_file_path)
            except Exception:
                pass


# ============================================================
# 🛑 CANCEL UPLOAD
# ============================================================
@router.post("/upload-cancel")
async def cancel_upload(data: dict = Body(...)):
    upload_id = data.get("upload_id")
    if not upload_id:
        raise HTTPException(status_code=400, detail="Missing upload_id")

    r.sadd("cancelled_uploads", upload_id)
    r.expire("cancelled_uploads", 86400) # Auto cleanup cancel list

    session_dir = TEMP_UPLOAD_DIR / upload_id
    if session_dir.exists():
        shutil.rmtree(session_dir, ignore_errors=True)

    r.delete(f"upload:{upload_id}")
    r.delete(f"upload:{upload_id}:received")

    return {"status": "cancelled"}


# ============================================================
# 📊 STATUS ENDPOINT (FIXED)
# ============================================================
@router.get("/upload-status/{upload_id}")
async def upload_status(upload_id: str):
    session_key = f"upload:{upload_id}"

    # If key doesn't exist, it might have expired or never started
    if not r.exists(session_key):
        return {"status": "not_found"}

    data = r.hgetall(session_key)
    status = data.get("status", "unknown")

    if status == "done":
        # CRITICAL: Return the actual IDs needed for Supabase
        return {
            "status": "done",
            "message_id": data.get("message_id"),
            "file_id": data.get("file_id"),
            "file_name": data.get("file_name")
        }
    
    elif status == "uploading":
        # Calculate progress
        received = r.scard(f"{session_key}:received")
        total = int(data.get("total", 0))
        return {
            "status": "uploading",
            "uploaded": received,
            "total": total
        }
        
    return {"status": status, "detail": data.get("error_msg")}