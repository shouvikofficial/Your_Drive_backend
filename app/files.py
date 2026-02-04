from fastapi import APIRouter, Depends, Header, Request, HTTPException
from jose import jwt, JWTError
from app.database import get_connection

router = APIRouter()

SECRET = "SUPER_SECRET_KEY"
ALGORITHM = "HS256"

# --------------------------------------------------
# AUTH: GET USER ID FROM JWT
# --------------------------------------------------
def get_user_id(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid authorization header")

    token = authorization.replace("Bearer ", "")

    try:
        payload = jwt.decode(token, SECRET, algorithms=[ALGORITHM])
        return payload["user_id"]
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# --------------------------------------------------
# GET FILES (USER ISOLATED)
# --------------------------------------------------
@router.get("/files")
def get_files(
    request: Request,
    user_id: int = Depends(get_user_id)
):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        """
        SELECT id, name, file_id, type, thumbnail_id
        FROM files
        WHERE user_id = ?
        ORDER BY id DESC
        """,
        (user_id,)
    )

    rows = cur.fetchall()
    conn.close()

    base_url = str(request.base_url).rstrip("/")

    results = []
    for r in rows:
        file_id = r[2]
        file_type = r[3]
        thumb_id = r[4]

        thumbnail_url = None
        if thumb_id:
            thumbnail_url = f"{base_url}/image/{thumb_id}"
        elif file_type == "image":
            thumbnail_url = f"{base_url}/image/{file_id}"

        results.append({
            "id": r[0],
            "name": r[1],
            "type": file_type,
            "url": f"{base_url}/image/{file_id}",
            "thumbnail_url": thumbnail_url
        })

    return results
