import os
from dotenv import load_dotenv

load_dotenv()

print(os.getenv("BOT_TOKEN"))
print(os.getenv("CHAT_ID"))
