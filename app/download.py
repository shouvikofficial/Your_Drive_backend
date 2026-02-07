from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.telegram_bot import client, init_telethon, CHAT_ID
import mimetypes

router = APIRouter()

@router.get("/file/{message_id}")
async def get_file(message_id: int):
    """
    Streams file from Telegram channel.
    Includes Content-Length so frontend can show progress bar.
    """
    try:
        # Ensure connection
        await init_telethon()

        # 1️⃣ Fetch message
        message = await client.get_messages(CHAT_ID, ids=message_id)

        if not message or not message.file:
            raise HTTPException(status_code=404, detail="File not found")

        # 2️⃣ Get Metadata (Crucial for Frontend)
        file_size = message.file.size  # Total bytes (needed for progress bar)
        mime_type = message.file.mime_type or "application/octet-stream"
        
        # Determine filename
        file_name = message.file.name
        if not file_name:
            # Fallback: guess extension from mime type
            ext = mimetypes.guess_extension(mime_type) or ""
            file_name = f"file_{message_id}{ext}"

        # 3️⃣ Async Generator (Streams chunks from Telegram -> FastAPI -> User)
        async def file_stream():
            async for chunk in client.iter_download(message.media):
                yield chunk

        # 4️⃣ Streaming Response with Headers
        return StreamingResponse(
            file_stream(),
            media_type=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{file_name}"',
                "Content-Length": str(file_size),  # 👈 THIS FIXES THE PROGRESS BAR
                "Accept-Ranges": "bytes",          # Allows video seeking/partial content
            },
        )

    except HTTPException:
        raise

    except Exception as e:
        print(f"Download Error: {e}")
        raise HTTPException(status_code=500, detail="Telegram download failed")