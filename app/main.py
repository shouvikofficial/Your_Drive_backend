import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from telethon.errors import AuthKeyDuplicatedError

# ✅ IMPORTS
from app.upload import router as upload_router
from app.download import router as download_router
from app.delete import router as delete_router 

# TELEGRAM CLIENT (Now using StringSession internally)
from app.telegram_bot import client

# 📝 FILE LOGGING (for MCP observability)
try:
    from mcp_server.setup_logging import configure_logging
    configure_logging()
except ImportError:
    pass  # MCP server not installed, skip file logging

# --------------------------------------------------
# LIFESPAN
# --------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure temp directory exists
    os.makedirs("temp_uploads", exist_ok=True)

    # ---- STARTUP ----
    print("🔄 Connecting to Telegram via String Session...")
    try:
        # ✅ FIX: No more session files. StringSession connects instantly.
        if not client.is_connected():
            await client.start()
        
        print("🚀 Telegram Drive Worker ONLINE (Connected)")

    except AuthKeyDuplicatedError:
        # This usually only happens if the StringSession is used by another 
        # active script or has been revoked.
        print("\n❌ CRITICAL ERROR: String Session Invalid or Revoked.")
        raise RuntimeError("Session Invalid")

    except Exception as e:
        print(f"❌ Connection Error: {e}")
        # Don't let the app start if the connection fails
        raise RuntimeError(f"Connection Failed: {e}")

    yield  # Server runs here

    # ---- SHUTDOWN ----
    try:
        if client.is_connected():
            await client.disconnect()
            print("🛑 Telethon disconnected.")
    except Exception:
        pass


# --------------------------------------------------
# FASTAPI APP
# --------------------------------------------------
app = FastAPI(
    title="Telegram Drive Worker",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --------------------------------------------------
# ROUTES
# --------------------------------------------------
app.include_router(upload_router, prefix="/api", tags=["Upload"])
app.include_router(download_router, prefix="/api", tags=["Download"])
app.include_router(delete_router, prefix="/api", tags=["Delete"])

@app.get("/", tags=["Health"])
async def health():
    # This helps Render's Health Check and UptimeRobot confirm connectivity
    return {
        "status": "online", 
        "connected": client.is_connected(),
        "info": "Your Drive Backend is Ready"
    }