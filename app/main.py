import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from telethon.errors import AuthKeyDuplicatedError

# ✅ IMPORTS (Assumes delete.py is inside the 'app' folder like upload.py)
from app.upload import router as upload_router
from app.download import router as download_router
from app.delete import router as delete_router  # 👈 UNCOMMENTED THIS

# TELEGRAM CLIENT
from app.telegram_bot import client

# --------------------------------------------------
# LIFESPAN
# --------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure temp directory exists
    os.makedirs("temp_uploads", exist_ok=True)

    # ---- STARTUP ----
    print("🔄 Connecting to Telegram...")
    try:
        # Connects using the session file defined in telegram_bot.py
        if not client.is_connected():
            await client.start()
        
        print("🚀 Telegram Drive Worker ONLINE (Connected)")

    except AuthKeyDuplicatedError:
        print("\n❌ CRITICAL ERROR: Session File Corrupted/Banned.")
        print("👉 The app will crash. Please restart to generate a new session.\n")
        raise RuntimeError("Session Corrupted")

    except Exception as e:
        print(f"❌ Connection Error: {e}")
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
app.include_router(delete_router, prefix="/api", tags=["Delete"]) # 👈 UNCOMMENTED THIS

@app.get("/", tags=["Health"])
async def health():
    return {"status": "online", "connected": client.is_connected()}