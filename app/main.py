from fastapi import FastAPI

# ROUTERS
from app.upload import router as upload_router
from app.download import router as download_router

app = FastAPI(title="Your Drive Telegram Worker")

# --------------------------------------------------
# REGISTER ROUTES
# --------------------------------------------------
app.include_router(upload_router)
app.include_router(download_router)

# --------------------------------------------------
# HEALTH CHECK
# --------------------------------------------------
@app.get("/")
def health():
    return {"status": "ok"}
