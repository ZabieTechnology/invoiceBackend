# api/gst_rates.py
from flask import Blueprint, request, jsonify, session
import logging
from bson import ObjectId
import re

from db.gst_rate_dal import (
    create_gst_rate,
    get_gst_rate_by_id,
    get_all_gst_rates,
    update_gst_rate,
    delete_gst_rate_by_id,
    get_gst_tds_setting,
    update_gst_tds_setting
)
# Import the DAL function for ca_tax entries
from db.ca_tax_dal import get_all_ca_tax_entries

# Renamed blueprint and updated URL prefix
gst_rates_bp = Blueprint(
    'gst_rates_bp',
    __name__,
    url_prefix='/api/gst-rates'
)

logging.basicConfig(level=logging.INFO)

def get_current_user():
    return session.get('username', 'System')

@gst_rates_bp.route('', methods=['POST'])
def handle_create_gst_rate(): # Renamed function
    data = request.get_json()
    if not data:
        return jsonify({"message": "No input data provided"}), 400
    if not data.get('taxName') or data.get('taxRate') is None or not data.get('head'):
        return jsonify({"message": "Missing required fields: Tax Name, Tax Rate, and Head"}), 400

    try:
        current_user = get_current_user()
        gst_id = create_gst_rate(data, user=current_user) # Use renamed DAL function
        created_gst_rate = get_gst_rate_by_id(str(gst_id)) # Use renamed DAL function
        if created_gst_rate:
            created_gst_rate['_id'] = str(created_gst_rate['_id'])
            return jsonify({"message": "GST rate created successfully", "data": created_gst_rate}), 201
        else:
            return jsonify({"message": "GST rate created, but failed to retrieve."}), 201
    except Exception as e:
        logging.error(f"Error in handle_create_gst_rate: {e}")
        return jsonify({"message": "Failed to create GST rate"}), 500

@gst_rates_bp.route('/<gst_id>', methods=['GET'])
def handle_get_gst_rate(gst_id): # Renamed function
    try:
        if not ObjectId.is_valid(gst_id):
            return jsonify({"message": "Invalid GST ID format"}), 400

        gst_rate = get_gst_rate_by_id(gst_id) # Use renamed DAL function
        if gst_rate:
            gst_rate['_id'] = str(gst_rate['_id'])
            return jsonify(gst_rate), 200
        else:
            return jsonify({"message": "GST rate not found"}), 404
    except Exception as e:
        logging.error(f"Error fetching GST rate {gst_id}: {e}")
        return jsonify({"message": "Failed to fetch GST rate"}), 500

@gst_rates_bp.route('', methods=['GET'])
def handle_get_all_api_gst_rates(): # Renamed function
    try:
        page = int(request.args.get("page", 1))
        limit_str = request.args.get("limit", "10")
        limit = int(limit_str) if limit_str.isdigit() and int(limit_str) != 0 else -1

        search_term = request.args.get("search", None)
        filters = {}
        if search_term:
            regex_query = {"$regex": re.escape(search_term), "$options": "i"}
            filters["$or"] = [
                {"taxName": regex_query},
                {"head": regex_query},
            ]

        gst_rate_list, total_items = get_all_gst_rates(page, limit, filters) # Use renamed DAL function

        result = []
        for item in gst_rate_list:
            item['_id'] = str(item['_id'])
            result.append(item)

        return jsonify({
            "data": result,
            "total": total_items,
            "page": page,
            "limit": limit if limit > 0 else total_items,
            "totalPages": (total_items + limit - 1) // limit if limit > 0 and total_items > 0 else 1
        }), 200
    except ValueError:
         return jsonify({"message": "Invalid page or limit parameter."}), 400
    except Exception as e:
        logging.error(f"Error fetching all GST rates: {e}")
        return jsonify({"message": "Failed to fetch GST rates"}), 500

@gst_rates_bp.route('/<gst_id>', methods=['PUT'])
def handle_update_gst_rate(gst_id): # Renamed function
    data = request.get_json()
    if not data:
        return jsonify({"message": "No input data provided"}), 400
    if not ObjectId.is_valid(gst_id):
        return jsonify({"message": "Invalid GST ID format"}), 400
    if not data.get('taxName') or data.get('taxRate') is None or not data.get('head'):
        return jsonify({"message": "Missing required fields: Tax Name, Tax Rate, and Head"}), 400

    try:
        current_user = get_current_user()
        matched_count = update_gst_rate(gst_id, data, user=current_user) # Use renamed DAL function
        if matched_count == 0:
            return jsonify({"message": "GST rate not found or no changes made"}), 404

        updated_gst_rate = get_gst_rate_by_id(gst_id) # Use renamed DAL function
        if updated_gst_rate:
            updated_gst_rate['_id'] = str(updated_gst_rate['_id'])
            return jsonify({"message": "GST rate updated successfully", "data": updated_gst_rate}), 200
        else:
            return jsonify({"message": "GST rate updated, but failed to retrieve."}), 200
    except Exception as e:
        logging.error(f"Error updating GST rate {gst_id}: {e}")
        return jsonify({"message": "Failed to update GST rate"}), 500

@gst_rates_bp.route('/<gst_id>', methods=['DELETE'])
def handle_delete_gst_rate(gst_id): # Renamed function
    try:
        if not ObjectId.is_valid(gst_id):
            return jsonify({"message": "Invalid GST ID format"}), 400

        deleted_count = delete_gst_rate_by_id(gst_id) # Use renamed DAL function
        if deleted_count == 0:
            return jsonify({"message": "GST rate not found"}), 404
        return jsonify({"message": "GST rate deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error deleting GST rate {gst_id}: {e}")
        return jsonify({"message": "Failed to delete GST rate"}), 500

# --- New Endpoint for Derived CA Tax Accounts ---
@gst_rates_bp.route('/derived-tax-accounts', methods=['GET'])
def handle_get_derived_tax_accounts():
    """
    Handles GET requests to fetch all derived CA tax accounts
    with pagination and search.
    """
    try:
        page = int(request.args.get("page", 1))
        limit_str = request.args.get("limit", "10")
        limit = int(limit_str) if limit_str.isdigit() and int(limit_str) != 0 else -1

        search_term = request.args.get("search", None)
        filters = {}
        if search_term:
            regex_query = {"$regex": re.escape(search_term), "$options": "i"}
            filters["$or"] = [
                {"name": regex_query},
                {"code": regex_query},
                {"head": regex_query},
                {"taxType": regex_query}
            ]

        # Uses get_all_ca_tax_entries from ca_tax_dal.py
        derived_tax_list, total_items = get_all_ca_tax_entries(page, limit, filters)

        result = []
        for item in derived_tax_list:
            item['_id'] = str(item['_id'])
            if 'originalGstRateId' in item and isinstance(item['originalGstRateId'], ObjectId):
                item['originalGstRateId'] = str(item['originalGstRateId'])
            result.append(item)

        return jsonify({
            "data": result,
            "total": total_items,
            "page": page,
            "limit": limit if limit > 0 else total_items,
            "totalPages": (total_items + limit - 1) // limit if limit > 0 and total_items > 0 else 1
        }), 200
    except ValueError:
         return jsonify({"message": "Invalid page or limit parameter for derived tax accounts."}), 400
    except Exception as e:
        logging.error(f"Error fetching all derived tax accounts: {e}")
        return jsonify({"message": "Failed to fetch derived tax accounts"}), 500

# --- GST TDS Setting Routes ---
@gst_rates_bp.route('/settings/gst-tds', methods=['GET'])
def handle_get_gst_tds_setting_route():
    try:
        setting = get_gst_tds_setting()
        return jsonify({"gstTdsApplicable": setting}), 200
    except Exception as e:
        logging.error(f"Error fetching GST TDS setting: {e}")
        return jsonify({"message": "Failed to fetch GST TDS setting"}), 500

@gst_rates_bp.route('/settings/gst-tds', methods=['PUT'])
def handle_update_gst_tds_setting_route():
    data = request.get_json()
    if data is None or 'gstTdsApplicable' not in data:
        return jsonify({"message": "Missing 'gstTdsApplicable' field"}), 400

    is_applicable_str = data.get('gstTdsApplicable')
    is_applicable_bool = is_applicable_str.lower() == 'yes' if isinstance(is_applicable_str, str) else False

    try:
        current_user = get_current_user()
        success = update_gst_tds_setting(is_applicable_bool, user=current_user)
        if success:
            return jsonify({"message": "GST TDS setting updated successfully", "gstTdsApplicable": "Yes" if is_applicable_bool else "No"}), 200
        else:
            return jsonify({"message": "Failed to update GST TDS setting"}), 500
    except Exception as e:
        logging.error(f"Error updating GST TDS setting via API: {e}")
        return jsonify({"message": "An internal error occurred"}), 500
