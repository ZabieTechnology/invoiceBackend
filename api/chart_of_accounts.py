# api/chart_of_accounts.py
from flask import Blueprint, request, jsonify, session
import logging
from bson import ObjectId
import re
from datetime import datetime

from db.chart_of_accounts_dal import (
    create_account,
    get_account_by_id,
    get_all_accounts,
    update_account,
    delete_account_by_id
)
from db.database import get_db


chart_of_accounts_bp = Blueprint(
    'chart_of_accounts_bp',
    __name__,
    url_prefix='/api/chart-of-accounts'
)

logging.basicConfig(level=logging.INFO)

def get_current_user():
    return session.get('username', 'System_User_Placeholder')

def get_current_tenant_id():
    return session.get('tenant_id', 'default_tenant_placeholder')

def serialize_doc(doc):
    """ Helper to serialize MongoDB doc, converting ObjectId and datetime. """
    if not doc:
        return None
    doc['_id'] = str(doc['_id'])
    if doc.get('balanceAsOf') and isinstance(doc['balanceAsOf'], datetime):
        doc['balanceAsOf'] = doc['balanceAsOf'].strftime('%Y-%m-%d')
    if doc.get('defaultGstRateId') and isinstance(doc['defaultGstRateId'], ObjectId):
        doc['defaultGstRateId'] = str(doc['defaultGstRateId'])
    if doc.get('subAccountOf') and isinstance(doc['subAccountOf'], ObjectId):
        doc['subAccountOf'] = str(doc['subAccountOf'])
    return doc


@chart_of_accounts_bp.route('', methods=['POST'])
def handle_create_account():
    data = request.get_json()
    if not data:
        return jsonify({"message": "No input data provided"}), 400

    if not data.get('nature') or not data.get('mainHead') or not data.get('code') or not data.get('name'):
        return jsonify({"message": "Missing required fields: Nature, Main Head, Code, and Name"}), 400

    if 'defaultGstRateId' in data and data['defaultGstRateId'] == "":
        data['defaultGstRateId'] = None
    if 'subAccountOf' in data and data['subAccountOf'] == "":
        data['subAccountOf'] = None

    if data.get('isSubAccount') and not data.get('subAccountOf'):
        return jsonify({"message": "Parent account is required for a sub-account."}), 400

    try:
        db = get_db()
        account_id = create_account(db, data, user=get_current_user(), tenant_id=get_current_tenant_id())
        created_account = get_account_by_id(db, str(account_id), tenant_id=get_current_tenant_id())

        return jsonify({"message": "Account created successfully", "data": serialize_doc(created_account)}), 201
    except Exception as e:
        logging.error(f"Error in handle_create_account: {e}")
        return jsonify({"message": f"Failed to create account: {str(e)}"}), 500

@chart_of_accounts_bp.route('/<account_id>', methods=['GET'])
def handle_get_account(account_id):
    try:
        if not ObjectId.is_valid(account_id):
            return jsonify({"message": "Invalid account ID format"}), 400

        db = get_db()
        account = get_account_by_id(db, account_id, tenant_id=get_current_tenant_id())
        if account:
            return jsonify(serialize_doc(account)), 200
        else:
            return jsonify({"message": "Account not found"}), 404
    except Exception as e:
        logging.error(f"Error fetching account {account_id}: {e}")
        return jsonify({"message": "Failed to fetch account"}), 500

@chart_of_accounts_bp.route('', methods=['GET'])
def handle_get_all_chart_of_accounts():
    try:
        # --- CHANGES START HERE ---
        # Add logging to see what arguments the backend is receiving
        logging.info(f"Received request args: {request.args}")
        # --- CHANGES END HERE ---

        page = int(request.args.get("page", 1))
        limit_str = request.args.get("limit", "10")
        limit = int(limit_str) if limit_str.isdigit() and int(limit_str) != 0 else -1
        search_term = request.args.get("search", None)
        gst_enabled_filter = request.args.get("enabledOptions.GST", None)

        filters = {}

        if search_term:
            regex_query = {"$regex": re.escape(search_term), "$options": "i"}
            filters["$or"] = [
                {"name": regex_query}, {"code": regex_query},
                {"description": regex_query}, {"nature": regex_query},
                {"mainHead": regex_query}, {"category": regex_query}
            ]

        if gst_enabled_filter is not None:
            filters["enabledOptions.GST"] = gst_enabled_filter.lower() == 'true'

        # --- CHANGES START HERE ---
        # Add logging to see the final constructed filter before querying the DB
        logging.info(f"Constructed MongoDB filter: {filters}")
        # --- CHANGES END HERE ---

        db = get_db()
        account_list, total_items = get_all_accounts(db, page, limit, filters, tenant_id=get_current_tenant_id())

        result = [serialize_doc(item) for item in account_list]

        return jsonify({
            "data": result, "total": total_items, "page": page,
            "limit": limit if limit > 0 else total_items,
            "totalPages": (total_items + limit - 1) // limit if limit > 0 and total_items > 0 else 1
        }), 200
    except ValueError:
         return jsonify({"message": "Invalid page or limit parameter."}), 400
    except Exception as e:
        logging.error(f"Error fetching all chart of accounts: {e}")
        return jsonify({"message": "Failed to fetch accounts"}), 500

@chart_of_accounts_bp.route('/<account_id>', methods=['PUT'])
def handle_update_account(account_id):
    data = request.get_json()
    if not data: return jsonify({"message": "No input data provided"}), 400
    if not ObjectId.is_valid(account_id): return jsonify({"message": "Invalid account ID format"}), 400

    if not data.get('nature') or not data.get('mainHead') or not data.get('code') or not data.get('name'):
        return jsonify({"message": "Missing required fields: Nature, Main Head, Code, and Name"}), 400

    if 'defaultGstRateId' in data and data['defaultGstRateId'] == "":
        data['defaultGstRateId'] = None
    if 'subAccountOf' in data and data['subAccountOf'] == "":
        data['subAccountOf'] = None

    if data.get('isSubAccount') and not data.get('subAccountOf'):
        return jsonify({"message": "Parent account is required for a sub-account."}), 400

    try:
        db = get_db()
        matched_count = update_account(db, account_id, data, user=get_current_user(), tenant_id=get_current_tenant_id())
        if matched_count == 0: return jsonify({"message": "Account not found or no changes made"}), 404

        updated_account = get_account_by_id(db, account_id, tenant_id=get_current_tenant_id())
        return jsonify({"message": "Account updated successfully", "data": serialize_doc(updated_account)}), 200
    except Exception as e:
        logging.error(f"Error updating account {account_id}: {e}")
        return jsonify({"message": f"Failed to update account: {str(e)}"}), 500

@chart_of_accounts_bp.route('/<account_id>', methods=['DELETE'])
def handle_delete_account(account_id):
    try:
        if not ObjectId.is_valid(account_id): return jsonify({"message": "Invalid account ID format"}), 400

        db = get_db()
        deleted_count = delete_account_by_id(db, account_id, user=get_current_user(), tenant_id=get_current_tenant_id())
        if deleted_count == 0: return jsonify({"message": "Account not found"}), 404
        return jsonify({"message": "Account deleted successfully"}), 200
    except ValueError as ve:
        return jsonify({"message": str(ve)}), 400
    except Exception as e:
        logging.error(f"Error deleting account {account_id}: {e}")
        return jsonify({"message": "Failed to delete account"}), 500
