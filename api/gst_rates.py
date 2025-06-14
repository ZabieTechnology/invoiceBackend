# api/gst_rates.py
from flask import Blueprint, request, jsonify, session, current_app
import logging
from bson import ObjectId
import re
from datetime import datetime # Ensure datetime is imported for DAL if needed there

# Import DAL functions for GST rates
from db.gst_rate_dal import (
    create_gst_rate,
    get_gst_rate_by_id,
    get_all_gst_rates,
    update_gst_rate,
    delete_gst_rate_by_id,
    get_gst_tds_setting,
    update_gst_tds_setting
)
# Import the DAL function for ca_tax entries if still used here, or remove if not
from db.ca_tax_dal import get_all_ca_tax_entries, manage_ca_tax_entries_for_gst_rate, delete_ca_tax_entries_by_original_id

# Import utility to get DB instance
from db.database import get_db

gst_rates_bp = Blueprint(
    'gst_rates_bp',
    __name__,
    url_prefix='/api/gst-rates'
)

logging.basicConfig(level=logging.INFO)

# Placeholder functions - replace with your actual implementation
def get_current_user():
    return session.get('username', 'System_User_Placeholder')

def get_current_tenant_id():
    return session.get('tenant_id', 'default_tenant')


@gst_rates_bp.route('', methods=['POST'])
def handle_create_gst_rate():
    data = request.get_json()
    if not data:
        return jsonify({"message": "No input data provided"}), 400
    if not data.get('taxName') or data.get('taxRate') is None or not data.get('head'):
        return jsonify({"message": "Missing required fields: Tax Name, Tax Rate, and Head"}), 400

    try:
        db = get_db()
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()

        gst_id = create_gst_rate(db_conn=db, gst_data=data, user=current_user, tenant_id=current_tenant)
        created_gst_rate = get_gst_rate_by_id(db_conn=db, gst_id=str(gst_id), tenant_id=current_tenant)

        if created_gst_rate:
            created_gst_rate['_id'] = str(created_gst_rate['_id'])
            # Ensure related ObjectIds are stringified if they exist
            if created_gst_rate.get('originalGstRateId') and isinstance(created_gst_rate['originalGstRateId'], ObjectId):
                created_gst_rate['originalGstRateId'] = str(created_gst_rate['originalGstRateId'])
            return jsonify({"message": "GST rate created successfully", "data": created_gst_rate}), 201
        else:
            logging.warning(f"GST rate created with ID {gst_id}, but failed to retrieve for response.")
            return jsonify({"message": "GST rate created, but failed to retrieve."}), 201 # Or 200 with just ID
    except ValueError as ve:
        logging.warning(f"ValueError in handle_create_gst_rate: {ve}")
        return jsonify({"message": str(ve)}), 400
    except Exception as e:
        logging.error(f"Error in handle_create_gst_rate: {e}")
        current_app.logger.error(f"Error details in handle_create_gst_rate: {str(e)}")
        return jsonify({"message": "Failed to create GST rate", "error": str(e)}), 500

@gst_rates_bp.route('/<gst_id>', methods=['GET'])
def handle_get_gst_rate(gst_id):
    try:
        if not ObjectId.is_valid(gst_id):
            return jsonify({"message": "Invalid GST ID format"}), 400

        db = get_db()
        current_tenant = get_current_tenant_id()
        gst_rate = get_gst_rate_by_id(db_conn=db, gst_id=gst_id, tenant_id=current_tenant)

        if gst_rate:
            gst_rate['_id'] = str(gst_rate['_id'])
            if gst_rate.get('originalGstRateId') and isinstance(gst_rate['originalGstRateId'], ObjectId):
                gst_rate['originalGstRateId'] = str(gst_rate['originalGstRateId'])
            return jsonify(gst_rate), 200
        else:
            return jsonify({"message": "GST rate not found"}), 404
    except Exception as e:
        logging.error(f"Error fetching GST rate {gst_id}: {e}")
        current_app.logger.error(f"Error details in handle_get_gst_rate for ID {gst_id}: {str(e)}")
        return jsonify({"message": "Failed to fetch GST rate", "error": str(e)}), 500

@gst_rates_bp.route('', methods=['GET'])
def handle_get_all_api_gst_rates():
    try:
        db = get_db()
        current_tenant = get_current_tenant_id()

        page_str = request.args.get("page", "1")
        limit_str = request.args.get("limit", "10") # Default to 10 as per user's previous code

        page = int(page_str) if page_str.isdigit() else 1
        limit = int(limit_str) if limit_str.isdigit() else 10 # Default to 10
        if limit == -1: # Allow fetching all if limit is -1
            pass
        elif limit < 1 : limit = 1
        if limit > 200 and limit != -1: limit = 200

        search_term = request.args.get("search", None)
        # The frontend sends `accountType` for bank accounts, but for GST rates,
        # it might send `head` or nothing if it wants all 'output' taxes.
        # Let's check for a 'head' filter specifically for GST rates.
        head_filter_value = request.args.get("head", None)


        filters = {}
        if search_term:
            regex_query = {"$regex": re.escape(search_term), "$options": "i"}
            filters["$or"] = [
                {"taxName": regex_query},
                {"head": regex_query},
            ]

        if head_filter_value:
            # If frontend sends "Output", DAL should handle regex for "output" if needed
            filters["head"] = head_filter_value
            # Example: if you need case-insensitive partial match for head:
            # filters["head"] = {"$regex": re.escape(head_filter_value), "$options": "i"}


        gst_rate_list, total_items = get_all_gst_rates(
            db_conn=db,
            page=page,
            limit=limit,
            filters=filters,
            tenant_id=current_tenant
        )

        result = []
        for item in gst_rate_list:
            item['_id'] = str(item['_id'])
            if item.get('originalGstRateId') and isinstance(item['originalGstRateId'], ObjectId):
                item['originalGstRateId'] = str(item['originalGstRateId'])
            result.append(item)

        response_data = {
            "data": result,
            "total": total_items,
            "page": page,
            "limit": limit if limit > 0 else total_items,
        }
        if limit > 0 and total_items > 0 :
             response_data["totalPages"] = (total_items + limit - 1) // limit
        elif total_items > 0 and limit == -1:
             response_data["totalPages"] = 1
        else:
             response_data["totalPages"] = 0 if total_items == 0 else 1

        return jsonify(response_data), 200
    except ValueError:
         return jsonify({"message": "Invalid page or limit parameter."}), 400
    except Exception as e:
        logging.error(f"Error fetching all GST rates: {e}")
        current_app.logger.error(f"Error details in handle_get_all_api_gst_rates: {str(e)}")
        return jsonify({"message": "Failed to fetch GST rates", "error": str(e)}), 500

@gst_rates_bp.route('/<gst_id>', methods=['PUT'])
def handle_update_gst_rate(gst_id):
    data = request.get_json()
    if not data:
        return jsonify({"message": "No input data provided"}), 400
    if not ObjectId.is_valid(gst_id):
        return jsonify({"message": "Invalid GST ID format"}), 400
    # Ensure required fields for update are present if they are being changed
    # For example, if taxName and taxRate are always expected for an update:
    # if not data.get('taxName') or data.get('taxRate') is None or not data.get('head'):
    #     return jsonify({"message": "Missing required fields for update: Tax Name, Tax Rate, and Head"}), 400

    try:
        db = get_db()
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()

        matched_count = update_gst_rate(db_conn=db, gst_id=gst_id, update_data=data, user=current_user, tenant_id=current_tenant)
        if matched_count == 0:
            return jsonify({"message": "GST rate not found or no changes made"}), 404

        updated_gst_rate = get_gst_rate_by_id(db_conn=db, gst_id=gst_id, tenant_id=current_tenant)
        if updated_gst_rate:
            updated_gst_rate['_id'] = str(updated_gst_rate['_id'])
            if updated_gst_rate.get('originalGstRateId') and isinstance(updated_gst_rate['originalGstRateId'], ObjectId):
                updated_gst_rate['originalGstRateId'] = str(updated_gst_rate['originalGstRateId'])
            return jsonify({"message": "GST rate updated successfully", "data": updated_gst_rate}), 200
        else:
            logging.error(f"CRITICAL: GST rate {gst_id} updated (matched_count: {matched_count}), but failed to retrieve.")
            return jsonify({"message": "GST rate updated, but failed to retrieve."}), 200 # Or 500 if this is critical
    except ValueError as ve:
        logging.warning(f"ValueError in handle_update_gst_rate for ID {gst_id}: {ve}")
        return jsonify({"message": str(ve)}), 400
    except Exception as e:
        logging.error(f"Error updating GST rate {gst_id}: {e}")
        current_app.logger.error(f"Error details in handle_update_gst_rate: {str(e)}")
        return jsonify({"message": "Failed to update GST rate", "error": str(e)}), 500

@gst_rates_bp.route('/<gst_id>', methods=['DELETE'])
def handle_delete_gst_rate(gst_id):
    try:
        if not ObjectId.is_valid(gst_id):
            return jsonify({"message": "Invalid GST ID format"}), 400

        db = get_db()
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()

        deleted_count = delete_gst_rate_by_id(db_conn=db, gst_id=gst_id, user=current_user, tenant_id=current_tenant)
        if deleted_count == 0:
            return jsonify({"message": "GST rate not found"}), 404
        return jsonify({"message": "GST rate deleted successfully"}), 200
    except ValueError as ve:
        logging.warning(f"ValueError in handle_delete_gst_rate for ID {gst_id}: {ve}")
        return jsonify({"message": str(ve)}), 400
    except Exception as e:
        logging.error(f"Error deleting GST rate {gst_id}: {e}")
        current_app.logger.error(f"Error details in handle_delete_gst_rate: {str(e)}")
        return jsonify({"message": "Failed to delete GST rate", "error": str(e)}), 500

# --- New Endpoint for Derived CA Tax Accounts ---
# This endpoint seems to belong more to ca_tax_api.py if it exists,
# but keeping it here as per user's provided file structure.
@gst_rates_bp.route('/derived-tax-accounts', methods=['GET'])
def handle_get_derived_tax_accounts():
    try:
        db = get_db()
        current_tenant = get_current_tenant_id() # Assuming tenant_id is needed for ca_tax_entries

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

        # Pass tenant_id to the DAL function if it supports it
        derived_tax_list, total_items = get_all_ca_tax_entries(db_conn=db, page=page, limit=limit, filters=filters, tenant_id=current_tenant)

        result = []
        for item in derived_tax_list:
            item['_id'] = str(item['_id'])
            if 'originalGstRateId' in item and isinstance(item['originalGstRateId'], ObjectId):
                item['originalGstRateId'] = str(item['originalGstRateId'])
            result.append(item)

        response_data = {
            "data": result,
            "total": total_items,
            "page": page,
            "limit": limit if limit > 0 else total_items,
        }
        if limit > 0 and total_items > 0 :
             response_data["totalPages"] = (total_items + limit - 1) // limit
        elif total_items > 0 and limit == -1:
             response_data["totalPages"] = 1
        else:
             response_data["totalPages"] = 0 if total_items == 0 else 1

        return jsonify(response_data), 200
    except ValueError:
         return jsonify({"message": "Invalid page or limit parameter for derived tax accounts."}), 400
    except Exception as e:
        logging.error(f"Error fetching all derived tax accounts: {e}")
        current_app.logger.error(f"Error details in handle_get_derived_tax_accounts: {str(e)}")
        return jsonify({"message": "Failed to fetch derived tax accounts", "error": str(e)}), 500

# --- GST TDS Setting Routes ---
@gst_rates_bp.route('/settings/gst-tds', methods=['GET'])
def handle_get_gst_tds_setting_route():
    try:
        db = get_db()
        current_tenant = get_current_tenant_id()
        setting = get_gst_tds_setting(db_conn=db, tenant_id=current_tenant)
        return jsonify({"gstTdsApplicable": setting}), 200
    except Exception as e:
        logging.error(f"Error fetching GST TDS setting: {e}")
        current_app.logger.error(f"Error details in handle_get_gst_tds_setting_route: {str(e)}")
        return jsonify({"message": "Failed to fetch GST TDS setting", "error": str(e)}), 500

@gst_rates_bp.route('/settings/gst-tds', methods=['PUT'])
def handle_update_gst_tds_setting_route():
    data = request.get_json()
    if data is None or 'gstTdsApplicable' not in data:
        return jsonify({"message": "Missing 'gstTdsApplicable' field"}), 400

    is_applicable_str = data.get('gstTdsApplicable')
    # Ensure boolean conversion is robust
    is_applicable_bool = str(is_applicable_str).lower() == 'yes' if isinstance(is_applicable_str, str) else bool(is_applicable_str)


    try:
        db = get_db()
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()
        success = update_gst_tds_setting(db_conn=db, is_applicable=is_applicable_bool, user=current_user, tenant_id=current_tenant)
        if success:
            return jsonify({"message": "GST TDS setting updated successfully", "gstTdsApplicable": "Yes" if is_applicable_bool else "No"}), 200
        else:
            # This case might mean the setting was already in the desired state, or an upsert didn't modify
            return jsonify({"message": "GST TDS setting not changed or update failed at DAL level."}), 200 # Or 400/500 if it's an error
    except Exception as e:
        logging.error(f"Error updating GST TDS setting via API: {e}")
        current_app.logger.error(f"Error details in handle_update_gst_tds_setting_route: {str(e)}")
        return jsonify({"message": "An internal error occurred while updating GST TDS setting", "error": str(e)}), 500

