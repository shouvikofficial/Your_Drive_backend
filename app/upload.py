import os
import shutil
import json
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body
from fastapi.responses import JSONResponse
from app.telegram_bot import client, init_telethon, CHAT_ID
import redis

router = APIRouter()

# ============================================================
# 📂 TEMP STORAGE
# ============================================================
TEMP_UPLOAD_DIR = Path("temp_uploads")
TEMP_UPLOAD_DIR.mkdir(exist_ok=True)

# ============================================================
# 🔴 REDIS CONNECTION (Render compatible)
# ============================================================
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
r = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True,
    ssl=True,
)

# ============================================================
# 🚀 CHUNK UPLOAD ENDPOINT (4-WORKER SAFE)
# ============================================================
@router.post("/upload-chunk")
async def upload_chunk(
    file: UploadFile = File(...),
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    file_name: str = Form(...),
    upload_id: str = Form(...),
):
    # ❌ cancelled check
    if r.sismember("cancelled_uploads", upload_id):
        raise HTTPException(status_code=499, detail="Upload cancelled")

    session_dir = TEMP_UPLOAD_DIR / upload_id
    session_dir.mkdir(exist_ok=True)

    session_key = f"upload:{upload_id}"

    # ---- create session in Redis if not exists ----
    if not r.exists(session_key):
        r.hset(session_key, mapping={
            "total": total_chunks,
            "file_name": file_name,
            "finalized": 0,
        })
        r.delete(f"{session_key}:received")

    # ---- prevent duplicate finalize ----
    if r.hget(session_key, "finalized") == "1":
        return {"status": "ignored"}

    # ---- save chunk ----
    chunk_path = session_dir / f"chunk_{chunk_index}"

    try:
        content = await file.read()
        if not chunk_path.exists():
            with open(chunk_path, "wb") as f:
                f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chunk save failed: {e}")

    # ---- mark chunk received ----
    r.sadd(f"{session_key}:received", chunk_index)

    # ✅ DEFINE THESE AGAIN
    received_count = r.scard(f"{session_key}:received")
    total = int(r.hget(session_key, "total"))

    # ---- finalize when complete (ATOMIC LOCK) ----
    if received_count == total:
        lock_key = f"{session_key}:finalizing"

        if r.set(lock_key, "1", nx=True, ex=300):
            return await finalize_upload(session_dir, upload_id)
        else:
            return {"status": "finalizing"}

    return {
        "status": "chunk_received",
        "uploaded": received_count,
        "total": total,
    }




# ============================================================
# 🛑 CANCEL UPLOAD (4-WORKER SAFE)
# ============================================================
@router.post("/upload-cancel")
async def cancel_upload(data: dict = Body(...)):
    upload_id = data.get("upload_id")
    if not upload_id:
        raise HTTPException(status_code=400, detail="Missing upload_id")

    r.sadd("cancelled_uploads", upload_id)

    session_dir = TEMP_UPLOAD_DIR / upload_id
    if session_dir.exists():
        shutil.rmtree(session_dir, ignore_errors=True)

    r.delete(f"upload:{upload_id}")
    r.delete(f"upload:{upload_id}:received")

    return {"status": "cancelled"}


# ============================================================
# 📦 FINALIZE UPLOAD (4-WORKER SAFE)
# ============================================================
async def finalize_upload(session_dir: Path, upload_id: str):
    if r.sismember("cancelled_uploads", upload_id):
        r.srem("cancelled_uploads", upload_id)
        return {"status": "cancelled"}

    session_key = f"upload:{upload_id}"

    file_name = r.hget(session_key, "file_name")
    total_chunks = int(r.hget(session_key, "total"))

    final_file_path = TEMP_UPLOAD_DIR / f"{upload_id}_{file_name}"

    try:
        # ---- assemble ----
        with open(final_file_path, "wb") as final_file:
            for i in range(total_chunks):
                chunk_path = session_dir / f"chunk_{i}"
                if not chunk_path.exists():
                    raise HTTPException(status_code=400, detail=f"Missing chunk {i}")

                with open(chunk_path, "rb") as chunk:
                    shutil.copyfileobj(chunk, final_file)

        # ---- Telegram upload ----
        await init_telethon()

        sent_message = await client.send_file(
            CHAT_ID,
            final_file_path,
            caption=file_name,
            force_document=True,
        )

        return JSONResponse(
            content={
                "status": "done",
                "message_id": sent_message.id,
                "file_id": str(sent_message.id),
                "type": sent_message.file.mime_type or "application/octet-stream",
                "file_name": file_name,
            }
        )

    finally:
        # ---- cleanup ----
        r.srem("cancelled_uploads", upload_id)
        r.delete(session_key)
        r.delete(f"{session_key}:received")

        if session_dir.exists():
            shutil.rmtree(session_dir, ignore_errors=True)

        if final_file_path.exists():
            try:
                os.remove(final_file_path)
            except Exception:
                pass


# ============================================================
# 📊 STATUS ENDPOINT
# ============================================================
@router.get("/upload-status/{upload_id}")
async def upload_status(upload_id: str):
    session_key = f"upload:{upload_id}"

    if not r.exists(session_key):
        return {"status": "done"}

    uploaded = r.scard(f"{session_key}:received")
    total = int(r.hget(session_key, "total"))

    return {
        "status": "uploading",
        "uploaded": uploaded,
        "total": total,
    }
