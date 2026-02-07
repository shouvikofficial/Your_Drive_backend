from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import StreamingResponse
from app.telegram_bot import client, init_telethon, CHAT_ID
import mimetypes

router = APIRouter()

# ==================================================================
# 1️⃣ ORIGINAL FILE ENDPOINT (Full Quality / Download)
# ==================================================================
@router.get("/file/{message_id}")
async def get_file(message_id: int):
    """
    Streams the original full-quality file from Telegram.
    Used when the user clicks "Download" or opens the full viewer.
    """
    try:
        # Ensure connection
        await init_telethon()

        # Fetch message
        message = await client.get_messages(CHAT_ID, ids=message_id)

        if not message or not message.file:
            raise HTTPException(status_code=404, detail="File not found")

        # Get Metadata
        file_size = message.file.size
        mime_type = message.file.mime_type or "application/octet-stream"
        
        # Determine filename
        file_name = message.file.name
        if not file_name:
            ext = mimetypes.guess_extension(mime_type) or ""
            file_name = f"file_{message_id}{ext}"

        # Async Generator for streaming
        async def file_stream():
            async for chunk in client.iter_download(message.media):
                yield chunk

        # Return Stream with Progress Headers
        return StreamingResponse(
            file_stream(),
            media_type=mime_type,
            headers={
                "Content-Disposition": f'attachment; filename="{file_name}"',
                "Content-Length": str(file_size),  # ✅ Enables Progress Bar
                "Accept-Ranges": "bytes",          # ✅ Enables Video Seeking
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        print(f"Download Error: {e}")
        raise HTTPException(status_code=500, detail="Telegram download failed")


# ==================================================================
# 2️⃣ THUMBNAIL ENDPOINT (Small Preview / Grid View)
# ==================================================================
@router.get("/thumbnail/{message_id}")
async def get_thumbnail(message_id: int):
    """
    Fetches a tiny, low-quality thumbnail (~10KB).
    Used for the Grid View to make scrolling instant and smooth.
    """
    try:
        await init_telethon()
        message = await client.get_messages(CHAT_ID, ids=message_id)

        if not message or not message.file:
            raise HTTPException(status_code=404, detail="File not found")

        # 🚀 'm' = Medium thumbnail (perfect balance of speed vs quality)
        # We download to memory (bytes) because it is very small.
        thumb_data = await client.download_media(message, file=bytes, thumb='m')

        if not thumb_data:
            # If the file has no thumbnail (like a .zip or .apk), return 404.
            # The Flutter frontend will catch this and show a File Icon instead.
            raise HTTPException(status_code=404, detail="No thumbnail available")

        # Return the image bytes directly
        return Response(content=thumb_data, media_type="image/jpeg")

    except Exception as e:
        # print(f"Thumbnail Error: {e}") 
        # Fail silently with 404 so the app shows the default icon
        raise HTTPException(status_code=404, detail="Thumbnail failed")