# api/dropdown.py
from flask import Blueprint, request, jsonify, session
import logging

# Import DAL functions for dropdowns
from db.dropdown_dal import (
    get_dropdowns_paginated,
    add_dropdown,
    update_dropdown,
    delete_dropdown,
    get_dropdown_by_id
)

# Define the blueprint for dropdown routes
dropdown_bp = Blueprint(
    'dropdown_bp',
    __name__,
    url_prefix='/api/dropdown' # Base URL for all routes in this blueprint
)

logging.basicConfig(level=logging.INFO)

def get_current_user():
    return session.get('username', 'System')

@dropdown_bp.route("", methods=["GET"])
def handle_get_dropdowns():
    """
    Handles GET requests to fetch dropdown values.
    Can be paginated or filtered by type.
    Query Parameters:
        page (int): Page number (default: 1) - used if 'type' is not provided.
        limit (int): Items per page (default: 25) - used if 'type' is not provided.
        type (str): The specific type of dropdown values to fetch (e.g., 'companyType').
    """
    try:
        type_filter = request.args.get("type", None)

        if type_filter:
            # Fetch all items of a specific type
            dropdown_list, total_items = get_dropdowns_paginated(type_filter=type_filter)
            # For type-specific fetches, pagination params might not be relevant in the response
            page = 1
            limit = total_items # Or a high number if DAL still paginates
        else:
            # Standard pagination
            page = int(request.args.get("page", 1))
            limit = int(request.args.get("limit", 25))
            if page < 1: page = 1
            if limit < 1: limit = 1
            if limit > 200: limit = 200 # Max limit for safety

            dropdown_list, total_items = get_dropdowns_paginated(page=page, limit=limit)

        result = [
            {**item, '_id': str(item['_id'])} for item in dropdown_list
        ]

        response_data = {
            "data": result,
            "total": total_items,
        }
        # Only include pagination details if not filtering by a specific type
        # or if you decide to implement pagination for type-filtered results as well.
        if not type_filter:
            response_data["page"] = page
            response_data["limit"] = limit
            response_data["totalPages"] = (total_items + limit - 1) // limit if limit > 0 else 0
        else: # For type filter, we are returning all items of that type
            response_data["page"] = 1
            response_data["limit"] = total_items
            response_data["totalPages"] = 1 if total_items > 0 else 0


        return jsonify(response_data), 200

    except ValueError:
         return jsonify({"message": "Invalid page or limit parameter. Must be integers."}), 400
    except Exception as e:
        logging.error(f"Error in handle_get_dropdowns: {e}")
        return jsonify({"message": "Failed to fetch dropdown values"}), 500

@dropdown_bp.route("", methods=["POST"])
def handle_add_dropdown():
    data = request.get_json()
    if not data or not data.get("type") or not data.get("value") or not data.get("label"):
        return jsonify({"message": "Missing required fields: type, value, and label"}), 400
    try:
        current_user = get_current_user()
        new_id = add_dropdown(data, user=current_user)
        return jsonify({"message": "Dropdown value added successfully", "id": str(new_id)}), 201
    except Exception as e:
        logging.error(f"Error in handle_add_dropdown: {e}")
        return jsonify({"message": "Failed to add dropdown value"}), 500

@dropdown_bp.route("/<item_id>", methods=["PUT"])
def handle_update_dropdown(item_id):
    data = request.get_json()
    if not data or not any(key in data for key in ['label', 'value', 'type']):
         return jsonify({"message": "No update data provided or missing required fields"}), 400
    try:
        current_user = get_current_user()
        matched_count = update_dropdown(item_id, data, user=current_user)
        if matched_count == 0:
            return jsonify({"message": "Dropdown value not found"}), 404
        return jsonify({"message": "Dropdown value updated successfully"}), 200
    except ValueError:
        return jsonify({"message": "Invalid dropdown ID format"}), 400
    except Exception as e:
        logging.error(f"Error in handle_update_dropdown for ID {item_id}: {e}")
        return jsonify({"message": "Failed to update dropdown value"}), 500

@dropdown_bp.route("/<item_id>", methods=["DELETE"])
def handle_delete_dropdown(item_id):
    try:
        deleted_count = delete_dropdown(item_id)
        if deleted_count == 0:
            return jsonify({"message": "Dropdown value not found"}), 404
        return jsonify({"message": "Dropdown value deleted successfully"}), 200
    except ValueError:
        return jsonify({"message": "Invalid dropdown ID format"}), 400
    except Exception as e:
        logging.error(f"Error in handle_delete_dropdown for ID {item_id}: {e}")
        return jsonify({"message": "Failed to delete dropdown value"}), 500

@dropdown_bp.route("/<item_id>", methods=["GET"])
def handle_get_single_dropdown(item_id):
    try:
        item = get_dropdown_by_id(item_id)
        if item:
            item['_id'] = str(item['_id'])
            return jsonify(item), 200
        else:
            return jsonify({"message": "Dropdown value not found"}), 404
    except ValueError:
        return jsonify({"message": "Invalid dropdown ID format"}), 400
    except Exception as e:
        logging.error(f"Error in handle_get_single_dropdown for ID {item_id}: {e}")
        return jsonify({"message": "Failed to fetch dropdown value"}), 500
