# db/company_information_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging

# Removed: from .database import mongo
from .activity_log_dal import add_activity

COMPANY_INFO_COLLECTION = 'company_information'
logging.basicConfig(level=logging.INFO)

def get_company_information(db_conn, tenant_id="default_tenant"):
    """
    Fetches the company information document for a specific tenant.
    """
    try:
        company_info = db_conn[COMPANY_INFO_COLLECTION].find_one({"tenant_id": tenant_id})
        if company_info and '_id' in company_info:
            company_info['_id'] = str(company_info['_id'])
        return company_info
    except Exception as e:
        logging.error(f"Error fetching company information for tenant {tenant_id}: {e}")
        raise

def create_or_update_company_information(db_conn, data, user="System", tenant_id="default_tenant"):
    """
    Creates a new company information document or updates the existing one for a specific tenant using upsert.
    Ensures 'created_date' and 'tenant_id' are only set on insert and not in the update '$set' part.
    """
    try:
        now = datetime.utcnow()

        # Prepare update data for $set, excluding _id, created_date, and tenant_id
        update_data_set = {k: v for k, v in data.items() if k not in ['_id', 'created_date', 'tenant_id']}
        update_data_set['updated_date'] = now
        update_data_set['updated_user'] = user

        result = db_conn[COMPANY_INFO_COLLECTION].update_one(
            {"tenant_id": tenant_id},
            {
                "$set": update_data_set,
                "$setOnInsert": {
                    "created_date": now,
                    "tenant_id": tenant_id # tenant_id is set on insert
                    # Add any other fields that should only be set on insert
                }
            },
            upsert=True
        )

        action_details = f"Company Information for tenant '{tenant_id}' "
        action_type = ""
        doc_id = None

        if result.upserted_id:
            doc_id = result.upserted_id
            action_details += f"created. ID: {doc_id}"
            action_type = "CREATE_COMPANY_INFORMATION"
            logging.info(action_details)
        elif result.matched_count > 0:
            updated_doc = db_conn[COMPANY_INFO_COLLECTION].find_one({"tenant_id": tenant_id}, {"_id": 1})
            doc_id = updated_doc['_id'] if updated_doc else None
            if result.modified_count > 0:
                # Log only fields that were actually part of the $set operation, excluding metadata we add
                changed_fields_by_user = {k:v for k,v in update_data_set.items() if k not in ['updated_date', 'updated_user']}
                action_details += f"updated. ID: {doc_id}. Changed fields: {list(changed_fields_by_user.keys())}"
                action_type = "UPDATE_COMPANY_INFORMATION"
                logging.info(action_details)
            else:
                action_details += f"matched but no fields were modified. ID: {doc_id}"
                logging.info(action_details)
        else:
             logging.warning(f"Company information update/insert operation for tenant {tenant_id} had no effect (no match, no upsert).")
             return None

        if action_type and doc_id:
             add_activity(
                action_type=action_type,
                user=user,
                details=action_details,
                document_id=doc_id,
                collection_name=COMPANY_INFO_COLLECTION,
                tenant_id=tenant_id
            )

        return str(doc_id) if doc_id else None

    except Exception as e:
        logging.error(f"Error creating/updating company information for tenant {tenant_id}: {e}")
        raise
