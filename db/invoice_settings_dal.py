# db/invoice_settings_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging

from .database import mongo

INVOICE_SETTINGS_COLLECTION = 'invoice_settings'

def get_invoice_settings(tenant_id="default_tenant"):
    """
    Fetches the invoice settings for a given tenant/user.
    """
    try:
        db = mongo.db
        settings = db[INVOICE_SETTINGS_COLLECTION].find_one({"tenant_id": tenant_id})
        if settings:
            return settings
        else:
            # Return default settings if none exist
            return {
                "activeThemeName": "Modern",
                "selectedColor": "#4CAF50",
                "itemTableColumns": {
                    "pricePerItem": True,
                    "quantity": True,
                    "batchNo": False,
                    "expDate": False,
                    "mfgDate": False,
                    "discountPerItem": False,
                    "taxPerItem": True,
                    "hsnSacCode": True,
                    "serialNo": False,
                },
                "customItemColumns": [],
                "bankAccountId": None,
                "termsAndConditionsId": None,
                "signatureImageUrl": None,
                "enableReceiverSignature": False,
                "notesDefault": "Thank you for your business!",
                "tenant_id": tenant_id, # Ensure tenant_id is part of the default structure
                # "created_date": datetime.utcnow() # Default created_date if returning new structure
            }
    except Exception as e:
        logging.error(f"Error fetching invoice settings for tenant {tenant_id}: {e}")
        raise

def save_invoice_settings(settings_data, user="System", tenant_id="default_tenant"):
    """
    Saves or updates the invoice settings for a given tenant/user.
    Uses upsert to create if not exists, or update if exists.
    """
    try:
        db = mongo.db
        now = datetime.utcnow()
        
        # Data that should always be updated or set if new
        update_payload = {
            **settings_data, # Spread the incoming data
            'updated_date': now,
            'updated_user': user,
            'tenant_id': tenant_id
        }

        # Crucially, remove 'created_date' from the main payload for $set
        # It will only be handled by $setOnInsert
        update_payload.pop('created_date', None)
        # Also, remove _id from $set if it's present in settings_data (e.g., from a fetch)
        update_payload.pop('_id', None)


        result = db[INVOICE_SETTINGS_COLLECTION].update_one(
            {"tenant_id": tenant_id}, 
            {
                "$set": update_payload,
                "$setOnInsert": {"created_date": now} # This will only apply if a new document is inserted
            },
            upsert=True
        )

        if result.upserted_id:
            logging.info(f"Invoice settings created for tenant {tenant_id} by {user} with ID: {result.upserted_id}")
            return result.upserted_id
        elif result.matched_count > 0:
            logging.info(f"Invoice settings updated for tenant {tenant_id} by {user}")
            updated_doc = db[INVOICE_SETTINGS_COLLECTION].find_one({"tenant_id": tenant_id}, {"_id": 1})
            return updated_doc['_id'] if updated_doc else None
        else:
            logging.warning(f"Invoice settings save operation had no effect for tenant {tenant_id} (no match, no upsert). This might indicate an issue if an update was expected.")
            # If upsert was true and no document matched, an upserted_id should have been generated.
            # This path implies no document matched and upsert also didn't happen, which is unusual for an empty filter with upsert=True
            # or a filter like {"tenant_id": tenant_id}
            return None
            
    except Exception as e:
        logging.error(f"Error saving invoice settings for tenant {tenant_id}: {e}")
        raise
