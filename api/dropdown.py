# api/dropdown.py
from flask import Blueprint, request, jsonify, session, current_app
import logging
from bson import ObjectId
import re

# Import DAL functions for dropdowns
from db.dropdown_dal import (
    get_dropdowns_paginated,
    add_dropdown,
    update_dropdown,
    delete_dropdown,
    get_dropdown_by_id,
    is_dropdown_locked
)
# Import utility to get DB instance
from db.database import get_db

dropdown_bp = Blueprint(
    'dropdown_bp',
    __name__,
    url_prefix='/api/dropdown'
)

logging.basicConfig(level=logging.INFO)

# Placeholder functions
def get_current_user():
    return session.get('username', 'System_User_Placeholder')

def get_current_tenant_id():
    return session.get('tenant_id', 'default_tenant')

@dropdown_bp.route("", methods=["GET"])
def handle_get_dropdowns():
    """
    Handles GET requests to fetch dropdown values.
    """
    try:
        db = get_db()
        current_tenant = get_current_tenant_id()
        type_filter = request.args.get("type", None)
        page_str = request.args.get("page", "1")
        limit_str = request.args.get("limit", "25")

        page = int(page_str)
        limit = int(limit_str)

        if limit > 200 and limit != -1: limit = 200

        dropdown_list, total_items = get_dropdowns_paginated(
            db_conn=db,
            page=page,
            limit=limit,
            type_filter=type_filter,
            tenant_id=current_tenant
        )

        result = [{**item, '_id': str(item['_id'])} for item in dropdown_list]

        response_data = {
            "data": result,
            "total": total_items,
            "page": page,
            "limit": limit if limit > 0 else total_items,
            "totalPages": (total_items + limit - 1) // limit if limit > 0 else 1
        }

        return jsonify(response_data), 200
    except ValueError:
        return jsonify({"message": "Invalid page or limit parameter."}), 400
    except Exception as e:
        logging.error(f"Error in handle_get_dropdowns: {e}")
        return jsonify({"message": "Failed to fetch dropdown values", "error": str(e)}), 500

@dropdown_bp.route("", methods=["POST"])
def handle_add_dropdown():
    data = request.get_json()
    if not data or not data.get("type") or not data.get("value") or not data.get("label"):
        return jsonify({"message": "Missing required fields: type, value, and label"}), 400
    try:
        db = get_db()
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()

        # Pass the whole data dictionary to the DAL
        new_id = add_dropdown(db_conn=db, data=data, user=current_user, tenant_id=current_tenant)
        created_item = get_dropdown_by_id(db_conn=db, item_id=str(new_id), tenant_id=current_tenant)

        if created_item:
            created_item['_id'] = str(created_item['_id'])
            return jsonify({"message": "Dropdown value added successfully", "data": created_item}), 201

        return jsonify({"message": "Dropdown value added successfully", "id": str(new_id)}), 201
    except ValueError as ve:
        return jsonify({"message": str(ve)}), 400
    except Exception as e:
        logging.error(f"Error in handle_add_dropdown: {e}")
        return jsonify({"message": "Failed to add dropdown value", "error": str(e)}), 500

@dropdown_bp.route("/<item_id>", methods=["PUT"])
def handle_update_dropdown(item_id):
    data = request.get_json()
    if not data:
        return jsonify({"message": "No update data provided"}), 400

    try:
        if not ObjectId.is_valid(item_id):
            return jsonify({"message": "Invalid dropdown ID format"}), 400

        db = get_db()
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()

        if 'is_locked' not in data: # Check if it's not a lock-only update
            if is_dropdown_locked(db, item_id, current_tenant):
                return jsonify({"message": "Cannot update a locked item."}), 403

        matched_count = update_dropdown(db_conn=db, item_id=item_id, data=data, user=current_user, tenant_id=current_tenant)

        if matched_count == 0:
            return jsonify({"message": "Dropdown value not found or no changes made"}), 404

        updated_item = get_dropdown_by_id(db_conn=db, item_id=item_id, tenant_id=current_tenant)
        if updated_item:
            updated_item['_id'] = str(updated_item['_id'])
            return jsonify({"message": "Dropdown value updated successfully", "data": updated_item}), 200

        return jsonify({"message": "Dropdown value updated, but failed to retrieve for confirmation."}), 200
    except ValueError as ve:
        return jsonify({"message": str(ve)}), 409
    except Exception as e:
        logging.error(f"Error in handle_update_dropdown for ID {item_id}: {e}")
        return jsonify({"message": "Failed to update dropdown value", "error": str(e)}), 500

@dropdown_bp.route("/<item_id>", methods=["DELETE"])
def handle_delete_dropdown(item_id):
    try:
        if not ObjectId.is_valid(item_id):
            return jsonify({"message": "Invalid dropdown ID format"}), 400

        db = get_db()
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()

        if is_dropdown_locked(db, item_id, current_tenant):
            return jsonify({"message": "Cannot delete a locked item. Please unlock it first."}), 403

        deleted_count = delete_dropdown(db_conn=db, item_id=item_id, user=current_user, tenant_id=current_tenant)

        if deleted_count == 0:
            return jsonify({"message": "Dropdown value not found"}), 404
        return jsonify({"message": "Dropdown value deleted successfully"}), 200
    except ValueError as ve:
        return jsonify({"message": str(ve)}), 400
    except Exception as e:
        logging.error(f"Error in handle_delete_dropdown for ID {item_id}: {e}")
        return jsonify({"message": "Failed to delete dropdown value", "error": str(e)}), 500

