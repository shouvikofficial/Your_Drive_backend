import asyncio
from fastapi import APIRouter, HTTPException
from app.telegram_bot import client, init_telethon, CHAT_ID

router = APIRouter()


@router.delete("/delete/{message_id}")
async def delete_file(message_id: int):
    """
    Deletes a stored file from Telegram channel using message_id.
    Safe for production with timeout & validation.
    """

    try:
        # --------------------------------------------------
        # Ensure Telethon connection
        # --------------------------------------------------
        await init_telethon()

        # --------------------------------------------------
        # Attempt delete with timeout protection
        # --------------------------------------------------
        deleted = await asyncio.wait_for(
            client.delete_messages(CHAT_ID, message_id),
            timeout=20,
        )

        # Telethon returns list of deleted messages
        if not deleted:
            raise HTTPException(
                status_code=404,
                detail="Message not found or already deleted.",
            )

        return {
            "success": True,
            "message": f"Message {message_id} deleted from Telegram storage.",
        }

    except HTTPException:
        raise

    except Exception as e:
        print(f"Delete Error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Telegram delete failed: {str(e)}",
        )
