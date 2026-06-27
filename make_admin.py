from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

db = MongoClient(os.getenv("MONGO_URI"))["voting_system"]

result = db.users.update_one(
    {"email": "rjdeepashree19@gmail.com"},
    {"$set": {"role": "admin"}}
)

if result.modified_count:
    print("✅ Admin role set successfully!")
else:
    print("❌ User not found or already admin.")