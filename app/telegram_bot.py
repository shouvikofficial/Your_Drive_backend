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
CHAT_ID = int(CHAT_ID)

# ============================================================
# 🚀 TELEGRAM CLIENT (STABLE CONFIG)
# ============================================================
client = TelegramClient(
    StringSession(STRING_SESSION),
    API_ID,
    API_HASH,
    timeout=120,          # ⏱ prevent timeout on large uploads
    request_retries=5,    # 🔁 auto retry network errors
)

# ⭐ GLOBAL LOCK → ensures only ONE send_file runs at a time
telegram_upload_lock = asyncio.Lock()

# ============================================================
# 🔌 CONNECTION HELPER
# ============================================================
async def init_telethon():
    """
    Ensure Telegram client is connected.
    Works instantly with StringSession (no OTP needed).
    """
    if not client.is_connected():
        await client.start()


# ============================================================
# 📤 SAFE TELEGRAM UPLOAD (QUEUE + RETRY)
# ============================================================
async def send_to_telegram(file_path: str, filename: str):
    """
    Sends a file to Telegram safely.

    Fixes:
    - Parallel upload timeout
    - Telegram rate-limit
    - Network instability
    """

    await init_telethon()

    # ⭐ SERIALIZE Telegram uploads (VERY IMPORTANT)
    async with telegram_upload_lock:

        # 🔁 retry up to 3 times
        for attempt in range(3):
            try:
                message = await client.send_file(
                    CHAT_ID,
                    file_path,
                    caption=f"📁 File: {filename}",
                    force_document=True,  # prevent compression
                )

                return message.id  # success

            except Exception as e:
                print(f"⚠️ Telegram upload retry {attempt + 1}/3 → {e}")
                await asyncio.sleep(2)

        # ❌ failed after retries
        print("❌ Telegram upload failed after 3 retries")
        return None


# ============================================================
# 🧪 LOCAL TEST (OPTIONAL)
# ============================================================
# if __name__ == "__main__":
#     async def test():
#         await init_telethon()
#         print("✅ Telegram connected successfully")
#
#     asyncio.run(test())
