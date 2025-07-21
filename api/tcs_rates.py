# api/tcs_rates.py
from flask import Blueprint, request, jsonify, session
import logging
from bson import ObjectId
from datetime import datetime
import re

from db.tcs_rates_dal import (
    create_tcs_rate,
    get_all_tcs_rates,
    delete_tcs_rate_by_id
)
from db.database import get_db

tcs_rates_bp = Blueprint(
    'tcs_rates_bp',
    __name__,
    url_prefix='/api/tcs-rates'
)

logging.basicConfig(level=logging.INFO)

def get_current_user():
    return session.get('username', 'System_User_Placeholder')

def get_current_tenant_id():
    return session.get('tenant_id', 'default_tenant_placeholder')

@tcs_rates_bp.route('', methods=['POST'])
def handle_create_tcs_rate():
    """Handles POST requests to create a new TCS rate."""
    data = request.get_json()
    if not data:
        return jsonify({"message": "No JSON data provided"}), 400

    required_fields = ['natureOfCollection', 'section', 'threshold', 'tcsRate', 'tcsRateNoPan', 'effectiveDate']
    if not all(field in data and data[field] != '' for field in required_fields):
        return jsonify({"message": "Missing required fields"}), 400

    try:
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()
        db = get_db()
        create_tcs_rate(db, data, user=current_user, tenant_id=current_tenant)
        return jsonify({"message": "TCS rate created successfully"}), 201
    except Exception as e:
        logging.error(f"Error in handle_create_tcs_rate: {e}")
        return jsonify({"message": "Failed to create TCS rate", "error": str(e)}), 500

@tcs_rates_bp.route('', methods=['GET'])
def handle_get_all_tcs_rates():
    """
    Handles GET requests for all TCS rates.
    If no rates exist for the tenant, it seeds the database with default values.
    """
    try:
        limit = int(request.args.get("limit", "25"))
        current_tenant = get_current_tenant_id()
        current_user = get_current_user()
        db = get_db()

        _, total_items = get_all_tcs_rates(db, 1, 1, tenant_id=current_tenant)

        if total_items == 0:
            logging.info(f"No TCS rates found for tenant {current_tenant}. Seeding default rates.")
            default_tcs_rates = [
                {'natureOfCollection': 'Sale of Goods', 'section': '206C(1H)', 'threshold': 5000000, 'tcsRate': 0.1, 'tcsRateNoPan': 1, 'effectiveDate': '2024-04-01'},
                {'natureOfCollection': 'Sale of Motor Vehicle', 'section': '206C(1F)', 'threshold': 1000000, 'tcsRate': 1, 'tcsRateNoPan': 5, 'effectiveDate': '2024-04-01'},
                {'natureOfCollection': 'LRS - Overseas tour package', 'section': '206C(1G)', 'threshold': 0, 'tcsRate': 20, 'tcsRateNoPan': 40, 'effectiveDate': '2024-04-01'},
                {'natureOfCollection': 'LRS - Other purposes', 'section': '206C(1G)', 'threshold': 700000, 'tcsRate': 20, 'tcsRateNoPan': 40, 'effectiveDate': '2024-04-01'},
                {'natureOfCollection': 'Sale of Scrap', 'section': '206C', 'threshold': 0, 'tcsRate': 1, 'tcsRateNoPan': 5, 'effectiveDate': '2024-04-01'},
            ]
            for rate_data in default_tcs_rates:
                create_tcs_rate(db, rate_data, user=current_user, tenant_id=current_tenant)

        rates_list, total_items = get_all_tcs_rates(db, 1, limit, tenant_id=current_tenant)
        result = []
        for item in rates_list:
            item['_id'] = str(item['_id'])
            if 'effectiveDate' in item and isinstance(item['effectiveDate'], datetime):
                item['effectiveDate'] = item['effectiveDate'].isoformat()
            result.append(item)

        return jsonify({"data": result, "total": total_items}), 200
    except Exception as e:
        logging.error(f"Error in handle_get_all_tcs_rates: {e}")
        return jsonify({"message": "Failed to fetch TCS rates", "error": str(e)}), 500

@tcs_rates_bp.route('/<rate_id>', methods=['DELETE'])
def handle_delete_tcs_rate(rate_id):
    """Handles DELETE requests for a TCS rate."""
    if not ObjectId.is_valid(rate_id):
        return jsonify({"message": "Invalid TCS rate ID format"}), 400
    try:
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()
        db = get_db()
        deleted_count = delete_tcs_rate_by_id(db, rate_id, user=current_user, tenant_id=current_tenant)
        if deleted_count == 0:
            return jsonify({"message": "TCS rate not found"}), 404
        return jsonify({"message": "TCS rate deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error in handle_delete_tcs_rate for ID {rate_id}: {e}")
        return jsonify({"message": "Failed to delete TCS rate", "error": str(e)}), 500
