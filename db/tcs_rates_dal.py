# db/tcs_rates_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging

TCS_RATES_COLLECTION = 'tcs_rates'
logging.basicConfig(level=logging.INFO)

def _parse_tcs_data(tcs_data):
    """Parses and validates data types for TCS rates."""
    try:
        if 'threshold' in tcs_data and tcs_data['threshold'] is not None:
            tcs_data['threshold'] = float(tcs_data['threshold'])
        if 'tcsRate' in tcs_data and tcs_data['tcsRate'] is not None:
            tcs_data['tcsRate'] = float(tcs_data['tcsRate'])
        if 'tcsRateNoPan' in tcs_data and tcs_data['tcsRateNoPan'] is not None:
            tcs_data['tcsRateNoPan'] = float(tcs_data['tcsRateNoPan'])
        if 'effectiveDate' in tcs_data and isinstance(tcs_data['effectiveDate'], str) and tcs_data['effectiveDate']:
            tcs_data['effectiveDate'] = datetime.fromisoformat(tcs_data['effectiveDate'].split('T')[0])
        return tcs_data
    except (ValueError, TypeError) as e:
        logging.error(f"Error parsing TCS data: {e}")
        raise ValueError("Invalid data format for numeric or date fields.")

def create_tcs_rate(db_conn, tcs_data, user="System", tenant_id="default_tenant_placeholder"):
    """Creates a new TCS rate document."""
    try:
        now = datetime.utcnow()
        parsed_data = _parse_tcs_data(tcs_data)

        parsed_data['created_date'] = now
        parsed_data['updated_date'] = now
        parsed_data['updated_user'] = user
        parsed_data['tenant_id'] = tenant_id
        parsed_data.pop('_id', None)

        result = db_conn[TCS_RATES_COLLECTION].insert_one(parsed_data)
        return result.inserted_id
    except Exception as e:
        logging.error(f"Error creating TCS rate for tenant {tenant_id}: {e}")
        raise

def get_all_tcs_rates(db_conn, page=1, limit=25, filters=None, tenant_id="default_tenant_placeholder"):
    """Fetches a list of all TCS rates for a tenant."""
    try:
        query = filters if filters else {}
        query["tenant_id"] = tenant_id
        skip = (page - 1) * limit if limit > 0 else 0
        sort_order = [("natureOfCollection", 1), ("section", 1), ("effectiveDate", -1)]

        rates_cursor = db_conn[TCS_RATES_COLLECTION].find(query).sort(sort_order).skip(skip)
        if limit > 0:
            rates_cursor = rates_cursor.limit(limit)

        rates_list = list(rates_cursor)
        total_items = db_conn[TCS_RATES_COLLECTION].count_documents(query)
        return rates_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all TCS rates for tenant {tenant_id}: {e}")
        raise

def delete_tcs_rate_by_id(db_conn, rate_id, user="System", tenant_id="default_tenant_placeholder"):
    """Deletes a TCS rate document."""
    try:
        original_id_obj = ObjectId(rate_id)
        result = db_conn[TCS_RATES_COLLECTION].delete_one({"_id": original_id_obj, "tenant_id": tenant_id})
        if result.deleted_count > 0:
            logging.info(f"TCS Rate {rate_id} deleted by {user} for tenant {tenant_id}.")
        return result.deleted_count
    except Exception as e:
        logging.error(f"Error deleting TCS rate {rate_id} for tenant {tenant_id}: {e}")
        raise
