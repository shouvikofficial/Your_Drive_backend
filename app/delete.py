from fastapi import APIRouter, HTTPException
from app.telegram_bot import client, init_telethon, CHAT_ID

router = APIRouter()

@router.delete("/delete/{message_id}")
async def delete_file(message_id: int):
    """
    Deletes the file from the Telegram Channel using its message_id.
    Note: Supabase deletion should be handled by your Flutter app logic.
    """
    try:
        # 1. Ensure the Telethon client is connected
        await init_telethon()

        # 2. Use Telethon's delete_messages method
        # This is much faster than making a new HTTP request every time
        success = await client.delete_messages(CHAT_ID, message_id)

        if not success:
            raise Exception("Telegram could not find or delete the message.")

        return {"success": True, "message": f"Message {message_id} deleted from storage."}

    except Exception as e:
        print(f"Delete Error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Telegram delete failed: {str(e)}",
        )