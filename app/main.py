from fastapi import FastAPI
from app.upload import router as upload_router

app = FastAPI(title="Your Drive Telegram Worker")

# Register routes
app.include_router(upload_router)

@app.get("/")
def health():
    return {"status": "ok"}
