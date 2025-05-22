# db/gst_rate_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging

from .database import mongo
# Import functions from ca_tax_dal to manage related CA tax entries
from .ca_tax_dal import manage_ca_tax_entries_for_gst_rate, delete_ca_tax_entries_by_original_id

GST_RATE_COLLECTION = 'gst_rates'

def create_gst_rate(gst_data, user="System"):
    """
    Creates a new GST rate document in the database and manages related ca_tax entries.
    Calculates SGST and CGST if taxRate is provided.
    """
    try:
        db = mongo.db
        now = datetime.utcnow()

        gst_data['created_date'] = now
        gst_data['updated_date'] = now
        gst_data['updated_user'] = user
        gst_data.pop('_id', None)

        try:
            rate = float(gst_data.get('taxRate', 0))
        except (ValueError, TypeError):
            logging.warning("Invalid taxRate value, defaulting to 0.")
            rate = 0

        gst_data['taxRate'] = rate
        gst_data['igstRate'] = rate
        gst_data['sgstRate'] = rate / 2
        gst_data['cgstRate'] = rate / 2

        # Use a more descriptive default name if taxName is not provided
        gst_data['taxName'] = gst_data.get('taxName', f"GST {rate}% ({gst_data.get('head', 'General')})")
        gst_data['head'] = gst_data.get('head', 'General')


        result = db[GST_RATE_COLLECTION].insert_one(gst_data)
        inserted_id = result.inserted_id
        logging.info(f"GST rate '{gst_data.get('taxName')}' created with ID: {inserted_id} by {user}")

        if inserted_id:
            # Fetch the full document to pass to ca_tax management
            # This ensures all calculated fields (sgstRate, cgstRate, igstRate) are present
            created_gst_rate_doc = db[GST_RATE_COLLECTION].find_one({"_id": inserted_id})
            if created_gst_rate_doc:
                manage_ca_tax_entries_for_gst_rate(created_gst_rate_doc, user)

        return inserted_id
    except Exception as e:
        logging.error(f"Error creating GST rate: {e}")
        raise

def get_gst_rate_by_id(gst_id):
    """
    Fetches a single GST rate by its ObjectId.
    """
    try:
        db = mongo.db
        return db[GST_RATE_COLLECTION].find_one({"_id": ObjectId(gst_id)})
    except Exception as e:
        logging.error(f"Error fetching GST rate by ID {gst_id}: {e}")
        raise

def get_all_gst_rates(page=1, limit=25, filters=None):
    """
    Fetches a paginated list of GST rates, optionally filtered.
    """
    try:
        db = mongo.db
        query = filters if filters else {}
        skip = (page - 1) * limit if limit > 0 else 0

        if limit > 0:
            gst_rates_cursor = db[GST_RATE_COLLECTION].find(query).skip(skip).limit(limit)
        else:
            gst_rates_cursor = db[GST_RATE_COLLECTION].find(query).skip(skip)

        gst_rate_list = list(gst_rates_cursor)
        total_items = db[GST_RATE_COLLECTION].count_documents(query)
        return gst_rate_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all GST rates: {e}")
        raise

def update_gst_rate(gst_id, update_data, user="System"):
    """
    Updates an existing GST rate and its related ca_tax entries.
    Recalculates SGST, CGST, IGST if taxRate is updated.
    """
    try:
        db = mongo.db
        now = datetime.utcnow()
        original_id_obj = ObjectId(gst_id) # Convert string ID to ObjectId for querying
        update_data.pop('_id', None) # Don't allow updating the _id

        update_payload_set = {
            **update_data,
            "updated_date": now,
            "updated_user": user
        }

        if 'taxRate' in update_payload_set:
            try:
                rate = float(update_payload_set['taxRate'])
            except (ValueError, TypeError):
                logging.warning(f"Invalid taxRate value for update, defaulting to 0.")
                rate = 0

            update_payload_set['taxRate'] = rate
            update_payload_set['igstRate'] = rate
            update_payload_set['sgstRate'] = rate / 2
            update_payload_set['cgstRate'] = rate / 2
            # Update taxName if it's based on rate and not explicitly provided for update,
            # or if the old name was the default generated one.
            current_head = update_payload_set.get('head', 'General') # Get head from update or assume General
            if 'taxName' not in update_data or update_data.get('taxName', f"GST {rate}% ({current_head})") == f"GST {rate}% ({current_head})":
                 update_payload_set['taxName'] = f"GST {rate}% ({current_head})"

        result = db[GST_RATE_COLLECTION].update_one(
            {"_id": original_id_obj},
            {"$set": update_payload_set}
        )

        if result.matched_count > 0:
            logging.info(f"GST rate {gst_id} updated by {user}")
            # Fetch the full updated document to pass to ca_tax management
            updated_gst_rate_doc = db[GST_RATE_COLLECTION].find_one({"_id": original_id_obj})
            if updated_gst_rate_doc:
                manage_ca_tax_entries_for_gst_rate(updated_gst_rate_doc, user)

        return result.matched_count
    except Exception as e:
        logging.error(f"Error updating GST rate {gst_id}: {e}")
        raise

def delete_gst_rate_by_id(gst_id):
    """
    Deletes a GST rate by its ObjectId and its related ca_tax entries.
    """
    try:
        db = mongo.db
        original_id_obj = ObjectId(gst_id) # Convert string ID to ObjectId
        result = db[GST_RATE_COLLECTION].delete_one({"_id": original_id_obj})
        if result.deleted_count > 0:
            logging.info(f"GST rate {gst_id} deleted.")
            # Also delete related ca_tax entries
            delete_ca_tax_entries_by_original_id(original_id_obj) # Pass ObjectId
        return result.deleted_count
    except Exception as e:
        logging.error(f"Error deleting GST rate {gst_id}: {e}")
        raise

# GST TDS Setting functions remain the same as they modify company_information
def get_gst_tds_setting(tenant_id="default_tenant"):
    from .company_information_dal import get_company_information
    company_info = get_company_information()
    return company_info.get("gstTdsApplicable", "No") if company_info else "No"

def update_gst_tds_setting(is_applicable, user="System", tenant_id="default_tenant"):
    from .company_information_dal import COMPANY_INFO_COLLECTION as CI_COLLECTION
    try:
        db = mongo.db
        now = datetime.utcnow()
        result = db[CI_COLLECTION].update_one(
            {"tenant_id": tenant_id},
            {
                "$set": {
                    "gstTdsApplicable": "Yes" if is_applicable else "No",
                    "updated_date": now,
                    "updated_user": user
                },
                "$setOnInsert": {"created_date": now}
            },
            upsert=True
        )
        return result.modified_count > 0 or result.upserted_id is not None
    except Exception as e:
        logging.error(f"Error updating GST TDS setting: {e}")
        raise
