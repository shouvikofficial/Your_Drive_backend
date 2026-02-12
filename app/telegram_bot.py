import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()

# ============================================================
# 🔐 LOAD ENV VARIABLES
# ============================================================
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
CHAT_ID = os.getenv("CHAT_ID")
STRING_SESSION = os.getenv("STRING_SESSION")

if not all([API_ID, API_HASH, CHAT_ID, STRING_SESSION]):
    raise RuntimeError("❌ Missing API_ID, API_HASH, CHAT_ID, or STRING_SESSION in environment")

API_ID = int(API_ID)
try:
    CHAT_ID = int(CHAT_ID)
except ValueError:
    print(f"⚠️ Warning: CHAT_ID '{CHAT_ID}' is not an integer. Ensure it is correct.")

# ============================================================
# 🚀 TELEGRAM CLIENT (GLOBAL)
# ============================================================
client = TelegramClient(
    StringSession(STRING_SESSION),
    API_ID,
    API_HASH,
    request_retries=5,
    connection_retries=5,
    retry_delay=1,
    auto_reconnect=True
)

# ⭐ GLOBAL LOCK → ensures only ONE upload happens at a time
# This prevents "FloodWait" errors from Telegram
telegram_upload_lock = asyncio.Lock()


# ============================================================
# 🔌 CONNECTION HELPER
# ============================================================
async def init_telethon():
    """
    Ensure Telegram client is connected and authorized.
    """
    if not client.is_connected():
        await client.connect()
    
    if not await client.is_user_authorized():
        raise RuntimeError("❌ Session invalid or not authorized. Please renew STRING_SESSION.")


# ============================================================
# 📤 SAFE TELEGRAM UPLOAD (QUEUE + EXPONENTIAL BACKOFF)
# ============================================================
async def send_to_telegram(file_path: str, filename: str):
    """
    Sends a file to Telegram safely.
    Returns the full Message object on success, None on failure.
    """
    
    await init_telethon()

    # ⭐ SERIALIZE Telegram uploads (Crucial for stability)
    async with telegram_upload_lock:
        
        # 🔁 Retry loop (3 attempts)
        for attempt in range(1, 4):
            try:
                # Optional: Progress callback (useful for logs if needed)
                def progress_callback(current, total):
                    pass 

                message = await client.send_file(
                    CHAT_ID,
                    file_path,
                    caption=str(filename),
                    force_document=True,  # 📦 Send as file, not media compression
                    progress_callback=progress_callback
                )

                # ✅ SUCCESS: Return full message object
                return message  

            except Exception as e:
                wait_time = 2 ** attempt  # Exponential backoff: 2s, 4s, 8s
                print(f"⚠️ Telegram upload retry {attempt}/3 failed: {e}")
                print(f"⏳ Waiting {wait_time}s before retry...")
                await asyncio.sleep(wait_time)

        # ❌ FAILED after all retries
        print(f"❌ Critical: Telegram upload failed for {filename} after 3 attempts")
        return None


# ============================================================
# 🧪 LOCAL TEST (Uncomment to test connection)
# ============================================================
# if __name__ == "__main__":
#     async def test():
#         await init_telethon()
#         print(f"✅ Telegram connected as: {(await client.get_me()).first_name}")
#     asyncio.run(test())