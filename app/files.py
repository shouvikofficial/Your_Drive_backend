from fastapi import APIRouter
from app.database import get_files

router = APIRouter()

@router.get("/files")
def list_files():
    return [
        {
            "id": f[0],
            "name": f[1],
            "type": f[2],
            "url": f"http://localhost:8000/uploads/{f[1]}"
        }
        for f in get_files()
    ]
