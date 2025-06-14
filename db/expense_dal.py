# db/expense_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging
import re
import json

from .database import mongo
from .activity_log_dal import add_activity

EXPENSE_COLLECTION = 'expenses'
VENDOR_COLLECTION = 'vendors'
CHART_OF_ACCOUNTS_COLLECTION = 'chart_of_accounts'

def parse_date_string(date_string):
    if not date_string or not isinstance(date_string, str):
        return None
    formats_to_try = ["%Y-%m-%d", "%d/%m/%Y"] # Backend expects YYYY-MM-DD from payload
    for fmt in formats_to_try:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    logging.warning(f"Could not parse date string: {date_string} with known formats.")
    return None

def parse_float_from_string(value_str, field_name="field"):
    if value_str is None or str(value_str).strip() == '': # Check for empty string too
        return None
    try:
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

        payload['billNo'] = expense_data.get('billNo')
        payload['billDate'] = parse_date_string(expense_data.get('billDate'))
        payload['supplierGst'] = expense_data.get('supplierGst')
        payload['supplierId'] = ObjectId(expense_data['supplierId']) if expense_data.get('supplierId') else None
        payload['dueDate'] = parse_date_string(expense_data.get('dueDate'))
        payload['expenseHeadId'] = ObjectId(expense_data['expenseHeadId']) if expense_data.get('expenseHeadId') else None
        payload['narration'] = expense_data.get('narration')
        payload['currency'] = expense_data.get('currency', 'INR')

        # Individual Tax Components
        payload['cgstAmount'] = parse_float_from_string(expense_data.get('cgstAmount'), 'cgstAmount')
        payload['sgstAmount'] = parse_float_from_string(expense_data.get('sgstAmount'), 'sgstAmount')
        payload['igstAmount'] = parse_float_from_string(expense_data.get('igstAmount'), 'igstAmount')
        payload['cessAmount'] = parse_float_from_string(expense_data.get('cessAmount'), 'cessAmount')

        # Total Tax Amount (sum of components)
        payload['taxAmount'] = (payload.get('cgstAmount') or 0) + \
                               (payload.get('sgstAmount') or 0) + \
                               (payload.get('igstAmount') or 0) + \
                               (payload.get('cessAmount') or 0)

        payload['totalAmount'] = parse_float_from_string(expense_data.get('totalAmount'), 'totalAmount')
        payload['netAmount'] = parse_float_from_string(expense_data.get('netAmount'), 'netAmount')

        payload['tdsRate'] = parse_float_from_string(expense_data.get('tdsRate'), 'tdsRate')
        payload['tdsAmountCalculated'] = parse_float_from_string(expense_data.get('tdsAmountCalculated'), 'tdsAmountCalculated')

        payload['paymentMethodPublish'] = expense_data.get('paymentMethodPublish')
        payload['billSource'] = expense_data.get('billSource')
        payload['status'] = expense_data.get('status', 'Draft')

        if 'invoiceFilename' in expense_data:
            payload['invoiceFilename'] = expense_data['invoiceFilename']

        line_items_data = expense_data.get('lineItems', [])
        if isinstance(line_items_data, str):
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
                    'hsnCode': item.get('hsnCode'), # Added HSN Code
                    'subtotal': parse_float_from_string(item.get('subtotal'), 'lineItem.subtotal')
                }
                processed_line_items.append(processed_item)
        payload['lineItems'] = processed_line_items

        payload['subTotalFromItems'] = parse_float_from_string(expense_data.get('subTotalFromItems'), 'subTotalFromItems')
        payload['discountAmount'] = parse_float_from_string(expense_data.get('discountAmount'), 'discountAmount')
        # taxFromItems and grandTotalFromItems are derived, but we can store what frontend calculated
        payload['taxFromItems'] = payload['taxAmount'] # Assuming taxFromItems is the same as total taxAmount
        payload['grandTotalFromItems'] = payload['totalAmount'] # Assuming grandTotalFromItems is same as totalAmount

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
        pipeline = [
            {"$match": {"_id": ObjectId(expense_id), "tenant_id": tenant_id}},
            {
                "$lookup": {
                    "from": VENDOR_COLLECTION,
                    "localField": "supplierId",
                    "foreignField": "_id",
                    "as": "supplierDetails"
                }
            },
            {"$unwind": {"path": "$supplierDetails", "preserveNullAndEmptyArrays": True}},
            {
                "$lookup": {
                    "from": CHART_OF_ACCOUNTS_COLLECTION,
                    "localField": "expenseHeadId",
                    "foreignField": "_id",
                    "as": "expenseHeadDetails"
                }
            },
            {"$unwind": {"path": "$expenseHeadDetails", "preserveNullAndEmptyArrays": True}},
            {
                "$addFields": {
                    "supplierName": "$supplierDetails.displayName",
                    "expenseHeadName": "$expenseHeadDetails.name"
                }
            },
        ]
        result = list(db[EXPENSE_COLLECTION].aggregate(pipeline))
        return result[0] if result else None
    except Exception as e:
        logging.error(f"Error fetching expense by ID {expense_id} for tenant {tenant_id}: {e}")
        raise

def get_all_expenses(page=1, limit=25, filters=None, sort_by='billDate', sort_order=-1, tenant_id="default_tenant"):
    try:
        db = mongo.db
        pipeline = []

        match_stage = {"tenant_id": tenant_id}
        if filters:
            if filters.get('dateFrom') and filters.get('dateTo'):
                match_stage['billDate'] = {"$gte": filters.pop('dateFrom'), "$lte": filters.pop('dateTo')}
            elif filters.get('dateFrom'): match_stage['billDate'] = {"$gte": filters.pop('dateFrom')}
            elif filters.get('dateTo'): match_stage['billDate'] = {"$lte": filters.pop('dateTo')}

            if filters.get("status") and filters["status"] != "All":
                match_stage["status"] = filters["status"]

            # Text search on original expense fields before lookup
            if filters.get("$text_search_term"):
                regex_query = {"$regex": re.escape(filters["$text_search_term"]), "$options": "i"}
                match_stage["$or"] = [
                    {"billNo": regex_query},
                    {"narration": regex_query},
                    {"lineItems.description": regex_query},
                    # Add other direct fields from expenses collection you want to search
                ]
        pipeline.append({"$match": match_stage})

        pipeline.extend([
            {"$lookup": {"from": VENDOR_COLLECTION, "localField": "supplierId", "foreignField": "_id", "as": "supplierDetails"}},
            {"$unwind": {"path": "$supplierDetails", "preserveNullAndEmptyArrays": True}},
            {"$lookup": {"from": CHART_OF_ACCOUNTS_COLLECTION, "localField": "expenseHeadId", "foreignField": "_id", "as": "expenseHeadDetails"}},
            {"$unwind": {"path": "$expenseHeadDetails", "preserveNullAndEmptyArrays": True}},
            {"$addFields": {"supplierName": "$supplierDetails.displayName", "expenseHeadName": "$expenseHeadDetails.name"}}
        ])

        # If search needs to happen on looked-up fields like supplierName, add another $match stage here
        if filters and filters.get("supplierName"): # Example for looked-up field
             pipeline.append({"$match": {"supplierName": {"$regex": re.escape(filters["supplierName"]), "$options": "i"}}})


        count_pipeline = pipeline + [{"$count": "totalItems"}]
        total_items_result = list(db[EXPENSE_COLLECTION].aggregate(count_pipeline))
        total_items = total_items_result[0]['totalItems'] if total_items_result else 0

        pipeline.append({"$sort": {sort_by: sort_order}})
        if limit > 0:
            skip = (page - 1) * limit
            pipeline.append({"$skip": skip})
            pipeline.append({"$limit": limit})

        expense_list = list(db[EXPENSE_COLLECTION].aggregate(pipeline))
        return expense_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all expenses with aggregation for tenant {tenant_id}: {e}")
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

        simple_text_fields = ['billNo', 'supplierGst', 'narration', 'currency',
                              'paymentMethodPublish', 'billSource', 'status', 'invoiceFilename']
        for field in simple_text_fields:
            if field in update_data:
                payload_to_set[field] = update_data[field]

        object_id_fields = {'supplierId': 'supplierId', 'expenseHeadId': 'expenseHeadId'} # Removed gstRateId
        for form_field, db_field in object_id_fields.items():
            if form_field in update_data:
                payload_to_set[db_field] = ObjectId(update_data[form_field]) if update_data[form_field] else None

        date_fields = {'billDate': 'billDate', 'dueDate': 'dueDate'}
        for form_field, db_field in date_fields.items():
            if form_field in update_data:
                payload_to_set[db_field] = parse_date_string(update_data[form_field])

        numeric_fields_from_string = ['totalAmount', 'taxAmount', 'netAmount', # taxAmount is now primary total tax
                                      'cgstAmount', 'sgstAmount', 'igstAmount', 'cessAmount',
                                      'tdsRate', 'tdsAmountCalculated',
                                      'subTotalFromItems', 'discountAmount']
        for field in numeric_fields_from_string:
            if field in update_data:
                payload_to_set[field] = parse_float_from_string(update_data[field], field)

        # Recalculate taxAmount if individual components are provided in update_data
        cgst = payload_to_set.get('cgstAmount', 0.0) if 'cgstAmount' in payload_to_set else (get_expense_by_id(expense_id, tenant_id).get('cgstAmount') or 0.0)
        sgst = payload_to_set.get('sgstAmount', 0.0) if 'sgstAmount' in payload_to_set else (get_expense_by_id(expense_id, tenant_id).get('sgstAmount') or 0.0)
        igst = payload_to_set.get('igstAmount', 0.0) if 'igstAmount' in payload_to_set else (get_expense_by_id(expense_id, tenant_id).get('igstAmount') or 0.0)
        cess = payload_to_set.get('cessAmount', 0.0) if 'cessAmount' in payload_to_set else (get_expense_by_id(expense_id, tenant_id).get('cessAmount') or 0.0)

        # If any individual tax component is being updated, recalculate the total taxAmount
        if any(tax_comp in update_data for tax_comp in ['cgstAmount', 'sgstAmount', 'igstAmount', 'cessAmount']):
             payload_to_set['taxAmount'] = (cgst or 0) + (sgst or 0) + (igst or 0) + (cess or 0)
        elif 'taxAmount' not in payload_to_set: # If total taxAmount is not being updated directly, ensure it's consistent
            # This case is tricky: if user clears individual components, should taxAmount become 0?
            # Or if user clears taxAmount, should components become 0?
            # For now, if taxAmount is not in update_data, it's not changed by $set unless components change it.
            # If components are also not in update_data, taxAmount remains as is in DB.
            # If components are in update_data and sum to 0, taxAmount becomes 0.
            pass


        if 'lineItems' in update_data:
            line_items_data = update_data['lineItems']
            if isinstance(line_items_data, str):
                try: line_items_data = json.loads(line_items_data)
                except json.JSONDecodeError: line_items_data = []

            processed_line_items = []
            if isinstance(line_items_data, list):
                for item in line_items_data:
                    processed_line_items.append({
                        'description': item.get('description'),
                        'price': parse_float_from_string(item.get('price'), 'lineItem.price'),
                        'qty': parse_float_from_string(item.get('qty'), 'lineItem.qty'),
                        'hsnCode': item.get('hsnCode'),
                        'subtotal': parse_float_from_string(item.get('subtotal'), 'lineItem.subtotal')
                    })
            payload_to_set['lineItems'] = processed_line_items

        if not payload_to_set or len(payload_to_set) <= 2:
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
            if doc_to_delete and doc_to_delete.get('invoiceFilename'):
                try:
                    upload_folder = current_app.config.get('EXPENSE_INVOICE_UPLOAD_FOLDER')
                    if upload_folder:
                        file_path = os.path.join(upload_folder, doc_to_delete['invoiceFilename'])
                        if os.path.exists(file_path):
                            os.remove(file_path)
                            logging.info(f"Deleted associated invoice file: {file_path}")
                except Exception as file_del_e:
                    logging.error(f"Error deleting invoice file {doc_to_delete.get('invoiceFilename')}: {file_del_e}")
        return result.deleted_count
    except Exception as e:
        logging.error(f"Error deleting expense {expense_id} for tenant {tenant_id}: {e}")
        raise
