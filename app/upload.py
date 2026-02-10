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

# 🧠 In-memory trackers (use Redis in real production)
CANCELLED_UPLOADS = set()
UPLOAD_SESSIONS = {}


# ============================================================
# 🚀 CHUNK UPLOAD ENDPOINT (PARALLEL SAFE)
# ============================================================
@router.post("/upload-chunk")
async def upload_chunk(
    file: UploadFile = File(...),
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    file_name: str = Form(...),
    upload_id: str = Form(...),
):
    if upload_id in CANCELLED_UPLOADS:
        raise HTTPException(status_code=499, detail="Upload cancelled")

    session_dir = TEMP_UPLOAD_DIR / upload_id
    session_dir.mkdir(exist_ok=True)

    # ---- create session if first chunk ----
    if upload_id not in UPLOAD_SESSIONS:
        UPLOAD_SESSIONS[upload_id] = {
            "total": total_chunks,
            "received": set(),
            "finalized": False,
            "file_name": file_name,
        }

    session = UPLOAD_SESSIONS[upload_id]

    # ---- save chunk ----
    chunk_path = session_dir / f"chunk_{chunk_index}"
    content = await file.read()
    with open(chunk_path, "wb") as f:
        f.write(content)

    session["received"].add(chunk_index)

    # ---- ignore if already finalized ----
    if session["finalized"]:
        return {"status": "ignored"}

    # ---- check completion ----
    if len(session["received"]) == session["total"]:
        session["finalized"] = True
        return await finalize_upload(session_dir, upload_id)

    return {
        "status": "chunk_received",
        "uploaded": len(session["received"]),
        "total": session["total"],
    }


# ============================================================
# 🛑 CANCEL UPLOAD
# ============================================================
@router.post("/upload-cancel")
async def cancel_upload(data: dict = Body(...)):
    upload_id = data.get("upload_id")
    if not upload_id:
        raise HTTPException(status_code=400, detail="Missing upload_id")

    CANCELLED_UPLOADS.add(upload_id)

    session_dir = TEMP_UPLOAD_DIR / upload_id
    if session_dir.exists():
        shutil.rmtree(session_dir)

    UPLOAD_SESSIONS.pop(upload_id, None)

    return {"status": "cancelled"}


# ============================================================
# 📦 FINALIZE UPLOAD (PARALLEL SAFE)
# ============================================================
async def finalize_upload(session_dir: Path, upload_id: str):
    if upload_id in CANCELLED_UPLOADS:
        CANCELLED_UPLOADS.discard(upload_id)
        return {"status": "cancelled"}

    session = UPLOAD_SESSIONS.get(upload_id)
    if not session:
        raise HTTPException(status_code=400, detail="Session not found")

    file_name = session["file_name"]
    total_chunks = session["total"]

    final_file_path = TEMP_UPLOAD_DIR / f"{upload_id}_{file_name}"

    try:
        # ---- assemble file ----
        with open(final_file_path, "wb") as final_file:
            for i in range(total_chunks):
                chunk_path = session_dir / f"chunk_{i}"
                if not chunk_path.exists():
                    raise HTTPException(status_code=400, detail=f"Missing chunk {i}")
                with open(chunk_path, "rb") as chunk:
                    final_file.write(chunk.read())

        if upload_id in CANCELLED_UPLOADS:
            return {"status": "cancelled"}

        # ---- upload to Telegram ----
        await init_telethon()

        sent_message = await client.send_file(
            CHAT_ID,
            final_file_path,
            caption=file_name,
            force_document=True
        )

        return JSONResponse(content={
            "status": "done",
            "message_id": sent_message.id,
            "file_id": str(sent_message.id),
            "type": sent_message.file.mime_type or "application/octet-stream",
            "file_name": file_name
        })

    finally:
        # ---- cleanup ----
        CANCELLED_UPLOADS.discard(upload_id)
        UPLOAD_SESSIONS.pop(upload_id, None)

        if session_dir.exists():
            shutil.rmtree(session_dir)

        if final_file_path.exists():
            os.remove(final_file_path)


# ============================================================
# 📊 STATUS ENDPOINT
# ============================================================
@router.get("/upload-status/{upload_id}")
async def upload_status(upload_id: str):
    session = UPLOAD_SESSIONS.get(upload_id)
    if not session:
        return {"status": "done"}

    return {
        "status": "uploading",
        "uploaded": len(session["received"]),
        "total": session["total"],
    }
