import os
import shutil
import json
import logging
import asyncio
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body
from fastapi.responses import JSONResponse
from app.telegram_bot import client, init_telethon, CHAT_ID, telegram_upload_lock

router = APIRouter()
logger = logging.getLogger(__name__)

# ============================================================
# 📂 TEMP STORAGE
# ============================================================
TEMP_UPLOAD_DIR = Path("temp_uploads")
TEMP_UPLOAD_DIR.mkdir(exist_ok=True)

# ============================================================
# 🔴 IN-MEMORY STORAGE (No Redis needed for local testing)
# ============================================================
upload_sessions = {}
cancelled_uploads = set()
session_locks = {}  # ⭐ Locks for thread-safe operations
active_uploads = {}  # ⭐ Track concurrent uploads for monitoring

# ============================================================
# ⚙️ CONFIGURATION
# ============================================================
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2GB
SESSION_EXPIRY = 3600  # 1 hour


# ============================================================
# 🔒 HELPER: Get or create lock for upload session
# ============================================================
def get_session_lock(upload_id: str) -> asyncio.Lock:
    if upload_id not in session_locks:
        session_locks[upload_id] = asyncio.Lock()
    return session_locks[upload_id]


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
    # ⭐ Track active uploads for monitoring
    if upload_id not in active_uploads:
        active_uploads[upload_id] = {
            "file_name": file_name,
            "start_time": asyncio.get_event_loop().time(),
            "total_chunks": total_chunks
        }
        logger.info(f"📁 New upload started: {file_name} (ID: {upload_id}, {total_chunks} chunks)")
    
    logger.info(f"📥 Received chunk {chunk_index}/{total_chunks} for {file_name}")
    
    # ❌ cancelled check
    if upload_id in cancelled_uploads:
        logger.warning(f"⚠️ Upload {upload_id} is cancelled")
        raise HTTPException(status_code=499, detail="Upload cancelled")

    session_dir = TEMP_UPLOAD_DIR / upload_id
    session_dir.mkdir(exist_ok=True)

    session_key = f"upload:{upload_id}"

    # ⭐ Get lock for this upload session
    lock = get_session_lock(upload_id)

    # ⭐ Use async lock to prevent race conditions
    async with lock:
        # ---- create session if not exists ----
        if session_key not in upload_sessions:
            upload_sessions[session_key] = {
                "total": total_chunks,
                "file_name": file_name,
                "finalized": False,  # ⭐ Boolean for clarity
                "received": set()
            }
            logger.info(f"🆕 Created new upload session for {upload_id}")

        # ---- prevent duplicate finalize ----
        if upload_sessions[session_key]["finalized"]:
            logger.info(f"⏭️ Ignoring chunk {chunk_index} - already finalized")
            return {"status": "ignored", "reason": "already_finalized"}

        # ---- save chunk ----
        chunk_path = session_dir / f"chunk_{chunk_index}"

        try:
            content = await file.read()
            
            # ⭐ File size validation (rough estimate)
            estimated_size = len(content) * total_chunks
            if estimated_size > MAX_FILE_SIZE:
                logger.error(f"❌ File too large: {estimated_size:,} bytes")
                raise HTTPException(status_code=413, detail="File too large")
            
            # ⭐ Check if chunk already exists (duplicate upload protection)
            if chunk_path.exists():
                logger.warning(f"⚠️ Chunk {chunk_index} already exists for {file_name}, skipping write")
            else:
                with open(chunk_path, "wb") as f:
                    f.write(content)
                logger.info(f"💾 Saved chunk {chunk_index}/{total_chunks} for {file_name} ({len(content):,} bytes)")
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"❌ Chunk save failed for {upload_id}: {e}")
            raise HTTPException(status_code=500, detail=f"Chunk save failed: {e}")

        # ---- mark chunk received ----
        upload_sessions[session_key]["received"].add(chunk_index)

        received_count = len(upload_sessions[session_key]["received"])
        total = upload_sessions[session_key]["total"]

        logger.info(f"📊 Progress: {received_count}/{total} chunks received for {file_name}")

        # ---- finalize when complete ----
        if received_count == total and not upload_sessions[session_key]["finalized"]:
            # ⭐ Mark as finalized IMMEDIATELY to prevent other chunks from triggering
            upload_sessions[session_key]["finalized"] = True
            logger.info(f"✅ All chunks received for {file_name}, starting finalization...")
            
            # ⭐ Finalize INSIDE the lock to prevent race conditions
            try:
                result = await finalize_upload(session_dir, upload_id)
                return result
            except Exception as e:
                # Reset finalized flag on error so user can retry
                upload_sessions[session_key]["finalized"] = False
                logger.error(f"❌ Finalization failed, reset finalized flag: {e}")
                raise

        return {
            "status": "chunk_received",
            "uploaded": received_count,
            "total": total,
            "chunk_index": chunk_index,
        }


# ============================================================
# 🛑 CANCEL UPLOAD
# ============================================================
@router.post("/upload-cancel")
async def cancel_upload(data: dict = Body(...)):
    upload_id = data.get("upload_id")
    if not upload_id:
        raise HTTPException(status_code=400, detail="Missing upload_id")

    cancelled_uploads.add(upload_id)
    
    file_name = active_uploads.get(upload_id, {}).get("file_name", upload_id)
    logger.info(f"🛑 Upload cancelled: {file_name} (ID: {upload_id})")

    # ⭐ Acquire lock before cleanup
    lock = get_session_lock(upload_id)
    async with lock:
        session_dir = TEMP_UPLOAD_DIR / upload_id
        if session_dir.exists():
            shutil.rmtree(session_dir, ignore_errors=True)
            logger.info(f"🗑️ Removed session directory: {session_dir}")

        session_key = f"upload:{upload_id}"
        if session_key in upload_sessions:
            del upload_sessions[session_key]
            logger.info(f"🗑️ Removed session data for {upload_id}")
    
    # Clean up lock and tracking
    if upload_id in session_locks:
        del session_locks[upload_id]
    
    if upload_id in active_uploads:
        del active_uploads[upload_id]

    return {"status": "cancelled"}


# ============================================================
# 📦 FINALIZE UPLOAD
# ============================================================
async def finalize_upload(session_dir: Path, upload_id: str):
    logger.info(f"🔄 Starting finalization for {upload_id}")
    
    if upload_id in cancelled_uploads:
        cancelled_uploads.remove(upload_id)
        logger.info(f"⏭️ Upload {upload_id} was cancelled during finalization")
        return {"status": "cancelled"}

    session_key = f"upload:{upload_id}"

    # ⭐ Safety check: session might have been cleaned up
    if session_key not in upload_sessions:
        logger.error(f"❌ Session {upload_id} not found during finalization")
        raise HTTPException(status_code=404, detail="Upload session not found")

    file_name = upload_sessions[session_key]["file_name"]
    total_chunks = upload_sessions[session_key]["total"]

    final_file_path = TEMP_UPLOAD_DIR / f"{upload_id}_{file_name}"

    try:
        # ⭐ Check for missing chunks
        missing_chunks = []
        for i in range(total_chunks):
            chunk_path = session_dir / f"chunk_{i}"
            if not chunk_path.exists():
                missing_chunks.append(i)

        if missing_chunks:
            logger.error(f"❌ Missing chunks for {file_name}: {missing_chunks}")
            raise HTTPException(
                status_code=400, 
                detail=f"Missing chunks: {missing_chunks}"
            )

        # ---- assemble ----
        logger.info(f"🔨 Assembling {total_chunks} chunks for {file_name}")
        with open(final_file_path, "wb") as final_file:
            for i in range(total_chunks):
                chunk_path = session_dir / f"chunk_{i}"
                with open(chunk_path, "rb") as chunk:
                    shutil.copyfileobj(chunk, final_file, length=1024 * 1024)  # 1MB buffer

        file_size = final_file_path.stat().st_size
        logger.info(f"✅ File assembled: {file_name} ({file_size:,} bytes)")

        # ⭐ Final size validation
        if file_size > MAX_FILE_SIZE:
            logger.error(f"❌ Assembled file exceeds size limit: {file_size:,} bytes")
            raise HTTPException(status_code=413, detail="File too large")

        # ---- Telegram upload ----
        logger.info(f"📤 Uploading to Telegram: {file_name}")
        await init_telethon()

        async with telegram_upload_lock:
            sent_message = await client.send_file(
                CHAT_ID,
                final_file_path,
                caption=file_name,
                force_document=True,
            )

        logger.info(f"✅ Uploaded to Telegram: {file_name} (msg_id: {sent_message.id})")

        return JSONResponse(
            content={
                "status": "done",
                "message_id": sent_message.id,
                "file_id": str(sent_message.id),
                "type": sent_message.file.mime_type or "application/octet-stream",
                "file_name": file_name,
                "size": file_size,
            }
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ Finalization failed for {file_name}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")
    finally:
        # ---- cleanup ----
        logger.info(f"🧹 Cleaning up {file_name}")
        
        if upload_id in cancelled_uploads:
            cancelled_uploads.discard(upload_id)
        
        if session_key in upload_sessions:
            del upload_sessions[session_key]
        
        if upload_id in session_locks:
            del session_locks[upload_id]
        
        if upload_id in active_uploads:
            elapsed = asyncio.get_event_loop().time() - active_uploads[upload_id]["start_time"]
            logger.info(f"⏱️ Total upload time for {file_name}: {elapsed:.2f}s")
            del active_uploads[upload_id]

        if session_dir.exists():
            try:
                shutil.rmtree(session_dir, ignore_errors=True)
                logger.info(f"🗑️ Removed session directory: {session_dir}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to remove session dir: {e}")

        if final_file_path.exists():
            try:
                os.remove(final_file_path)
                logger.info(f"🗑️ Removed final file: {final_file_path}")
            except Exception as e:
                logger.warning(f"⚠️ Failed to remove final file: {e}")


# ============================================================
# 📊 STATUS ENDPOINT
# ============================================================
@router.get("/upload-status/{upload_id}")
async def upload_status(upload_id: str):
    session_key = f"upload:{upload_id}"

    if session_key not in upload_sessions:
        return {"status": "not_found"}

    # ⭐ Thread-safe read
    lock = get_session_lock(upload_id)
    async with lock:
        if session_key not in upload_sessions:
            return {"status": "not_found"}
        
        session = upload_sessions[session_key]
        uploaded = len(session["received"])
        total = session["total"]
        finalized = session["finalized"]

    return {
        "status": "finalizing" if finalized else "uploading",
        "uploaded": uploaded,
        "total": total,
        "finalized": finalized,
    }


# ============================================================
# 📊 STATS ENDPOINT (Monitor concurrent uploads)
# ============================================================
@router.get("/upload-stats")
async def upload_stats():
    """
    Get current upload statistics
    Useful for monitoring when uploading multiple files in parallel
    """
    current_time = asyncio.get_event_loop().time()
    
    return {
        "active_uploads": len(active_uploads),
        "active_sessions": len(upload_sessions),
        "uploads": [
            {
                "upload_id": uid,
                "file_name": info["file_name"],
                "total_chunks": info["total_chunks"],
                "elapsed_seconds": round(current_time - info["start_time"], 2)
            }
            for uid, info in active_uploads.items()
        ]
    }

# ============================================================
# 🖼️ UPLOAD ENCRYPTED THUMBNAIL
# ============================================================
@router.post("/upload-thumbnail")
async def upload_thumbnail(file: UploadFile = File(...), upload_id: str = Form(default=None)):
    temp_thumb_path = None  # 🔥 IMPORTANT SAFETY FIX

    try:
        await init_telethon()

        # Use upload_id for unique temp filename to prevent collisions on parallel uploads
        unique_suffix = upload_id if upload_id else file.filename
        temp_thumb_path = TEMP_UPLOAD_DIR / f"thumb_{unique_suffix}.enc"

        # Save encrypted thumbnail temporarily
        with open(temp_thumb_path, "wb") as f:
            f.write(await file.read())

        # Upload encrypted binary as document
        async with telegram_upload_lock:
            sent_message = await client.send_file(
                CHAT_ID,
                temp_thumb_path,
                caption="encrypted_thumbnail",
                force_document=True,
            )

        return {
            "status": "done",
            "message_id": sent_message.id,
        }

    except Exception as e:
        logger.error(f"❌ Thumbnail upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Thumbnail upload failed")

    finally:
        # Cleanup safely
        if temp_thumb_path and temp_thumb_path.exists():
            try:
                os.remove(temp_thumb_path)
            except:
                pass