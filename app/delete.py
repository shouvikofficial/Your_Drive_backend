from fastapi import APIRouter, HTTPException
from telethon.errors import MessageIdInvalidError
from app.telegram_bot import client, init_telethon, CHAT_ID

router = APIRouter()

@router.delete("/delete/{message_id}")
async def delete_file(message_id: int):
    """
    Deletes the file from the Telegram Channel.
    
    ✅ SMART FIX:
    If the file is already gone from Telegram (404), we return 'success' anyway.
    This allows the Flutter app to remove the 'ghost file' from the database.
    """
    try:
        # 1. Ensure connected
        await init_telethon()

        # 2. Try to delete
        try:
            # delete_messages returns the list of affected messages
            result = await client.delete_messages(CHAT_ID, [message_id])
            
            # If result is empty, it means the message didn't exist
            if not result:
                print(f"⚠️ Message {message_id} was already gone (Ghost File). Treating as success.")

        except MessageIdInvalidError:
            print(f"⚠️ Message {message_id} ID is invalid or already deleted. Treating as success.")
        
        except Exception as e:
            print(f"⚠️ Telegram Delete Warning: {e}")
            # We continue even if Telegram complains, so DB can be cleaned up.

        # 3. Always return success so Supabase deletes the row
        return {
            "success": True, 
            "message": f"Message {message_id} processed for deletion."
        }

    except Exception as e:
        print(f"❌ Critical Delete Error: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Server error during delete: {str(e)}",
        )