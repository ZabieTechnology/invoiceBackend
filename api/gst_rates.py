# api/gst_rates.py
from flask import Blueprint, request, jsonify, session, current_app
import logging
from bson import ObjectId
import re
from datetime import datetime
import traceback # Import the traceback module

from db.gst_rate_dal import (
    create_gst_rate,
    get_gst_rate_by_id,
    get_all_gst_rates,
    update_gst_rate,
    delete_gst_rate_by_id
)
from db.database import get_db

gst_rates_bp = Blueprint(
    'gst_rates_bp',
    __name__,
    url_prefix='/api/gst-rates'
)

logging.basicConfig(level=logging.INFO)

def get_current_user():
    return session.get('username', 'System_User_Placeholder')

def get_current_tenant_id():
    return session.get('tenant_id', 'default_tenant')

def serialize_doc(doc):
    """
    Robustly serializes a MongoDB document by converting ObjectId and datetime
    objects to strings.
    """
    if not doc:
        return None

    serialized = {}
    for key, value in doc.items():
        if isinstance(value, ObjectId):
            serialized[key] = str(value)
        elif isinstance(value, datetime):
            # Convert datetime to ISO 8601 format string
            serialized[key] = value.isoformat()
        else:
            serialized[key] = value
    return serialized

@gst_rates_bp.route('', methods=['POST'])
def handle_create_gst_rate():
    data = request.get_json()
    if not data:
        return jsonify({"message": "No input data provided"}), 400
    if not data.get('taxName') or data.get('taxRate') is None or not data.get('head'):
        return jsonify({"message": "Missing required fields: Tax Name, Tax Rate, and Head"}), 400

    try:
        db = get_db()
        gst_id = create_gst_rate(db, data, user=get_current_user(), tenant_id=get_current_tenant_id())
        created_gst_rate = get_gst_rate_by_id(db, str(gst_id), tenant_id=get_current_tenant_id())
        return jsonify({"message": "GST rate created successfully", "data": serialize_doc(created_gst_rate)}), 201
    except Exception as e:
        logging.error(f"Error in handle_create_gst_rate: {e}")
        return jsonify({"message": "Failed to create GST rate", "error": str(e)}), 500

@gst_rates_bp.route('/<gst_id>', methods=['GET'])
def handle_get_gst_rate(gst_id):
    try:
        if not ObjectId.is_valid(gst_id):
            return jsonify({"message": "Invalid GST ID format"}), 400

        db = get_db()
        gst_rate = get_gst_rate_by_id(db, gst_id, tenant_id=get_current_tenant_id())

        if gst_rate:
            return jsonify(serialize_doc(gst_rate)), 200
        else:
            return jsonify({"message": "GST rate not found"}), 404
    except Exception as e:
        logging.error(f"Error fetching GST rate {gst_id}: {e}")
        return jsonify({"message": "Failed to fetch GST rate", "error": str(e)}), 500

@gst_rates_bp.route('', methods=['GET'])
def handle_get_all_api_gst_rates():
    try:
        db = get_db()
        page = int(request.args.get("page", 1))
        limit_str = request.args.get("limit", "10")
        limit = int(limit_str) if limit_str.isdigit() and int(limit_str) != 0 else -1
        search_term = request.args.get("search", None)
        head_filter = request.args.get("head", None)

        filters = {}
        if search_term:
            regex_query = {"$regex": re.escape(search_term), "$options": "i"}
            filters["$or"] = [{"taxName": regex_query}, {"head": regex_query}]
        if head_filter:
            filters["head"] = head_filter

        gst_rate_list, total_items = get_all_gst_rates(db, page, limit, filters, tenant_id=get_current_tenant_id())
        result = [serialize_doc(item) for item in gst_rate_list]

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
        return jsonify({"message": "Failed to fetch GST rates", "error": str(e)}), 500

@gst_rates_bp.route('/<gst_id>', methods=['PUT'])
def handle_update_gst_rate(gst_id):
    data = request.get_json()
    if not data:
        return jsonify({"message": "No input data provided"}), 400
    if not ObjectId.is_valid(gst_id):
        return jsonify({"message": "Invalid GST ID format"}), 400

    current_app.logger.info(f"Attempting to update GST rate {gst_id} with data: {data}")

    try:
        db = get_db()

        # Directly call the update function
        matched_count = update_gst_rate(db, gst_id, data, user=get_current_user(), tenant_id=get_current_tenant_id())

        if matched_count > 0:
            # If update was successful, fetch the updated document to return
            updated_gst_rate = get_gst_rate_by_id(db, gst_id, tenant_id=get_current_tenant_id())
            if updated_gst_rate:
                return jsonify({"message": "GST rate updated successfully", "data": serialize_doc(updated_gst_rate)}), 200
            else:
                # This case is unlikely but handled for safety
                current_app.logger.error(f"Update for GST rate {gst_id} succeeded, but retrieval failed.")
                return jsonify({"message": "Update succeeded, but failed to retrieve the updated record."}), 500
        else:
            return jsonify({"message": "GST rate not found or no changes made"}), 404

    except Exception as e:
        current_app.logger.error(f"An exception occurred while updating GST rate {gst_id}: {e}")
        current_app.logger.error(traceback.format_exc())
        return jsonify({"message": "Failed to update GST rate", "error": str(e)}), 500

@gst_rates_bp.route('/<gst_id>', methods=['DELETE'])
def handle_delete_gst_rate(gst_id):
    try:
        if not ObjectId.is_valid(gst_id):
            return jsonify({"message": "Invalid GST ID format"}), 400

        db = get_db()
        deleted_count = delete_gst_rate_by_id(db, gst_id, user=get_current_user(), tenant_id=get_current_tenant_id())

        if deleted_count == 0:
            return jsonify({"message": "GST rate not found"}), 404

        return jsonify({"message": "GST rate deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error deleting GST rate {gst_id}: {e}")
        return jsonify({"message": "Failed to delete GST rate", "error": str(e)}), 500
