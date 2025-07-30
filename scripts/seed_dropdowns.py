# scripts/seed_dropdowns.py
from pymongo import MongoClient
from datetime import datetime
import os

# --- Configuration ---
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.environ.get("DB_NAME", "your_saas_db")
# ---------------------

DROPDOWNS_COLLECTION = 'dropdown'

# Add your application's essential, default dropdown values here.
# This data is necessary for the app to function correctly on first launch.
# For example:
# {
#     "type": "gst_type",
#     "value": "regular",
#     "label": "Regular",
#     ...
# }
DEFAULT_DROPDOWNS = [
    # This list is intentionally empty. Add your default dropdown items here.
]

def seed_data():
    """Connects to the DB and seeds the global dropdown values."""
    try:
        if not DEFAULT_DROPDOWNS:
            print("No default dropdowns to seed. Exiting.")
            return

        print(f"Connecting to MongoDB at {MONGO_URI}...")
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[DROPDOWNS_COLLECTION]
        print(f"Connected to database '{DB_NAME}'.")

        # Check for existing data to prevent duplicates
        # This checks if the first item's type already exists.
        first_item_type = DEFAULT_DROPDOWNS[0].get("type")
        if first_item_type and collection.count_documents({"type": first_item_type}) > 0:
            print(f"Found existing dropdowns of type '{first_item_type}'. Skipping seed.")
            return

        print("Seeding default dropdown values...")
        collection.insert_many(DEFAULT_DROPDOWNS)
        print(f"Successfully seeded {len(DEFAULT_DROPDOWNS)} dropdown items.")

    except Exception as e:
        print(f"An error occurred during seeding: {e}")
    finally:
        if 'client' in locals():
            client.close()
            print("MongoDB connection closed.")

if __name__ == "__main__":
    print("--- Starting Dropdown Seeding Script ---")
    seed_data()
    print("--- Seeding Script Finished ---")
