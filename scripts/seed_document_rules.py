# scripts/seed_document_rules.py
from pymongo import MongoClient
from datetime import datetime
from bson.objectid import ObjectId
import os

# --- Configuration ---
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
DB_NAME = os.environ.get("DB_NAME", "your_saas_db") # IMPORTANT: Change this to your actual DB name
# ---------------------

RULES_COLLECTION = 'document_rules'
GLOBAL_DOC_RULES_NAME = "global_document_rules"

def get_default_rules_with_new_ids():
    """Generates default rules with fresh ObjectIds for seeding."""
    return {
        "business_rules": [
            { "_id": ObjectId(), "name": 'Private Company', "description": 'Registered under the Companies Act.', "pan_rules": 'Required for all transactions.', "gstin_rules": 'Required if turnover exceeds threshold.', "tan_rules": 'Required for TDS deduction.', "isLocked": True },
            { "_id": ObjectId(), "name": 'Public Company', "description": 'A company whose shares are traded freely on a stock exchange.', "pan_rules": 'Mandatory for all financial transactions.', "gstin_rules": 'Mandatory.', "tan_rules": 'Mandatory.', "isLocked": False },
            { "_id": ObjectId(), "name": 'Sole Proprietorship', "description": 'An unincorporated business owned and run by one individual.', "pan_rules": 'Owner\'s PAN can be used.', "gstin_rules": 'Required if turnover exceeds threshold.', "tan_rules": 'Required for TDS deduction.', "isLocked": False },
        ],
        "other_rules": [
            { "_id": ObjectId(), "name": 'Aadhaar Card Rules', "description": 'Format: 12-digit numeric\nExample: 1234 5678 9012\nIssued By: UIDAI', "isLocked": True },
            { "_id": ObjectId(), "name": 'Director Identification Number (DIN)', "description": 'Format: 8-digit numeric\nExample: 01234567\nIssued By: Ministry of Corporate Affairs (MCA)', "isLocked": False },
            { "_id": ObjectId(), "name": 'Corporate Identity Number (CIN)', "description": 'Format: 21-digit alphanumeric\nExample: U74899DL2021PTC123456\nIssued By: Registrar of Companies (ROC)', "isLocked": False },
        ]
    }

def seed_data():
    """Connects to the DB and seeds the global document rules."""
    try:
        print(f"Connecting to MongoDB at {MONGO_URI}...")
        client = MongoClient(MONGO_URI)
        db = client[DB_NAME]
        collection = db[RULES_COLLECTION]
        print(f"Connected to database '{DB_NAME}'.")

        # Check if the global document already exists to prevent duplicates
        if collection.count_documents({"name": GLOBAL_DOC_RULES_NAME}) > 0:
            print("Global document rules already exist. Skipping seed.")
            return

        # Create the global document with default rules
        default_rules = get_default_rules_with_new_ids()
        global_doc = {
            "name": GLOBAL_DOC_RULES_NAME,
            "created_date": datetime.utcnow(),
            "updated_date": datetime.utcnow(),
            "updated_user": "System_Seed",
            **default_rules
        }

        result = collection.insert_one(global_doc)
        print(f"Successfully seeded global document rules. Document ID: {result.inserted_id}")

    except Exception as e:
        print(f"An error occurred during seeding: {e}")
    finally:
        if 'client' in locals():
            client.close()
            print("MongoDB connection closed.")

if __name__ == "__main__":
    print("--- Starting Document Rules Seeding Script ---")
    seed_data()
    print("--- Seeding Script Finished ---")
