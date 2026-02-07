import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()

# 1. Load Env Vars
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
CHAT_ID = os.getenv("CHAT_ID")
# ✅ FETCH THE STRING SESSION FROM RENDER
STRING_SESSION = os.getenv("STRING_SESSION") 

if not all([API_ID, API_HASH, CHAT_ID, STRING_SESSION]):
    raise RuntimeError("❌ Missing API_ID, API_HASH, CHAT_ID, or STRING_SESSION in environment")

API_ID = int(API_ID)
CHAT_ID = int(CHAT_ID)

# 2. Initialize Client
# ✅ FIX: Using StringSession instead of 'session_v2' filename
client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

# 3. Connection Helper
async def init_telethon():
    if not client.is_connected():
        # Using .start() with StringSession works instantly without a phone prompt
        await client.start()

# 4. Upload Helper
async def send_to_telegram(file_path: str, filename: str):
    """
    Sends a file to your Telegram storage (CHAT_ID).
    """
    try:
        await init_telethon()
        
        # Upload the file to the specific chat
        message = await client.send_file(
            CHAT_ID, 
            file_path, 
            caption=f"📁 File: {filename}",
            force_document=True  # Ensures it doesn't compress images
        )
        
        # Return the message ID or file ID for your Supabase database
        return message.id
        
    except Exception as e:
        print(f"❌ Telegram Upload Error: {e}")
        return None

# To test the connection locally, you can run:
# if __name__ == "__main__":
#     asyncio.run(init_telethon())
#     print("✅ Successfully connected to Telegram using String Session!")