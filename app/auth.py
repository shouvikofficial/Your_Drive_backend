from fastapi import APIRouter, HTTPException
from passlib.hash import bcrypt
from jose import jwt
from pydantic import BaseModel
from app.database import get_connection

router = APIRouter()

SECRET = "SUPER_SECRET_KEY"
ALGORITHM = "HS256"


# ----------------------------
# REQUEST SCHEMA (🔥 REQUIRED)
# ----------------------------
class AuthRequest(BaseModel):
    email: str
    password: str


# ----------------------------
# REGISTER
# ----------------------------
@router.post("/register")
def register(data: AuthRequest):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id FROM users WHERE email=?",
        (data.email,)
    )

    if cur.fetchone():
        raise HTTPException(status_code=400, detail="Email already registered")

    password_hash = bcrypt.hash(data.password)

    cur.execute(
        "INSERT INTO users (email, password_hash) VALUES (?, ?)",
        (data.email, password_hash)
    )

    conn.commit()
    conn.close()

    return {"message": "Account created successfully"}


# ----------------------------
# LOGIN
# ----------------------------
@router.post("/login")
def login(data: AuthRequest):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(
        "SELECT id, password_hash FROM users WHERE email=?",
        (data.email,)
    )

    user = cur.fetchone()
    conn.close()

    if not user or not bcrypt.verify(data.password, user[1]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = jwt.encode(
        {"user_id": user[0]},
        SECRET,
        algorithm=ALGORITHM
    )

    return {"token": token}
