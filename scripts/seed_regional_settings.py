# scripts/seed_regional_settings.py
from pymongo import MongoClient
from datetime import datetime
import os

# --- Configuration ---
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.environ.get("DB_NAME", "your_saas_db") # IMPORTANT: Change this to your actual DB name
# ---------------------

SETTINGS_COLLECTION = 'regional_settings'

# Sample data to seed
DEFAULT_REGIONS = [
    {
        "regionName": "United Arab Emirates",
        "states": [],
        "currency": "AED",
        "countryCode": "+971",
        "flag": "🇦🇪",
        "currencySymbol": "د.إ",
        "isDefaultBase": True, # Set one as the default
        "isLocked": True,
        "created_date": datetime.utcnow(),
        "updated_date": datetime.utcnow(),
        "updated_user": "System_Seed"
    },
    {
        "regionName": "India",
        "states": [],
        "currency": "INR",
        "countryCode": "+91",
        "flag": "🇮🇳",
        "currencySymbol": "₹",
        "isDefaultBase": False,
        "isLocked": False,
        "created_date": datetime.utcnow(),
        "updated_date": datetime.utcnow(),
        "updated_user": "System_Seed"
    },
    {
        "regionName": "United States",
        "states": [],
        "currency": "USD",
        "countryCode": "+1",
        "flag": "🇺🇸",
        "currencySymbol": "$",
        "isDefaultBase": False,
        "isLocked": False,
        "created_date": datetime.utcnow(),
        "updated_date": datetime.utcnow(),
        "updated_user": "System_Seed"
    }
]

def seed_data():
    """Connects to the DB and seeds the global regional settings."""
    try:
        print(f"Connecting to MongoDB at {MONGO_URI}...")
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[SETTINGS_COLLECTION]
        print(f"Connected to database '{DB_NAME}'.")

        # Check for existing data to prevent duplicates
        existing_regions_count = collection.count_documents({})
        if existing_regions_count > 0:
            print(f"Found {existing_regions_count} regions. Skipping seed.")
            return

        print("Seeding default regional settings...")
        collection.insert_many(DEFAULT_REGIONS)
        print(f"Successfully seeded {len(DEFAULT_REGIONS)} regional settings.")

    except Exception as e:
        print(f"An error occurred during seeding: {e}")
    finally:
        if 'client' in locals():
            client.close()
            print("MongoDB connection closed.")

if __name__ == "__main__":
    print("--- Starting Regional Settings Seeding Script ---")
    seed_data()
    print("--- Seeding Script Finished ---")
