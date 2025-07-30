# scripts/seed_industries.py
from pymongo import MongoClient
from datetime import datetime
import os

# --- Configuration ---
# Make sure these match your environment
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.environ.get("DB_NAME", "your_saas_db")
# ---------------------

# The name of the collection to seed
COLLECTION_NAME = 'industry_classifications'

# Sample data adapted from your file
DEFAULT_INDUSTRIES = [
    {
        "industry": "Information Technology",
        "natureOfBusiness": "Software Development & Services",
        "code": "IT-001",
        "isLocked": False,
        "created_date": datetime.utcnow(),
        "updated_user": "System_Seed"
    },
    {
        "industry": "Healthcare",
        "natureOfBusiness": "Hospitals and Clinics",
        "code": "HC-001",
        "isLocked": False,
        "created_date": datetime.utcnow(),
        "updated_user": "System_Seed"
    },
    {
        "industry": "Finance",
        "natureOfBusiness": "Banking and Financial Services",
        "code": "FIN-001",
        "isLocked": True,
        "created_date": datetime.utcnow(),
        "updated_user": "System_Seed"
    },
    {
        "industry": "Retail",
        "natureOfBusiness": "E-commerce and Online Shopping",
        "code": "RET-001",
        "isLocked": False,
        "created_date": datetime.utcnow(),
        "updated_user": "System_Seed"
    },
    {
        "industry": "Manufacturing",
        "natureOfBusiness": "Automotive Production",
        "code": "MAN-001",
        "isLocked": False,
        "created_date": datetime.utcnow(),
        "updated_user": "System_Seed"
    }
]

def seed_data():
    """Connects to the DB and seeds the global industry classifications."""
    try:
        print(f"Connecting to MongoDB at {MONGO_URI}...")
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[COLLECTION_NAME]
        print(f"Connected to database '{DB_NAME}'.")

        # Check for existing data to prevent duplicates
        if collection.count_documents({}) > 0:
            print(f"Collection '{COLLECTION_NAME}' already contains data. Skipping seed.")
            return

        print(f"Seeding default data into '{COLLECTION_NAME}'...")
        # FIX: Insert each classification as a separate document
        collection.insert_many(DEFAULT_INDUSTRIES)
        print(f"Successfully seeded {len(DEFAULT_INDUSTRIES)} industry classifications.")

    except Exception as e:
        print(f"An error occurred during seeding: {e}")
    finally:
        if 'client' in locals():
            client.close()
            print("MongoDB connection closed.")

if __name__ == "__main__":
    print("--- Starting Industry Classification Seeding Script ---")
    seed_data()
    print("--- Seeding Script Finished ---")
