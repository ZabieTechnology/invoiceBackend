# db/inventory_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging
import re

from .activity_log_dal import add_activity

INVENTORY_COLLECTION = 'inventory_items'
TRANSACTION_COLLECTION = 'stock_transactions'
logging.basicConfig(level=logging.INFO)

def _format_item_dates_for_response(item):
    """Converts datetime objects to string format for API responses."""
    if item.get('expiryDate') and isinstance(item['expiryDate'], datetime):
        item['expiryDate'] = item['expiryDate'].strftime('%Y-%m-%d')
    if item.get('mfgDate') and isinstance(item['mfgDate'], datetime):
        item['mfgDate'] = item['mfgDate'].strftime('%Y-%m-%d')
    if item.get('asOfDate') and isinstance(item['asOfDate'], datetime):
        item['asOfDate'] = item['asOfDate'].strftime('%Y-%m-%d')
    return item

def _parse_item_dates_from_request(item_data):
    """Converts date strings from request payload to datetime objects for DB storage."""
    for date_field in ['expiryDate', 'mfgDate', 'asOfDate']:
        if date_field in item_data and item_data.get(date_field):
            try:
                item_data[date_field] = datetime.strptime(item_data[date_field], '%Y-%m-%d')
            except (ValueError, TypeError):
                item_data[date_field] = None
    return item_data

def create_item(db_conn, item_data, user="System", tenant_id="default_tenant_placeholder"):
    """
    Creates a new inventory item.
    """
    try:
        now = datetime.utcnow()
        item_name_to_check = item_data.get("itemName")
        if not item_name_to_check:
            raise ValueError("itemName is required to create an item.")

        existing_item = db_conn[INVENTORY_COLLECTION].find_one({
            "itemName": {"$regex": f"^{re.escape(item_name_to_check)}$", "$options": "i"},
            "tenant_id": tenant_id
        })
        if existing_item:
            raise ValueError(f"An item with the name '{item_name_to_check}' already exists.")

        item_data = _parse_item_dates_from_request(item_data)
        item_data['created_date'] = now
        item_data['updated_date'] = now
        item_data['updated_by'] = user
        item_data['tenant_id'] = tenant_id

        initial_stock = 0
        if item_data.get('itemType') == 'product' and item_data.get('openingStockQty'):
            try:
                initial_stock = float(item_data['openingStockQty'])
            except (ValueError, TypeError):
                initial_stock = 0

        item_data['currentStock'] = initial_stock
        item_data.pop('_id', None)

        result = db_conn[INVENTORY_COLLECTION].insert_one(item_data)
        inserted_id = result.inserted_id
        logging.info(f"Item '{item_name_to_check}' created with ID: {inserted_id}")

        add_activity("CREATE_ITEM", user, f"Created Item: {item_name_to_check}", inserted_id, INVENTORY_COLLECTION, tenant_id)

        if initial_stock > 0:
            add_stock_transaction(
                db_conn=db_conn, item_id=str(inserted_id), transaction_type='IN', quantity=initial_stock,
                price_per_item=item_data.get('pricePerItem'), notes='Initial opening stock', user=user, tenant_id=tenant_id
            )
        return inserted_id
    except ValueError as ve:
        raise
    except Exception as e:
        logging.error(f"Error creating item: {e}")
        raise

def get_item_by_id(db_conn, item_id, tenant_id="default_tenant_placeholder"):
    try:
        item = db_conn[INVENTORY_COLLECTION].find_one({"_id": ObjectId(item_id), "tenant_id": tenant_id})
        if item:
            item = _format_item_dates_for_response(item)
        return item
    except Exception as e:
        logging.error(f"Error fetching item by ID {item_id}: {e}")
        raise

def get_all_items(db_conn, page=1, limit=25, filters=None, tenant_id="default_tenant_placeholder"):
    try:
        query = filters if filters else {}
        query["tenant_id"] = tenant_id

        skip = (page - 1) * limit if limit > 0 else 0
        items_cursor = db_conn[INVENTORY_COLLECTION].find(query).sort("itemName", 1).skip(skip)

        if limit > 0:
            items_cursor = items_cursor.limit(limit)

        item_list = [_format_item_dates_for_response(item) for item in items_cursor]
        total_items = db_conn[INVENTORY_COLLECTION].count_documents(query)
        return item_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all items: {e}")
        raise

def update_item(db_conn, item_id, update_data, user="System", tenant_id="default_tenant_placeholder"):
    try:
        now = datetime.utcnow()
        original_id_obj = ObjectId(item_id)

        if "itemName" in update_data:
            item_name_to_check = update_data["itemName"]
            existing_item = db_conn[INVENTORY_COLLECTION].find_one({
                "_id": {"$ne": original_id_obj},
                "itemName": {"$regex": f"^{re.escape(item_name_to_check)}$", "$options": "i"},
                "tenant_id": tenant_id
            })
            if existing_item:
                raise ValueError(f"Another item with the name '{item_name_to_check}' already exists.")

        update_data = _parse_item_dates_from_request(update_data)
        update_data.pop('_id', None)
        update_payload = {"$set": {**update_data, "updated_date": now, "updated_by": user}}

        result = db_conn[INVENTORY_COLLECTION].update_one({"_id": original_id_obj, "tenant_id": tenant_id}, update_payload)

        if result.matched_count > 0 and result.modified_count > 0:
            logging.info(f"Item {item_id} updated by {user}")
            add_activity("UPDATE_ITEM", user, f"Updated Item ID: {item_id}", original_id_obj, INVENTORY_COLLECTION, tenant_id)

        return result.matched_count
    except ValueError as ve:
        raise
    except Exception as e:
        logging.error(f"Error updating item {item_id}: {e}")
        raise

def delete_item_by_id(db_conn, item_id, user="System", tenant_id="default_tenant_placeholder"):
    try:
        original_id_obj = ObjectId(item_id)

        transaction_exists = db_conn[TRANSACTION_COLLECTION].find_one({"itemId": str(original_id_obj), "tenant_id": tenant_id})
        if transaction_exists:
            raise ValueError("Cannot delete item with existing stock transactions.")

        item_to_delete = get_item_by_id(db_conn, item_id, tenant_id)
        if not item_to_delete: return 0

        item_name = item_to_delete.get('itemName', 'N/A')
        result = db_conn[INVENTORY_COLLECTION].delete_one({"_id": original_id_obj, "tenant_id": tenant_id})

        if result.deleted_count > 0:
            logging.info(f"Item {item_id} ('{item_name}') deleted by {user}.")
            add_activity("DELETE_ITEM", user, f"Deleted Item: '{item_name}' (ID: {item_id})", original_id_obj, INVENTORY_COLLECTION, tenant_id)
        return result.deleted_count
    except ValueError as ve:
        raise
    except Exception as e:
        logging.error(f"Error deleting item {item_id}: {e}")
        raise

def add_stock_transaction(db_conn, item_id, transaction_type, quantity, price_per_item=None, notes="", user="System", tenant_id="default_tenant_placeholder"):
    """ Records a stock transaction (IN/OUT) and updates the current stock of the item. """
    try:
        now = datetime.utcnow()
        item_oid = ObjectId(item_id)

        item = db_conn[INVENTORY_COLLECTION].find_one({"_id": item_oid, "tenant_id": tenant_id})
        if not item: raise ValueError("Item not found for stock transaction.")

        quantity = float(quantity)
        if transaction_type == 'OUT' and item.get('currentStock', 0) < quantity:
            raise ValueError(f"Insufficient stock for item '{item.get('itemName')}'. Available: {item.get('currentStock', 0)}, Requested: {quantity}")

        transaction_data = {
            "tenant_id": tenant_id, "itemId": str(item_oid), "transaction_type": transaction_type, "quantity": quantity,
            "price_per_item": price_per_item, "transaction_date": now, "recorded_by": user, "notes": notes
        }
        transaction_result = db_conn[TRANSACTION_COLLECTION].insert_one(transaction_data)

        stock_change = quantity if transaction_type == 'IN' else -quantity
        db_conn[INVENTORY_COLLECTION].update_one(
            {"_id": item_oid, "tenant_id": tenant_id},
            {"$inc": {"currentStock": stock_change}, "$set": {"updated_date": now, "updated_by": user}}
        )

        logging.info(f"Stock transaction {transaction_result.inserted_id} recorded for item {item_id}.")
        return transaction_result.inserted_id
    except ValueError as ve:
        raise
    except Exception as e:
        logging.error(f"Error adding stock transaction for item {item_id}: {e}")
        raise

def get_transactions_for_item(db_conn, item_id, tenant_id="default_tenant_placeholder"):
    """ Fetches all stock transactions for a given item ID, sorted by date. """
    try:
        transactions_cursor = db_conn[TRANSACTION_COLLECTION].find({
            "itemId": item_id,
            "tenant_id": tenant_id
        }).sort("transaction_date", -1)
        return list(transactions_cursor)
    except Exception as e:
        logging.error(f"Error fetching transactions for item {item_id}: {e}")
        raise
