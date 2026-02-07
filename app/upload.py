import os
import shutil
from pathlib import Path
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from fastapi.responses import JSONResponse
from app.telegram_bot import send_to_telegram

router = APIRouter()

# Temporary directory for file chunks
TEMP_UPLOAD_DIR = Path("temp_chunks")
TEMP_UPLOAD_DIR.mkdir(exist_ok=True)

@router.post("/upload-chunk")
async def upload_chunk(
    file: UploadFile = File(...),
    chunk_index: int = Form(...),
    total_chunks: int = Form(...),
    file_name: str = Form(...)
):
    """
    Receives individual 5MB file chunks from Flutter and merges them.
    """
    # 1. Create a unique folder for this specific file upload session
    file_session_dir = TEMP_UPLOAD_DIR / file_name
    file_session_dir.mkdir(exist_ok=True)

    # 2. Save the incoming chunk
    chunk_path = file_session_dir / f"{chunk_index}.part"
    try:
        with open(chunk_path, "wb") as buffer:
            buffer.write(await file.read())
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save chunk: {str(e)}")

    # 3. Check if this is the final chunk
    if chunk_index == total_chunks - 1:
        return await finalize_and_send(file_name, total_chunks)

    return JSONResponse(status_code=200, content={"status": "chunk_received", "chunk_index": chunk_index})

async def finalize_and_send(file_name: str, total_chunks: int):
    """
    Stitches chunks together and pushes to Telegram via Telethon.
    """
    final_file_path = TEMP_UPLOAD_DIR / f"final_{file_name}"
    file_session_dir = TEMP_UPLOAD_DIR / file_name

    try:
        # 4. Merge all chunks into one original file
        with open(final_file_path, "wb") as final_file:
            for i in range(total_chunks):
                chunk_path = file_session_dir / f"{i}.part"
                if not chunk_path.exists():
                    raise HTTPException(status_code=400, detail=f"Chunk {i} missing")
                
                with open(chunk_path, "rb") as chunk:
                    final_file.write(chunk.read())

        # 5. 🔥 Send the MERGED ORIGINAL to Telegram
        # IMPORTANT: We pass the STR PATH to Telethon for better performance
        # instead of a 'rb' file object.
        result = await send_to_telegram(str(final_file_path), file_name)

        if not result or "file_id" not in result:
            raise Exception("Telegram upload failed")

        return JSONResponse(
            status_code=200,
            content={
                "file_id": str(result["file_id"]),
                "message_id": result["message_id"],
                "type": result.get("type", "document"),
                "status": "success",
                "file_name": file_name
            },
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Finalizing failed: {str(e)}")

    finally:
        # 6. Cleanup: Delete chunks and the merged file to keep Render's disk light
        if file_session_dir.exists():
            shutil.rmtree(file_session_dir)
        if final_file_path.exists():
            final_file_path.unlink()