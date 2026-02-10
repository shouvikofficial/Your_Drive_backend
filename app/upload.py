import os
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Body
from fastapi.responses import JSONResponse
from app.telegram_bot import client, init_telethon, CHAT_ID

router = APIRouter()

# ============================================================
# 📂 TEMP STORAGE CONFIG
# ============================================================
TEMP_UPLOAD_DIR = Path("temp_uploads")
TEMP_UPLOAD_DIR.mkdir(exist_ok=True)

# 🧠 Track cancelled upload IDs in memory 
# (In a production app with multiple workers, use Redis or a Database for this)
CANCELLED_UPLOADS = set()

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
    # 🛑 Check if this upload was already cancelled
    if upload_id in CANCELLED_UPLOADS:
        raise HTTPException(status_code=499, detail="Upload was cancelled by user")

    session_dir = TEMP_UPLOAD_DIR / upload_id
    session_dir.mkdir(exist_ok=True)

    chunk_path = session_dir / f"chunk_{chunk_index}"

    try:
        content = await file.read()
        with open(chunk_path, "wb") as f:
            f.write(content)
        print(f"✅ Saved Chunk {chunk_index + 1}/{total_chunks} for {file_name}")

    except Exception as e:
        print(f"❌ Error saving chunk: {e}")
        raise HTTPException(status_code=500, detail="Failed to save chunk")

    existing_chunks = sorted(int(p.name.split("_")[1]) for p in session_dir.glob("chunk_*"))
    uploaded_chunks_count = len(existing_chunks)

    if uploaded_chunks_count < total_chunks:
        return JSONResponse(content={
            "status": "chunk_received",
            "chunk_index": chunk_index,
            "uploaded_chunks": existing_chunks,
            "message": "Chunk saved"
        })

    # ============================================================
    # 🏁 ALL CHUNKS RECEIVED -> ASSEMBLE & UPLOAD
    # ============================================================
    return await finalize_upload(session_dir, upload_id, file_name, total_chunks)


# ============================================================
# 🛑 NEW: CANCEL UPLOAD ENDPOINT
# ============================================================
@router.post("/upload-cancel")
async def cancel_upload(data: dict = Body(...)):
    """
    Called by Flutter when the user taps the Cross icon.
    Stops the process and cleans up chunks immediately.
    """
    upload_id = data.get("upload_id")
    if not upload_id:
        raise HTTPException(status_code=400, detail="Missing upload_id")

    # 1. Mark as cancelled so finalize_upload stops
    CANCELLED_UPLOADS.add(upload_id)

    # 2. Delete temporary chunks immediately
    session_dir = TEMP_UPLOAD_DIR / upload_id
    try:
        if session_dir.exists():
            shutil.rmtree(session_dir)
            print(f"🗑️ Cancelled: Deleted chunks for {upload_id}")
        return {"status": "cancelled", "message": "Upload aborted and cleaned up"}
    except Exception as e:
        print(f"⚠️ Cancel Error: {e}")
        return {"status": "error", "message": str(e)}


# ============================================================
# 📦 FINALIZE UPLOAD (Updated with Cancel Check)
# ============================================================
async def finalize_upload(session_dir: Path, upload_id: str, file_name: str, total_chunks: int):
    # 🛑 Final check before starting reassembly
    if upload_id in CANCELLED_UPLOADS:
        print(f"🛑 Aborting finalization for {upload_id}: User Cancelled")
        CANCELLED_UPLOADS.remove(upload_id) # Cleanup the set
        return JSONResponse(content={"status": "cancelled"}, status_code=200)

    print(f"📦 All chunks received. Assembling {file_name}...")
    final_file_path = TEMP_UPLOAD_DIR / f"{upload_id}_{file_name}"

    try:
        # Reassemble
        with open(final_file_path, "wb") as final_file:
            for i in range(total_chunks):
                chunk_path = session_dir / f"chunk_{i}"
                if not chunk_path.exists():
                    raise HTTPException(status_code=400, detail=f"Missing chunk {i}")
                with open(chunk_path, "rb") as chunk:
                    final_file.write(chunk.read())

        # 🛑 Final check before Telegram upload
        if upload_id in CANCELLED_UPLOADS:
            print(f"🛑 Aborting Telegram upload for {upload_id}")
            return JSONResponse(content={"status": "cancelled"}, status_code=200)

        # Upload to Telegram
        await init_telethon()
        print(f"🚀 Uploading to Telegram: {file_name}")

        sent_message = await client.send_file(
            CHAT_ID,
            final_file_path,
            caption=file_name,
            force_document=True
        )

        print(f"✅ Upload Complete! Message ID: {sent_message.id}")

        return JSONResponse(content={
            "status": "done",
            "message_id": sent_message.id,
            "file_id": str(sent_message.id),
            "type": sent_message.file.mime_type or "application/octet-stream",
            "file_name": file_name
        })

    except Exception as e:
        print(f"❌ Finalization Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

    finally:
        # Cleanup
        if upload_id in CANCELLED_UPLOADS:
            CANCELLED_UPLOADS.remove(upload_id)
            
        if session_dir.exists():
            shutil.rmtree(session_dir)
        if final_file_path.exists():
            os.remove(final_file_path)


@router.get("/upload-status/{upload_id}")
async def upload_status(upload_id: str):
    session_dir = TEMP_UPLOAD_DIR / upload_id
    if session_dir.exists():
        chunks = list(session_dir.glob("chunk_*"))
        return {"status": "uploading", "uploaded_chunks": len(chunks)}
    return {"status": "done"}