# api/inventory.py
from flask import Blueprint, request, jsonify, session, current_app
import logging
from bson import ObjectId
import re
import json
from datetime import datetime

# Import DAL functions and db utility
from db.inventory_dal import (
    create_item,
    get_item_by_id,
    get_all_items,
    update_item,
    delete_item_by_id,
    add_stock_transaction,
    get_transactions_for_item
)
from db.database import get_db

inventory_bp = Blueprint(
    'inventory_bp',
    __name__,
    url_prefix='/api/inventory'
)

logging.basicConfig(level=logging.INFO)

def get_current_user():
    return session.get('username', 'System_User_Placeholder')

def get_current_tenant_id():
    return session.get('tenant_id', 'default_tenant_placeholder')

@inventory_bp.route('', methods=['POST'])
def handle_create_item():
    """ Handles POST requests to create a new inventory item. """
    if not request.json:
        return jsonify({"message": "No JSON data provided"}), 400

    data = request.json

    required_fields = ['itemName', 'itemType', 'salePrice']
    if not all(field in data for field in required_fields):
        missing_fields = [field for field in required_fields if field not in data]
        return jsonify({"message": f"Missing required fields: {', '.join(missing_fields)}"}), 400

    try:
        db = get_db()
        item_id = create_item(db, data, user=get_current_user(), tenant_id=get_current_tenant_id())
        created_item = get_item_by_id(db, str(item_id), tenant_id=get_current_tenant_id())
        if created_item:
            created_item['_id'] = str(created_item['_id'])
            return jsonify({"message": "Item created successfully", "data": created_item}), 201
        else:
            return jsonify({"message": "Item created, but failed to retrieve."}), 500
    except ValueError as ve:
        return jsonify({"message": str(ve)}), 409
    except Exception as e:
        logging.error(f"Error in handle_create_item: {e}")
        return jsonify({"message": "Failed to create item", "error": str(e)}), 500

@inventory_bp.route('/<item_id>', methods=['PUT'])
def handle_update_item(item_id):
    """ Handles PUT requests to update an existing item. """
    if not request.json: return jsonify({"message": "No JSON data provided"}), 400
    if not ObjectId.is_valid(item_id): return jsonify({"message": "Invalid item ID format"}), 400

    data = request.json
    try:
        db = get_db()
        matched_count = update_item(db, item_id, data, user=get_current_user(), tenant_id=get_current_tenant_id())
        if matched_count == 0: return jsonify({"message": "Item not found or no changes made"}), 404
        updated_item = get_item_by_id(db, item_id, tenant_id=get_current_tenant_id())
        if updated_item:
            updated_item['_id'] = str(updated_item['_id'])
            return jsonify({"message": "Item updated successfully", "data": updated_item}), 200
        else:
            return jsonify({"message": "Item updated, but failed to retrieve data."}), 500
    except ValueError as ve:
        return jsonify({"message": str(ve)}), 409
    except Exception as e:
        logging.error(f"Error in handle_update_item for ID {item_id}: {e}")
        return jsonify({"message": "Failed to update item", "error": str(e)}), 500

@inventory_bp.route('/<item_id>', methods=['GET'])
def handle_get_item(item_id):
    if not ObjectId.is_valid(item_id): return jsonify({"message": "Invalid item ID format"}), 400
    try:
        db = get_db()
        item = get_item_by_id(db, item_id, tenant_id=get_current_tenant_id())
        if item:
            item['_id'] = str(item['_id'])
            return jsonify(item), 200
        else:
            return jsonify({"message": "Item not found"}), 404
    except Exception as e:
        logging.error(f"Error in handle_get_item for ID {item_id}: {e}")
        return jsonify({"message": "Failed to fetch item", "error": str(e)}), 500

@inventory_bp.route('', methods=['GET'])
def handle_get_all_items():
    """ Handles GET requests to fetch inventory items with pagination and filtering. """
    try:
        page = int(request.args.get("page", 1))
        limit_str = request.args.get("limit")
        search_term = request.args.get("search", None)
        category = request.args.get("category", None)

        limit = -1
        if limit_str:
            try:
                limit = int(limit_str)
            except ValueError:
                return jsonify({"message": "Invalid limit parameter. Must be an integer."}), 400

        db = get_db()
        filters = {}
        if search_term:
            regex_query = {"$regex": re.escape(search_term), "$options": "i"}
            filters["$or"] = [
                {"itemName": regex_query},
                {"itemCode": regex_query},
                {"description": regex_query},
                {"serialNo": regex_query},
                {"batchCode": regex_query}
            ]
        if category:
            filters["category"] = category

        item_list, total_items = get_all_items(db, page, limit, filters, tenant_id=get_current_tenant_id())

        for item in item_list:
            item['_id'] = str(item['_id'])

        return jsonify({
            "data": item_list,
            "total": total_items,
            "page": page,
            "limit": limit if limit > 0 else total_items,
            "totalPages": (total_items + limit - 1) // limit if limit > 0 else 1
        }), 200
    except ValueError as ve:
         return jsonify({"message": str(ve)}), 400
    except Exception as e:
        logging.error(f"Error in handle_get_all_items: {e}")
        return jsonify({"message": "Failed to fetch items", "error": str(e)}), 500

@inventory_bp.route('/<item_id>', methods=['DELETE'])
def handle_delete_item(item_id):
    if not ObjectId.is_valid(item_id): return jsonify({"message": "Invalid item ID format"}), 400
    try:
        db = get_db()
        deleted_count = delete_item_by_id(db, item_id, user=get_current_user(), tenant_id=get_current_tenant_id())
        if deleted_count == 0: return jsonify({"message": "Item not found"}), 404
        return jsonify({"message": "Item deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error in handle_delete_item for ID {item_id}: {e}")
        return jsonify({"message": "Failed to delete item", "error": str(e)}), 500

@inventory_bp.route('/<item_id>/stock-transactions', methods=['GET'])
def handle_get_stock_transactions(item_id):
    """ Fetches all stock transactions for a specific item. """
    if not ObjectId.is_valid(item_id): return jsonify({"message": "Invalid item ID format"}), 400
    try:
        db = get_db()
        transactions = get_transactions_for_item(db, item_id, get_current_tenant_id())
        for tx in transactions:
            tx['_id'] = str(tx['_id'])
        return jsonify({"data": transactions}), 200
    except Exception as e:
        logging.error(f"Error fetching stock transactions for item {item_id}: {e}")
        return jsonify({"message": "Failed to fetch stock transactions", "error": str(e)}), 500
