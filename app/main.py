import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ROUTERS
from app.upload import router as upload_router
from app.download import router as download_router
from app.delete import router as delete_router

# TELEGRAM CLIENT
from app.telegram_bot import client, BOT_TOKEN


# --------------------------------------------------
# LIFESPAN: Startup & Shutdown control
# --------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Runs once at startup and once at shutdown.
    """

    # Ensure temp directory exists
    os.makedirs("temp_chunks", exist_ok=True)

    # ---- STARTUP ----
    try:
        if not client.is_connected():
            await client.start(bot_token=BOT_TOKEN)

        print("🚀 Telegram Drive Worker ONLINE (MTProto connected)")

    except Exception as e:
        # Crash server if Telegram not connected (important for production)
        raise RuntimeError(f"❌ Failed to connect Telethon: {e}")

    yield  # -------- SERVER RUNNING --------

    # ---- SHUTDOWN ----
    try:
        await client.disconnect()
        print("🛑 Server shutdown: Telethon disconnected.")
    except Exception:
        pass


# --------------------------------------------------
# FASTAPI APP
# --------------------------------------------------
app = FastAPI(
    title="Telegram Drive Worker",
    lifespan=lifespan
)


# --------------------------------------------------
# CORS CONFIGURATION
# --------------------------------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 🔧 Change to your domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --------------------------------------------------
# ROUTES
# --------------------------------------------------
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
        "telethon_connected": client.is_connected(),
    }
