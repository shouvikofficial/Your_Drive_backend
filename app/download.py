from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.telegram_bot import client, init_telethon, CHAT_ID
import mimetypes

router = APIRouter()


# ==================================================================
# 1️⃣ ORIGINAL FILE ENDPOINT (Encrypted Stream / Full Viewer)
# ==================================================================
@router.get("/file/{message_id}")
async def get_file(message_id: int):
    """
    Streams the ORIGINAL encrypted file from Telegram.
    Flutter will decrypt locally (zero-knowledge).
    """
    try:
        await init_telethon()

        message = await client.get_messages(CHAT_ID, ids=message_id)

        if not message or not message.file:
            raise HTTPException(status_code=404, detail="File not found")

        file_size = message.file.size
        mime_type = message.file.mime_type or "application/octet-stream"

        file_name = message.file.name
        if not file_name:
            ext = mimetypes.guess_extension(mime_type) or ""
            file_name = f"file_{message_id}{ext}"

        async def file_stream():
            async for chunk in client.iter_download(message.media):
                yield chunk

        return StreamingResponse(
            file_stream(),
            media_type="application/octet-stream",  # ⚠️ MUST be binary
            headers={
                "Content-Disposition": f'attachment; filename="{file_name}"',
                "Content-Length": str(file_size),
                "Accept-Ranges": "bytes",
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Download Error: {e}")
        raise HTTPException(status_code=500, detail="Telegram download failed")


# ==================================================================
# 2️⃣ THUMBNAIL ENDPOINT (Encrypted Stream for Grid Preview)
# ==================================================================
@router.get("/thumbnail/{message_id}")
async def get_thumbnail(message_id: int):
    """
    Returns the SAME encrypted bytes as /file.
    Flutter decrypts and shows a resized preview locally.
    This keeps true zero-knowledge security.
    """
    try:
        await init_telethon()

        message = await client.get_messages(CHAT_ID, ids=message_id)

        if not message or not message.file:
            raise HTTPException(status_code=404, detail="File not found")

        async def file_stream():
            async for chunk in client.iter_download(message.media):
                yield chunk

        return StreamingResponse(
            file_stream(),
            media_type="application/octet-stream",  # ⚠️ encrypted binary only
        )

    except Exception as e:
        print(f"Thumbnail Error: {e}")
        raise HTTPException(status_code=404, detail="Thumbnail failed")
