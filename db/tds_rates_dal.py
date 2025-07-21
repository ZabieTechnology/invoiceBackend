# db/tds_rates_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging
import re

# Assuming a similar activity log utility exists
# from .activity_log_dal import add_activity

TDS_RATES_COLLECTION = 'tds_rates'
logging.basicConfig(level=logging.INFO)

def _parse_tds_data(tds_data):
    """Parses and validates data types for TDS rates."""
    try:
        if 'threshold' in tds_data and tds_data['threshold'] is not None:
            tds_data['threshold'] = float(tds_data['threshold'])
        if 'tdsRate' in tds_data and tds_data['tdsRate'] is not None:
            tds_data['tdsRate'] = float(tds_data['tdsRate'])
        if 'tdsRateNoPan' in tds_data and tds_data['tdsRateNoPan'] is not None:
            tds_data['tdsRateNoPan'] = float(tds_data['tdsRateNoPan'])
        if 'effectiveDate' in tds_data and isinstance(tds_data['effectiveDate'], str) and tds_data['effectiveDate']:
            # Assumes date is in ISO format 'YYYY-MM-DD' from frontend
            tds_data['effectiveDate'] = datetime.fromisoformat(tds_data['effectiveDate'].split('T')[0])
        return tds_data
    except (ValueError, TypeError) as e:
        logging.error(f"Error parsing TDS data: {e}")
        raise ValueError("Invalid data format for numeric or date fields.")


def create_tds_rate(db_conn, tds_data, user="System", tenant_id="default_tenant_placeholder"):
    """
    Creates a new TDS rate document in the database.
    Checks for uniqueness based on natureOfPayment, section, and effectiveDate.
    """
    try:
        now = datetime.utcnow()

        parsed_data = _parse_tds_data(tds_data)

        # Uniqueness check
        existing_rate = db_conn[TDS_RATES_COLLECTION].find_one({
            "natureOfPayment": parsed_data.get("natureOfPayment"),
            "section": parsed_data.get("section"),
            "effectiveDate": parsed_data.get("effectiveDate"),
            "tenant_id": tenant_id
        })
        if existing_rate:
            raise ValueError(f"A TDS rate for '{parsed_data.get('natureOfPayment')}' with the same effective date already exists.")

        parsed_data['created_date'] = now
        parsed_data['updated_date'] = now
        parsed_data['updated_user'] = user
        parsed_data['tenant_id'] = tenant_id
        parsed_data.pop('_id', None)

        result = db_conn[TDS_RATES_COLLECTION].insert_one(parsed_data)
        inserted_id = result.inserted_id
        logging.info(f"TDS Rate created with ID: {inserted_id} by {user} for tenant {tenant_id}")

        # add_activity( ... ) # Optional: Log activity
        return inserted_id
    except ValueError as ve:
        raise
    except Exception as e:
        logging.error(f"Error creating TDS rate for tenant {tenant_id}: {e}")
        raise

def get_tds_rate_by_id(db_conn, rate_id, tenant_id="default_tenant_placeholder"):
    """Fetches a single TDS rate by its document ID."""
    try:
        return db_conn[TDS_RATES_COLLECTION].find_one({"_id": ObjectId(rate_id), "tenant_id": tenant_id})
    except Exception as e:
        logging.error(f"Error fetching TDS rate by ID {rate_id} for tenant {tenant_id}: {e}")
        raise

def get_all_tds_rates(db_conn, page=1, limit=25, filters=None, tenant_id="default_tenant_placeholder"):
    """Fetches a paginated list of all TDS rates for a tenant."""
    try:
        query = filters if filters else {}
        query["tenant_id"] = tenant_id

        skip = (page - 1) * limit if limit > 0 else 0

        # Default sort order
        sort_order = [("natureOfPayment", 1), ("section", 1), ("effectiveDate", -1)]

        # Find all documents matching the query and apply sorting
        rates_cursor = db_conn[TDS_RATES_COLLECTION].find(query).sort(sort_order).skip(skip)

        # Apply limit only if it's a positive number
        if limit > 0:
            rates_cursor = rates_cursor.limit(limit)

        rates_list = list(rates_cursor)
        total_items = db_conn[TDS_RATES_COLLECTION].count_documents(query)
        return rates_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all TDS rates for tenant {tenant_id}: {e}")
        raise

def update_tds_rate(db_conn, rate_id, update_data, user="System", tenant_id="default_tenant_placeholder"):
    """Updates an existing TDS rate document."""
    try:
        now = datetime.utcnow()
        original_id_obj = ObjectId(rate_id)

        parsed_data = _parse_tds_data(update_data)

        # Uniqueness check on update
        if "natureOfPayment" in parsed_data or "section" in parsed_data or "effectiveDate" in parsed_data:
            # Fetch the original document to build the query for the uniqueness check
            original_doc = db_conn[TDS_RATES_COLLECTION].find_one({"_id": original_id_obj})
            if original_doc:
                query_fields = {
                    "natureOfPayment": parsed_data.get("natureOfPayment", original_doc.get("natureOfPayment")),
                    "section": parsed_data.get("section", original_doc.get("section")),
                    "effectiveDate": parsed_data.get("effectiveDate", original_doc.get("effectiveDate")),
                    "tenant_id": tenant_id,
                    "_id": {"$ne": original_id_obj}
                }
                existing_rate = db_conn[TDS_RATES_COLLECTION].find_one(query_fields)
                if existing_rate:
                    raise ValueError("An identical TDS rate with this effective date already exists.")

        parsed_data.pop('_id', None)
        update_payload = {
            "$set": {
                **parsed_data,
                "updated_date": now,
                "updated_user": user
            }
        }

        result = db_conn[TDS_RATES_COLLECTION].update_one(
            {"_id": original_id_obj, "tenant_id": tenant_id},
            update_payload
        )

        if result.matched_count > 0:
            logging.info(f"TDS Rate {rate_id} updated by {user} for tenant {tenant_id}")
            # add_activity( ... ) # Optional: Log activity

        return result.matched_count
    except ValueError as ve:
        raise
    except Exception as e:
        logging.error(f"Error updating TDS rate {rate_id} for tenant {tenant_id}: {e}")
        raise

def delete_tds_rate_by_id(db_conn, rate_id, user="System", tenant_id="default_tenant_placeholder"):
    """Deletes a TDS rate document from the database."""
    try:
        original_id_obj = ObjectId(rate_id)
        result = db_conn[TDS_RATES_COLLECTION].delete_one({"_id": original_id_obj, "tenant_id": tenant_id})

        if result.deleted_count > 0:
            logging.info(f"TDS Rate {rate_id} deleted by {user} for tenant {tenant_id}.")
            # add_activity( ... ) # Optional: Log activity

        return result.deleted_count
    except Exception as e:
        logging.error(f"Error deleting TDS rate {rate_id} for tenant {tenant_id}: {e}")
        raise
