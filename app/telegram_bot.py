import os
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()

# 1. CREDENTIALS: These are now hardcoded or pulled from Render Env
API_ID = 34748224
API_HASH = '4a5b76ba2a82d88ce0368c7d29cde72a'
BOT_TOKEN = os.getenv("BOT_TOKEN")
STRING_SESSION = os.getenv("STRING_SESSION") 
CHAT_ID = int(os.getenv("CHAT_ID"))

# 2. INITIALIZE CLIENT: Using StringSession for Render persistence
# This is your "Super Highway" to Telegram
client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

async def init_telethon():
    """Ensures the bot is connected before we try to send anything."""
    if not client.is_connected():
        await client.start(bot_token=BOT_TOKEN)

async def send_to_telegram(file_path: str, filename: str):
    """
    Sends the merged file to Telegram as a DOCUMENT.
    Telethon handles files up to 2GB automatically.
    """
    await init_telethon()

    # We send as a document to ensure original quality (no compression)
    # force_document=True is the same as sendDocument in the old API
    message = await client.send_file(
        CHAT_ID,
        file_path,
        caption=filename,
        force_document=True 
    )

    # Return structured data for your Supabase Database
    return {
        "file_id": str(message.file.id), # The ID needed for downloading
        "message_id": message.id,       # The ID needed for deleting
        "type": "document",
        "size": os.path.getsize(file_path)
    }