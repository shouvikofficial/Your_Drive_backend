import sqlite3

DB_NAME = "files.db"

def get_connection():
    return sqlite3.connect(DB_NAME)

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # FIX: Added 'thumbnail_id' column
    cur.execute("""
        CREATE TABLE IF NOT EXISTS files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            file_id TEXT NOT NULL,
            type TEXT NOT NULL,
            thumbnail_id TEXT
        )
    """)

    conn.commit()
    conn.close()