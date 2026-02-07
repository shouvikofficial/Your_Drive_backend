import os
import asyncio
from telethon import TelegramClient
from telethon.sessions import StringSession
from dotenv import load_dotenv

load_dotenv()

# --------------------------------------------------
# Load & validate environment variables
# --------------------------------------------------
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
BOT_TOKEN = os.getenv("BOT_TOKEN")
STRING_SESSION = os.getenv("STRING_SESSION")
CHAT_ID = os.getenv("CHAT_ID")

if not all([API_ID, API_HASH, BOT_TOKEN, STRING_SESSION, CHAT_ID]):
    raise RuntimeError("❌ Missing required environment variables in .env")

API_ID = int(API_ID)
CHAT_ID = int(CHAT_ID)

# --------------------------------------------------
# Initialize Telegram client
# --------------------------------------------------
client = TelegramClient(StringSession(STRING_SESSION), API_ID, API_HASH)

# Prevent multiple simultaneous start() calls
_client_lock = asyncio.Lock()


# --------------------------------------------------
# Ensure connection safely
# --------------------------------------------------
async def init_telethon():
    async with _client_lock:
        if not client.is_connected():
            try:
                await client.start(bot_token=BOT_TOKEN)
            except Exception:
                await asyncio.sleep(2)
                await client.start(bot_token=BOT_TOKEN)


# --------------------------------------------------
# Send merged file to Telegram with retry + timeout
# --------------------------------------------------
async def send_to_telegram(file_path: str, filename: str, retries: int = 3):
    """
    Uploads file to Telegram as DOCUMENT (no compression).
    Supports retry and timeout for big-file reliability.
    """

    await init_telethon()

    last_error = None

    for _ in range(retries):
        try:
            message = await asyncio.wait_for(
                client.send_file(
                    CHAT_ID,
                    file_path,
                    caption=filename,
                    force_document=True,
                ),
                timeout=300,  # ⏱ 5 min timeout for big uploads
            )

            return {
                "file_id": str(message.file.id),
                "message_id": message.id,
                "type": "document",
                "size": os.path.getsize(file_path),
            }

        except Exception as e:
            last_error = e
            await asyncio.sleep(2)

    raise Exception(f"Telegram upload failed after {retries} retries: {last_error}")
