import io
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from app.telegram_bot import client, init_telethon

router = APIRouter()

@router.get("/file/{file_id}")
async def get_file(file_id: str):
    """
    Downloads large files (>20MB) from Telegram via MTProto 
    and streams them to the Flutter app.
    """
    try:
        # 1. Ensure Telethon is online
        await init_telethon()

        # 2. Check if the file exists and get its metadata
        # Note: Telethon can fetch the file directly using the file_id string
        # We use a BytesIO object to store the data in memory temporarily
        file_buffer = io.BytesIO()
        
        # 3. Download the file from the channel
        # Telethon downloads the file in chunks automatically to save RAM
        downloaded_file = await client.download_media(file_id, file=file_buffer)
        
        if not downloaded_file:
            raise HTTPException(status_code=404, detail="File not found on Telegram servers")

        # 4. Seek to the beginning of the buffer so the streamer can read it
        file_buffer.seek(0)

        # 5. Stream the response
        # Using StreamingResponse ensures that even for large files,
        # the server sends data piece-by-piece to the phone.
        return StreamingResponse(
            file_buffer, 
            media_type="application/octet-stream"
        )

    except Exception as e:
        print(f"Download Error: {e}")
        raise HTTPException(status_code=500, detail="Could not retrieve file from Telegram")