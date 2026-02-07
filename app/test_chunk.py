import requests
import os
import uuid

URL = "http://127.0.0.1:8000/api/upload-chunk"
FILE_PATH = "IMG_9587.MOV"
CHUNK_SIZE = 5 * 1024 * 1024  # 5MB

# 🔥 ONE upload session for all chunks
UPLOAD_ID = str(uuid.uuid4())

total_size = os.path.getsize(FILE_PATH)
total_chunks = (total_size + CHUNK_SIZE - 1) // CHUNK_SIZE

with open(FILE_PATH, "rb") as f:
    for chunk_index in range(total_chunks):
        chunk = f.read(CHUNK_SIZE)

        files = {"file": ("chunk", chunk)}
        data = {
            "chunk_index": chunk_index,
            "total_chunks": total_chunks,
            "file_name": "IMG_9605.MOV",
            "upload_id": UPLOAD_ID,  # ⭐ SAME ID for all chunks
        }

        r = requests.post(URL, files=files, data=data)
        print("Chunk", chunk_index, "→", r.json())
