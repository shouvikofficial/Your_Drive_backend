import os
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse

from app.telegram_bot import send_to_telegram

router = APIRouter()

# ============================================================
# TEMP STORAGE
# ============================================================

TEMP_UPLOAD_DIR = Path("temp_chunks")
TEMP_UPLOAD_DIR.mkdir(exist_ok=True)


# ============================================================
# HELPER: SAFE FILENAME
# ============================================================

def safe_filename(name: str) -> str:
    """Remove dangerous path characters."""
    return os.path.basename(name).replace(" ", "_")


# ============================================================
# CHUNK UPLOAD ENDPOINT
# ============================================================

@router.post("/upload-chunk")
async def upload_chunk(
    file: UploadFile = File(...),
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    file_name: str = Form(...),
    upload_id: str | None = Form(None),
):
    """
    Production-ready resumable chunk upload.
    """

    # 1️⃣ Create or reuse upload session
    if not upload_id:
        upload_id = str(uuid4())

    file_name = safe_filename(file_name)

    file_session_dir = TEMP_UPLOAD_DIR / upload_id
    file_session_dir.mkdir(exist_ok=True)

    chunk_path = file_session_dir / f"{chunk_index}.part"

    # 2️⃣ Save chunk safely
    try:
        with open(chunk_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(500, f"Failed to save chunk: {str(e)}")

    # 3️⃣ Check uploaded chunk count (fast)
    uploaded_chunks = sum(1 for _ in file_session_dir.glob("*.part"))

    if uploaded_chunks < total_chunks:
        return JSONResponse(
            status_code=200,
            content={
                "status": "chunk_received",
                "chunk_index": chunk_index,
                "upload_id": upload_id,
                "uploaded_chunks": uploaded_chunks,
                "total_chunks": total_chunks,
            },
        )

    # 4️⃣ All chunks uploaded → finalize
    return await finalize_and_send(upload_id, file_name, total_chunks)


# ============================================================
# FINALIZE + TELEGRAM UPLOAD
# ============================================================

async def finalize_and_send(upload_id: str, file_name: str, total_chunks: int):
    """
    Merge chunks → upload to Telegram → cleanup.
    """

    file_session_dir = TEMP_UPLOAD_DIR / upload_id
    final_file_path = TEMP_UPLOAD_DIR / f"{upload_id}_{file_name}"

    try:
        # 1️⃣ Merge chunks in order
        with open(final_file_path, "wb") as final_file:
            for i in range(total_chunks):
                chunk_path = file_session_dir / f"{i}.part"

                if not chunk_path.exists():
                    raise HTTPException(400, f"Missing chunk {i}")

                with open(chunk_path, "rb") as chunk:
                    shutil.copyfileobj(chunk, final_file)

        # 2️⃣ Upload merged file to Telegram
        result = await send_to_telegram(str(final_file_path), file_name)

        if not result or "file_id" not in result:
            raise Exception("Telegram upload failed")

        return JSONResponse(
            status_code=200,
            content={
                "status": "success",
                "file_id": str(result["file_id"]),
                "message_id": result["message_id"],
                "type": result.get("type", "document"),
                "file_name": file_name,
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, f"Finalizing failed: {str(e)}")

    finally:
        # 3️⃣ Safe cleanup AFTER upload attempt
        try:
            if file_session_dir.exists():
                shutil.rmtree(file_session_dir)

            if final_file_path.exists():
                final_file_path.unlink()
        except Exception:
            pass
