import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ROUTERS
from app.upload import router as upload_router
from app.download import router as download_router
from app.delete import router as delete_router

# TELETHON CLIENT (Imported from your bot file)
from app.telegram_bot import client, BOT_TOKEN

# --------------------------------------------------
# LIFESPAN: Handles Startup & Shutdown
# --------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Logic inside this block runs ONCE when the server starts 
    and ONCE when it shuts down.
    """
    # 1. Startup Logic
    os.makedirs("temp_chunks", exist_ok=True)
    
    # Connect Telethon to MTProto using your StringSession
    if not client.is_connected():
        # Using start() ensures the client is authorized and ready
        await client.start(bot_token=BOT_TOKEN)
    
    print("🚀 Telegram Drive Worker is Online and Connected to MTProto!")
    
    yield  # --- Server is now running and accepting requests ---
    
    # 2. Shutdown Logic
    await client.disconnect()
    print("🛑 Server shutting down: Telethon disconnected.")

app = FastAPI(
    title="Telegram Drive Worker",
    lifespan=lifespan
)

# --------------------------------------------------
# CORS CONFIGURATION
# --------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, replace with your specific domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# REGISTER ROUTES
# --------------------------------------------------
# We use a prefix to keep the API organized and versionable
app.include_router(upload_router, prefix="/api", tags=["Storage"])
app.include_router(download_router, prefix="/api", tags=["Storage"])
app.include_router(delete_router, prefix="/api", tags=["Storage"])

# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------
@app.get("/", tags=["Health"])
async def health():
    return {
        "status": "online",
        "worker": "Telegram Drive Engine",
        "storage": "Unlimited (via MTProto)",
        "telethon_connected": client.is_connected()
    }