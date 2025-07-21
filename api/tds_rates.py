# api/tds_rates.py
from flask import Blueprint, request, jsonify, session, current_app
import logging
from bson import ObjectId
from datetime import datetime
import re

# Import DAL functions and db utility
from db.tds_rates_dal import (
    create_tds_rate,
    get_tds_rate_by_id,
    get_all_tds_rates,
    update_tds_rate,
    delete_tds_rate_by_id
)
from db.database import get_db # Assuming you have this utility

tds_rates_bp = Blueprint(
    'tds_rates_bp',
    __name__,
    url_prefix='/api/tds-rates'
)

logging.basicConfig(level=logging.INFO)

# Helper functions to get user and tenant from session
def get_current_user():
    return session.get('username', 'System_User_Placeholder')

def get_current_tenant_id():
    return session.get('tenant_id', 'default_tenant_placeholder')

@tds_rates_bp.route('', methods=['POST'])
def handle_create_tds_rate():
    """Handles POST requests to create a new TDS rate."""
    data = request.get_json()
    if not data:
        return jsonify({"message": "No JSON data provided"}), 400

    required_fields = ['natureOfPayment', 'section', 'threshold', 'tdsRate', 'tdsRateNoPan', 'effectiveDate']
    if not all(field in data and data[field] != '' for field in required_fields):
        return jsonify({"message": "Missing required fields"}), 400

    try:
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()
        db = get_db()

        rate_id = create_tds_rate(
            db_conn=db,
            tds_data=data,
            user=current_user,
            tenant_id=current_tenant
        )

        created_rate = get_tds_rate_by_id(db, str(rate_id), tenant_id=current_tenant)
        if created_rate:
            created_rate['_id'] = str(created_rate['_id'])
            if isinstance(created_rate.get('effectiveDate'), datetime):
                created_rate['effectiveDate'] = created_rate['effectiveDate'].isoformat()
            return jsonify({"message": "TDS rate created successfully", "data": created_rate}), 201
        else:
            return jsonify({"message": "TDS rate created, but failed to retrieve."}), 500
    except ValueError as ve:
        logging.warning(f"ValueError in handle_create_tds_rate: {ve}")
        return jsonify({"message": str(ve)}), 409 # Conflict
    except Exception as e:
        logging.error(f"Error in handle_create_tds_rate: {e}")
        return jsonify({"message": "Failed to create TDS rate", "error": str(e)}), 500

@tds_rates_bp.route('/<rate_id>', methods=['PUT'])
def handle_update_tds_rate(rate_id):
    """Handles PUT requests to update an existing TDS rate."""
    if not ObjectId.is_valid(rate_id):
        return jsonify({"message": "Invalid TDS rate ID format"}), 400

    data = request.get_json()
    if not data:
        return jsonify({"message": "No JSON data provided for update"}), 400

    try:
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()
        db = get_db()

        matched_count = update_tds_rate(db, rate_id, data, user=current_user, tenant_id=current_tenant)
        if matched_count == 0:
            return jsonify({"message": "TDS rate not found or no changes made"}), 404

        updated_rate = get_tds_rate_by_id(db, rate_id, tenant_id=current_tenant)
        if updated_rate:
            updated_rate['_id'] = str(updated_rate['_id'])
            if isinstance(updated_rate.get('effectiveDate'), datetime):
                updated_rate['effectiveDate'] = updated_rate['effectiveDate'].isoformat()
            return jsonify({"message": "TDS rate updated successfully", "data": updated_rate}), 200
        else:
            return jsonify({"message": "TDS rate updated, but failed to retrieve updated data."}), 500
    except ValueError as ve:
        logging.warning(f"ValueError in handle_update_tds_rate for ID {rate_id}: {ve}")
        return jsonify({"message": str(ve)}), 409
    except Exception as e:
        logging.error(f"Error in handle_update_tds_rate for ID {rate_id}: {e}")
        return jsonify({"message": "Failed to update TDS rate", "error": str(e)}), 500

@tds_rates_bp.route('/<rate_id>', methods=['GET'])
def handle_get_tds_rate(rate_id):
    """Handles GET requests for a single TDS rate."""
    if not ObjectId.is_valid(rate_id):
        return jsonify({"message": "Invalid TDS rate ID format"}), 400
    try:
        current_tenant = get_current_tenant_id()
        db = get_db()
        rate = get_tds_rate_by_id(db, rate_id, tenant_id=current_tenant)
        if rate:
            rate['_id'] = str(rate['_id'])
            if isinstance(rate.get('effectiveDate'), datetime):
                rate['effectiveDate'] = rate['effectiveDate'].isoformat()
            return jsonify(rate), 200
        else:
            return jsonify({"message": "TDS rate not found"}), 404
    except Exception as e:
        logging.error(f"Error in handle_get_tds_rate for ID {rate_id}: {e}")
        return jsonify({"message": "Failed to fetch TDS rate", "error": str(e)}), 500

@tds_rates_bp.route('', methods=['GET'])
def handle_get_all_tds_rates():
    """
    Handles GET requests for all TDS rates with pagination.
    If no rates exist for the tenant, it seeds the database with default values.
    """
    try:
        page = int(request.args.get("page", "1"))
        limit = int(request.args.get("limit", "25"))
        search_term = request.args.get("search", None)

        current_tenant = get_current_tenant_id()
        current_user = get_current_user()
        db = get_db()

        filters = {}
        if search_term:
            regex_query = {"$regex": re.escape(search_term), "$options": "i"}
            filters["$or"] = [
                {"natureOfPayment": regex_query},
                {"section": regex_query}
            ]

        # First, check if any documents exist
        _, total_items = get_all_tds_rates(db, 1, 1, filters, tenant_id=current_tenant)

        if total_items == 0 and not search_term:
            logging.info(f"No TDS rates found for tenant {current_tenant}. Seeding default rates.")
            # Define default rates based on Indian regulations for AY 2024-25
            default_tds_rates = [
                {'natureOfPayment': 'Payment to Contractors (Individual/HUF)', 'section': '194C', 'threshold': 30000, 'tdsRate': 1, 'tdsRateNoPan': 20, 'effectiveDate': '2024-04-01'},
                {'natureOfPayment': 'Payment to Contractors (Others)', 'section': '194C', 'threshold': 30000, 'tdsRate': 2, 'tdsRateNoPan': 20, 'effectiveDate': '2024-04-01'},
                {'natureOfPayment': 'Fees for Professional Services', 'section': '194J', 'threshold': 30000, 'tdsRate': 10, 'tdsRateNoPan': 20, 'effectiveDate': '2024-04-01'},
                {'natureOfPayment': 'Fees for Technical Services', 'section': '194J', 'threshold': 30000, 'tdsRate': 2, 'tdsRateNoPan': 20, 'effectiveDate': '2024-04-01'},
                {'natureOfPayment': 'Rent on Plant & Machinery', 'section': '194I', 'threshold': 240000, 'tdsRate': 2, 'tdsRateNoPan': 20, 'effectiveDate': '2024-04-01'},
                {'natureOfPayment': 'Rent on Land, Building, Furniture', 'section': '194I', 'threshold': 240000, 'tdsRate': 10, 'tdsRateNoPan': 20, 'effectiveDate': '2024-04-01'},
                {'natureOfPayment': 'Commission or Brokerage', 'section': '194H', 'threshold': 15000, 'tdsRate': 5, 'tdsRateNoPan': 20, 'effectiveDate': '2024-04-01'},
                {'natureOfPayment': 'Interest (other than on securities)', 'section': '194A', 'threshold': 40000, 'tdsRate': 10, 'tdsRateNoPan': 20, 'effectiveDate': '2024-04-01'},
                {'natureOfPayment': 'Purchase of Goods', 'section': '194Q', 'threshold': 5000000, 'tdsRate': 0.1, 'tdsRateNoPan': 5, 'effectiveDate': '2024-04-01'},
            ]

            for rate_data in default_tds_rates:
                try:
                    create_tds_rate(db, rate_data, user=current_user, tenant_id=current_tenant)
                except ValueError as ve:
                    # This might happen in a race condition, it's safe to ignore.
                    logging.warning(f"Skipping seeding for a rate that already exists: {ve}")

        # Fetch again after potential seeding
        rates_list, total_items = get_all_tds_rates(db, page, limit, filters, tenant_id=current_tenant)

        result = []
        for item in rates_list:
            item['_id'] = str(item['_id'])
            # Convert datetime back to string for JSON response
            if 'effectiveDate' in item and isinstance(item['effectiveDate'], datetime):
                item['effectiveDate'] = item['effectiveDate'].isoformat()
            result.append(item)

        total_pages = 0
        if total_items > 0:
            if limit == -1:
                total_pages = 1
            elif limit > 0:
                total_pages = (total_items + limit - 1) // limit

        response_data = {
            "data": result, "total": total_items,
            "page": page if limit != -1 else 1,
            "limit": limit if limit > 0 else total_items,
            "totalPages": total_pages
        }
        return jsonify(response_data), 200
    except ValueError:
         return jsonify({"message": "Invalid page or limit parameter. Must be integers."}), 400
    except Exception as e:
        logging.error(f"Error in handle_get_all_tds_rates: {e}")
        return jsonify({"message": "Failed to fetch TDS rates", "error": str(e)}), 500

@tds_rates_bp.route('/<rate_id>', methods=['DELETE'])
def handle_delete_tds_rate(rate_id):
    """Handles DELETE requests for a TDS rate."""
    if not ObjectId.is_valid(rate_id):
        return jsonify({"message": "Invalid TDS rate ID format"}), 400
    try:
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()
        db = get_db()

        deleted_count = delete_tds_rate_by_id(db, rate_id, user=current_user, tenant_id=current_tenant)
        if deleted_count == 0:
            return jsonify({"message": "TDS rate not found"}), 404
        return jsonify({"message": "TDS rate deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error in handle_delete_tds_rate for ID {rate_id}: {e}")
        return jsonify({"message": "Failed to delete TDS rate", "error": str(e)}), 500
