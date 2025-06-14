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
    get_dropdown_by_id
)
# Import utility to get DB instance
from db.database import get_db

dropdown_bp = Blueprint(
    'dropdown_bp',
    __name__,
    url_prefix='/api/dropdown'
)

logging.basicConfig(level=logging.INFO) # Ensure logger is configured

# Placeholder functions - replace with your actual implementation
def get_current_user():
    return session.get('username', 'System_User_Placeholder')

def get_current_tenant_id():
    return session.get('tenant_id', 'default_tenant') # Ensure this returns the correct tenant_id

@dropdown_bp.route("", methods=["GET"])
def handle_get_dropdowns():
    """
    Handles GET requests to fetch dropdown values.
    Can be paginated or filtered by type.
    Query Parameters:
        page (int): Page number (default: 1).
        limit (int): Items per page (default: 25). Use -1 for all items of a type.
        type (str): The specific type of dropdown values to fetch (e.g., 'companyType').
    """
    try:
        db = get_db()
        current_tenant = get_current_tenant_id()
        type_filter = request.args.get("type", None)

        page_str = request.args.get("page", "1")
        limit_str = request.args.get("limit", "25")

        page = int(page_str) if page_str.isdigit() else 1
        # If type_filter is present, frontend might send limit=-1 to get all of that type
        limit = int(limit_str) if limit_str.isdigit() else 25
        if limit == -1 and type_filter: # Special case for fetching all of a type
            pass # DAL will handle limit=-1 appropriately
        elif limit < 1 and limit != -1 : limit = 1 # Ensure positive limit unless -1
        if limit > 200 and limit != -1: limit = 200 # Max limit for safety unless -1


        dropdown_list, total_items = get_dropdowns_paginated(
            db_conn=db,
            page=page,
            limit=limit,
            type_filter=type_filter, # Pass type_filter to DAL
            tenant_id=current_tenant
        )

        result = [
            {**item, '_id': str(item['_id'])} for item in dropdown_list
        ]

        response_data = {
            "data": result,
            "total": total_items,
            "page": page,
            "limit": limit if limit > 0 else total_items,
        }
        if limit > 0 and total_items > 0 :
             response_data["totalPages"] = (total_items + limit - 1) // limit
        elif total_items > 0 and limit == -1: # All items fetched
             response_data["totalPages"] = 1
        else:
             response_data["totalPages"] = 0 if total_items == 0 else 1


        return jsonify(response_data), 200

    except ValueError:
         return jsonify({"message": "Invalid page or limit parameter. Must be integers."}), 400
    except Exception as e:
        logging.error(f"Error in handle_get_dropdowns: {e}")
        current_app.logger.error(f"Error details in handle_get_dropdowns: {str(e)}")
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

        new_id = add_dropdown(db_conn=db, data=data, user=current_user, tenant_id=current_tenant)

        # Fetch the newly created item to return it in the response
        created_item = get_dropdown_by_id(db_conn=db, item_id=str(new_id), tenant_id=current_tenant)
        if created_item:
            created_item['_id'] = str(created_item['_id'])
            return jsonify({"message": "Dropdown value added successfully", "data": created_item}), 201
        else:
            logging.warning(f"Dropdown value created with ID {new_id}, but failed to retrieve for response.")
            return jsonify({"message": "Dropdown value added successfully", "id": str(new_id)}), 201

    except ValueError as ve:
        logging.warning(f"ValueError in handle_add_dropdown: {ve}")
        return jsonify({"message": str(ve)}), 400
    except Exception as e:
        logging.error(f"Error in handle_add_dropdown: {e}")
        current_app.logger.error(f"Error details in handle_add_dropdown: {str(e)}")
        return jsonify({"message": "Failed to add dropdown value", "error": str(e)}), 500

@dropdown_bp.route("/<item_id>", methods=["PUT"])
def handle_update_dropdown(item_id):
    data = request.get_json()
    if not data or not any(key in data for key in ['label', 'value', 'type']):
         return jsonify({"message": "No update data provided or missing relevant fields (label, value, or type)"}), 400

    try:
        if not ObjectId.is_valid(item_id):
            return jsonify({"message": "Invalid dropdown ID format"}), 400

        db = get_db()
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()

        logging.info(f"API: Attempting to update dropdown ID {item_id} for tenant {current_tenant} with data: {data}")
        matched_count = update_dropdown(db_conn=db, item_id=item_id, data=data, user=current_user, tenant_id=current_tenant)

        if matched_count == 0:
            logging.warning(f"API: Dropdown item ID {item_id} not found for tenant {current_tenant} or no changes made during update.")
            return jsonify({"message": "Dropdown value not found or no changes made"}), 404

        logging.info(f"API: Update matched {matched_count} document(s). Fetching updated item {item_id}...")
        updated_item = get_dropdown_by_id(db_conn=db, item_id=item_id, tenant_id=current_tenant)

        if updated_item:
            logging.info(f"API: Successfully fetched updated item: {updated_item}")
            updated_item['_id'] = str(updated_item['_id'])
            return jsonify({"message": "Dropdown value updated successfully", "data": updated_item}), 200
        else:
            logging.error(f"API CRITICAL: Dropdown item ID {item_id} was reportedly updated (matched_count: {matched_count}), but could not be fetched afterwards for tenant {current_tenant}.")
            return jsonify({"message": "Dropdown value updated, but failed to retrieve for confirmation. Please refresh."}), 200

    except ValueError as ve:
        logging.warning(f"ValueError in handle_update_dropdown for ID {item_id}: {ve}")
        return jsonify({"message": str(ve)}), 409
    except Exception as e:
        logging.error(f"Unexpected error in handle_update_dropdown for ID {item_id}: {e}")
        current_app.logger.error(f"Error details in handle_update_dropdown: {str(e)}")
        return jsonify({"message": "Failed to update dropdown value due to an internal error", "error_details": str(e)}), 500

@dropdown_bp.route("/<item_id>", methods=["DELETE"])
def handle_delete_dropdown(item_id):
    try:
        if not ObjectId.is_valid(item_id):
            return jsonify({"message": "Invalid dropdown ID format"}), 400

        db = get_db()
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()

        deleted_count = delete_dropdown(db_conn=db, item_id=item_id, user=current_user, tenant_id=current_tenant)

        if deleted_count == 0:
            return jsonify({"message": "Dropdown value not found"}), 404
        return jsonify({"message": "Dropdown value deleted successfully"}), 200
    except ValueError as ve:
        logging.warning(f"ValueError in handle_delete_dropdown for ID {item_id}: {ve}")
        return jsonify({"message": str(ve)}), 400
    except Exception as e:
        logging.error(f"Error in handle_delete_dropdown for ID {item_id}: {e}")
        current_app.logger.error(f"Error details in handle_delete_dropdown: {str(e)}")
        return jsonify({"message": "Failed to delete dropdown value", "error": str(e)}), 500

# This route was duplicated in the user's provided code. Ensuring it's unique.
# If you intend to have a separate GET for a single item by ID, it's fine.
# If it was meant to be part of the main GET /api/dropdown with an optional ID, that's a different pattern.
@dropdown_bp.route("/item/<item_id>", methods=["GET"]) # Changed route slightly for uniqueness if needed
def handle_get_single_dropdown_item(item_id):
    try:
        if not ObjectId.is_valid(item_id):
            return jsonify({"message": "Invalid dropdown ID format"}), 400

        db = get_db()
        current_tenant = get_current_tenant_id()
        item = get_dropdown_by_id(db_conn=db, item_id=item_id, tenant_id=current_tenant)

        if item:
            item['_id'] = str(item['_id'])
            return jsonify(item), 200
        else:
            return jsonify({"message": "Dropdown value not found"}), 404
    except ValueError:
        return jsonify({"message": "Invalid dropdown ID format"}), 400
    except Exception as e:
        logging.error(f"Error in handle_get_single_dropdown_item for ID {item_id}: {e}")
        current_app.logger.error(f"Error details in handle_get_single_dropdown_item: {str(e)}")
        return jsonify({"message": "Failed to fetch dropdown value", "error": str(e)}), 500

