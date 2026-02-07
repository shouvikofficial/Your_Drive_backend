import os
import asyncio
from telethon import TelegramClient
from dotenv import load_dotenv

load_dotenv()

# 1. Load Env Vars
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
CHAT_ID = os.getenv("CHAT_ID")

if not all([API_ID, API_HASH, CHAT_ID]):
    raise RuntimeError("❌ Missing API_ID, API_HASH, or CHAT_ID in .env")

API_ID = int(API_ID)
CHAT_ID = int(CHAT_ID)

# 2. Initialize Client
# ✅ CRITICAL FIX: Changed name to 'session_v2' to force a fresh login file.
client = TelegramClient('session_v2', API_ID, API_HASH)

# 3. Connection Helper
async def init_telethon():
    if not client.is_connected():
        await client.start()

# 4. Upload Helper
async def send_to_telegram(file_path: str, filename: str, retries: int = 3):
    await init_telethon()
    # (This function is kept for backward compatibility if needed)
    pass