# api/vendors.py
from flask import Blueprint, request, jsonify, session, current_app
import logging
from bson import ObjectId # For validating ObjectId in GET by ID
import re # For search functionality

# Import DAL functions
from db.vendor_dal import (
    create_vendor,
    get_vendor_by_id,
    get_all_vendors,
    update_vendor,
    delete_vendor_by_id
)

# Define the blueprint
vendors_bp = Blueprint(
    'vendors_bp',
    __name__,
    url_prefix='/api/vendors'
)

logging.basicConfig(level=logging.INFO)

def get_current_user():
    return session.get('username', 'System') # Placeholder

@vendors_bp.route('', methods=['POST'])
def handle_create_vendor():
    """Handles POST requests to create a new vendor."""
    data = request.get_json()
    if not data:
        return jsonify({"message": "No input data provided"}), 400
    # Add required field checks based on your VendorDetailsPage form
    if not data.get('displayName'): # Example required field
        return jsonify({"message": "Missing required field: displayName"}), 400

    try:
        current_user = get_current_user()
        vendor_id = create_vendor(data, user=current_user)
        created_vendor = get_vendor_by_id(str(vendor_id))
        if created_vendor:
            created_vendor['_id'] = str(created_vendor['_id'])
            return jsonify({"message": "Vendor created successfully", "data": created_vendor}), 201
        else:
            return jsonify({"message": "Vendor created, but failed to retrieve."}), 201
    except Exception as e:
        logging.error(f"Error in handle_create_vendor: {e}")
        return jsonify({"message": "Failed to create vendor"}), 500

@vendors_bp.route('/<vendor_id>', methods=['GET'])
def handle_get_vendor(vendor_id):
    """Handles GET requests to fetch a single vendor by ID."""
    try:
        if not ObjectId.is_valid(vendor_id):
            return jsonify({"message": "Invalid vendor ID format"}), 400
        
        vendor = get_vendor_by_id(vendor_id)
        if vendor:
            vendor['_id'] = str(vendor['_id'])
            return jsonify(vendor), 200
        else:
            return jsonify({"message": "Vendor not found"}), 404
    except Exception as e:
        logging.error(f"Error in handle_get_vendor for ID {vendor_id}: {e}")
        return jsonify({"message": "Failed to fetch vendor"}), 500

@vendors_bp.route('', methods=['GET'])
def handle_get_all_vendors():
    """Handles GET requests to fetch all vendors with pagination and search."""
    try:
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 25))
        search_term = request.args.get("search", None)

        filters = {}
        if search_term:
            regex_query = {"$regex": re.escape(search_term), "$options": "i"}
            filters["$or"] = [
                {"displayName": regex_query},
                {"vendorName": regex_query}, # Assuming a 'vendorName' field
                {"primaryContact.email": regex_query},
                {"primaryContact.name": regex_query},
                {"gstNo": regex_query},
                {"pan": regex_query}
            ]
        
        vendor_list, total_items = get_all_vendors(page, limit, filters)
        
        result = []
        for item in vendor_list:
            item['_id'] = str(item['_id'])
            result.append(item)

        return jsonify({
            "data": result,
            "total": total_items,
            "page": page,
            "limit": limit,
            "totalPages": (total_items + limit - 1) // limit if limit > 0 else 0
        }), 200
    except ValueError:
         return jsonify({"message": "Invalid page or limit parameter. Must be integers."}), 400
    except Exception as e:
        logging.error(f"Error in handle_get_all_vendors: {e}")
        return jsonify({"message": "Failed to fetch vendors"}), 500

@vendors_bp.route('/<vendor_id>', methods=['PUT'])
def handle_update_vendor(vendor_id):
    """Handles PUT requests to update an existing vendor."""
    data = request.get_json()
    if not data:
        return jsonify({"message": "No input data provided"}), 400
    if not ObjectId.is_valid(vendor_id):
        return jsonify({"message": "Invalid vendor ID format"}), 400

    try:
        current_user = get_current_user()
        matched_count = update_vendor(vendor_id, data, user=current_user)
        if matched_count == 0:
            return jsonify({"message": "Vendor not found or no changes made"}), 404
        
        updated_vendor = get_vendor_by_id(vendor_id)
        if updated_vendor:
            updated_vendor['_id'] = str(updated_vendor['_id'])
            return jsonify({"message": "Vendor updated successfully", "data": updated_vendor}), 200
        else:
            return jsonify({"message": "Vendor updated, but failed to retrieve updated data."}), 200
    except Exception as e:
        logging.error(f"Error in handle_update_vendor for ID {vendor_id}: {e}")
        return jsonify({"message": "Failed to update vendor"}), 500

@vendors_bp.route('/<vendor_id>', methods=['DELETE'])
def handle_delete_vendor(vendor_id):
    """Handles DELETE requests to remove a vendor."""
    try:
        if not ObjectId.is_valid(vendor_id):
            return jsonify({"message": "Invalid vendor ID format"}), 400

        deleted_count = delete_vendor_by_id(vendor_id)
        if deleted_count == 0:
            return jsonify({"message": "Vendor not found"}), 404
        return jsonify({"message": "Vendor deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error in handle_delete_vendor for ID {vendor_id}: {e}")
        return jsonify({"message": "Failed to delete vendor"}), 500
