# db/expense_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging
import re
import json # For parsing lineItems if sent as JSON string

from .database import mongo
from .activity_log_dal import add_activity # Assuming you have this for logging

EXPENSE_COLLECTION = 'expenses'

def parse_date_string(date_string):
    if not date_string or not isinstance(date_string, str):
        return None
    formats_to_try = ["%d/%m/%Y", "%Y-%m-%d"] # Frontend sends YYYY-MM-DD
    for fmt in formats_to_try:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    logging.warning(f"Could not parse date string: {date_string} with known formats.")
    return None

def parse_float_from_string(value_str, field_name="field"):
    if value_str is None or value_str == '':
        return None # Or 0.0 if you prefer default
    try:
        # Remove currency symbols and commas before parsing
        cleaned_str = re.sub(r'[$,]', '', str(value_str))
        return float(cleaned_str)
    except (ValueError, TypeError):
        logging.warning(f"Could not convert {field_name} '{value_str}' to float. Storing as None.")
        return None

def create_expense(expense_data, user="System", tenant_id="default_tenant"):
    try:
        db = mongo.db
        now = datetime.utcnow()

        payload = {
            'created_date': now,
            'updated_date': now,
            'updated_user': user,
            'tenant_id': tenant_id,
        }

        # Map frontend fields to backend schema
        payload['billNo'] = expense_data.get('billNo')
        payload['billDate'] = parse_date_string(expense_data.get('billDate'))
        payload['supplierGst'] = expense_data.get('supplierGst')
        payload['supplierId'] = ObjectId(expense_data['supplierId']) if expense_data.get('supplierId') else None
        payload['dueDate'] = parse_date_string(expense_data.get('dueDate'))
        payload['expenseHeadId'] = ObjectId(expense_data['expenseHeadId']) if expense_data.get('expenseHeadId') else None
        payload['narration'] = expense_data.get('narration')
        payload['currency'] = expense_data.get('currency', 'INR')

        payload['totalAmount'] = parse_float_from_string(expense_data.get('totalAmount'), 'totalAmount')
        payload['tdsPercentage'] = parse_float_from_string(expense_data.get('tdsPercentage'), 'tdsPercentage')
        payload['gstRateId'] = ObjectId(expense_data['gstRateId']) if expense_data.get('gstRateId') else None
        payload['gstVatAmount'] = parse_float_from_string(expense_data.get('gstVatAmount'), 'gstVatAmount')
        payload['netAmount'] = parse_float_from_string(expense_data.get('netAmount'), 'netAmount')

        payload['paymentMethodPublish'] = expense_data.get('paymentMethodPublish')
        payload['billSource'] = expense_data.get('billSource')
        payload['status'] = expense_data.get('status', 'Draft')

        # Handle invoice file name if provided by API layer
        if 'invoiceFilename' in expense_data:
            payload['invoiceFilename'] = expense_data['invoiceFilename']

        # Process line items
        line_items_data = expense_data.get('lineItems', [])
        if isinstance(line_items_data, str): # If sent as JSON string from FormData
            try:
                line_items_data = json.loads(line_items_data)
            except json.JSONDecodeError:
                logging.error("Failed to parse lineItems JSON string.")
                line_items_data = []

        processed_line_items = []
        if isinstance(line_items_data, list):
            for item in line_items_data:
                processed_item = {
                    'description': item.get('description'),
                    'price': parse_float_from_string(item.get('price'), 'lineItem.price'),
                    'qty': parse_float_from_string(item.get('qty'), 'lineItem.qty'),
                    'hsnCode': item.get('hsnCode'),
                    'subtotal': parse_float_from_string(item.get('subtotal'), 'lineItem.subtotal')
                }
                processed_line_items.append(processed_item)
        payload['lineItems'] = processed_line_items

        # These are calculated on frontend, but good to store consistent values
        payload['subTotalFromItems'] = parse_float_from_string(expense_data.get('subTotalFromItems'), 'subTotalFromItems')
        payload['discountAmount'] = parse_float_from_string(expense_data.get('discountAmount'), 'discountAmount')
        payload['taxFromItems'] = parse_float_from_string(expense_data.get('taxFromItems'), 'taxFromItems')
        payload['grandTotalFromItems'] = parse_float_from_string(expense_data.get('grandTotalFromItems'), 'grandTotalFromItems')


        result = db[EXPENSE_COLLECTION].insert_one(payload)
        inserted_id = result.inserted_id
        logging.info(f"Expense created with ID: {inserted_id} by {user} for tenant {tenant_id}")

        add_activity(
            "CREATE_EXPENSE", user,
            f"Created Expense: Bill No='{payload.get('billNo', 'N/A')}', Supplier ID='{str(payload.get('supplierId','N/A'))}'",
            inserted_id, EXPENSE_COLLECTION, tenant_id
        )
        return inserted_id
    except Exception as e:
        logging.error(f"Error creating expense for tenant {tenant_id}: {e}")
        raise

def get_expense_by_id(expense_id, tenant_id="default_tenant"):
    try:
        db = mongo.db
        return db[EXPENSE_COLLECTION].find_one({"_id": ObjectId(expense_id), "tenant_id": tenant_id})
    except Exception as e:
        logging.error(f"Error fetching expense by ID {expense_id} for tenant {tenant_id}: {e}")
        raise

def get_all_expenses(page=1, limit=25, filters=None, sort_by='billDate', sort_order=-1, tenant_id="default_tenant"):
    try:
        db = mongo.db
        query = filters if filters else {}
        query["tenant_id"] = tenant_id
        skip = (page - 1) * limit if limit > 0 else 0

        if filters and filters.get('dateFrom') and filters.get('dateTo'):
            query['billDate'] = { # Assuming filtering by billDate
                "$gte": filters.pop('dateFrom'),
                "$lte": filters.pop('dateTo')
            }
        # ... (other specific filters)

        if limit > 0:
            expenses_cursor = db[EXPENSE_COLLECTION].find(query).sort(sort_by, sort_order).skip(skip).limit(limit)
        else:
            expenses_cursor = db[EXPENSE_COLLECTION].find(query).sort(sort_by, sort_order).skip(skip)

        expense_list = list(expenses_cursor)
        total_items = db[EXPENSE_COLLECTION].count_documents(query)
        return expense_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all expenses for tenant {tenant_id}: {e}")
        raise

def update_expense(expense_id, update_data, user="System", tenant_id="default_tenant"):
    try:
        db = mongo.db
        now = datetime.utcnow()
        original_id_obj = ObjectId(expense_id)

        payload_to_set = {
            "updated_date": now,
            "updated_user": user
        }

        # Map and process fields from update_data
        simple_text_fields = ['billNo', 'supplierGst', 'narration', 'currency', 'paymentMethodPublish', 'billSource', 'status']
        for field in simple_text_fields:
            if field in update_data:
                payload_to_set[field] = update_data[field]

        object_id_fields = {'supplierId': 'supplierId', 'expenseHeadId': 'expenseHeadId', 'gstRateId': 'gstRateId'}
        for form_field, db_field in object_id_fields.items():
            if form_field in update_data:
                payload_to_set[db_field] = ObjectId(update_data[form_field]) if update_data[form_field] else None

        date_fields = {'billDate': 'billDate', 'dueDate': 'dueDate'}
        for form_field, db_field in date_fields.items():
            if form_field in update_data:
                payload_to_set[db_field] = parse_date_string(update_data[form_field])

        numeric_fields_from_string = ['totalAmount', 'tdsPercentage', 'gstVatAmount', 'netAmount', 'subTotalFromItems', 'discountAmount', 'taxFromItems', 'grandTotalFromItems']
        for field in numeric_fields_from_string:
            if field in update_data:
                payload_to_set[field] = parse_float_from_string(update_data[field], field)

        if 'invoiceFilename' in update_data: # If a new file was uploaded and processed by API
            payload_to_set['invoiceFilename'] = update_data['invoiceFilename']

        # Process line items
        if 'lineItems' in update_data:
            line_items_data = update_data['lineItems']
            if isinstance(line_items_data, str):
                try:
                    line_items_data = json.loads(line_items_data)
                except json.JSONDecodeError:
                    line_items_data = []

            processed_line_items = []
            if isinstance(line_items_data, list):
                for item in line_items_data:
                    processed_item = {
                        'description': item.get('description'),
                        'price': parse_float_from_string(item.get('price'), 'lineItem.price'),
                        'qty': parse_float_from_string(item.get('qty'), 'lineItem.qty'),
                        'hsnCode': item.get('hsnCode'),
                        'subtotal': parse_float_from_string(item.get('subtotal'), 'lineItem.subtotal')
                    }
                    processed_line_items.append(processed_item)
            payload_to_set['lineItems'] = processed_line_items

        if not payload_to_set or len(payload_to_set) <= 2: # Only metadata updated
            logging.info(f"No effective changes for expense {expense_id}. Update skipped.")
            return 0


        result = db[EXPENSE_COLLECTION].update_one(
            {"_id": original_id_obj, "tenant_id": tenant_id},
            {"$set": payload_to_set}
        )

        if result.matched_count > 0:
            logging.info(f"Expense {expense_id} updated by {user} for tenant {tenant_id}")
            add_activity(
                "UPDATE_EXPENSE", user,
                f"Updated Expense ID: {expense_id}. Changed fields: {list(payload_to_set.keys())}",
                original_id_obj, EXPENSE_COLLECTION, tenant_id
            )
        return result.matched_count
    except Exception as e:
        logging.error(f"Error updating expense {expense_id} for tenant {tenant_id}: {e}")
        raise

def delete_expense_by_id(expense_id, user="System", tenant_id="default_tenant"):
    try:
        db = mongo.db
        original_id_obj = ObjectId(expense_id)

        doc_to_delete = db[EXPENSE_COLLECTION].find_one({"_id": original_id_obj, "tenant_id": tenant_id})
        doc_ref = doc_to_delete.get('billNo', str(original_id_obj)) if doc_to_delete else str(original_id_obj)

        result = db[EXPENSE_COLLECTION].delete_one({"_id": original_id_obj, "tenant_id": tenant_id})
        if result.deleted_count > 0:
            logging.info(f"Expense {expense_id} ('{doc_ref}') deleted by {user} for tenant {tenant_id}.")
            add_activity(
                "DELETE_EXPENSE", user,
                f"Deleted Expense: '{doc_ref}' (ID: {expense_id})",
                original_id_obj, EXPENSE_COLLECTION, tenant_id
            )
        return result.deleted_count
    except Exception as e:
        logging.error(f"Error deleting expense {expense_id} for tenant {tenant_id}: {e}")
        raise
