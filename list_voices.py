import os
import requests
from dotenv import load_dotenv

load_dotenv()

resp = requests.get(
    "https://api.cartesia.ai/voices",
    headers={
        "X-API-Key": os.getenv("CARTESIA_API_KEY"),
        "Cartesia-Version": "2024-06-10",
    }
)

for voice in resp.json():
    print(f"{voice['id']}  —  {voice['name']}")