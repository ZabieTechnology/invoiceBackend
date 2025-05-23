# api/chart_of_accounts.py
from flask import Blueprint, request, jsonify, session
import logging
from bson import ObjectId
import re
from datetime import datetime # Ensure datetime is imported

from db.chart_of_accounts_dal import (
    create_account,
    get_account_by_id,
    get_all_accounts,
    update_account,
    delete_account_by_id
)
# Assuming activity log is handled within DALs, or import if specific API logging needed

chart_of_accounts_bp = Blueprint(
    'chart_of_accounts_bp',
    __name__,
    url_prefix='/api/chart-of-accounts'
)

logging.basicConfig(level=logging.INFO)

# Placeholder: Implement these based on your authentication/session management
def get_current_user():
    return session.get('username', 'System_User_Placeholder')

def get_current_tenant_id():
    return session.get('tenant_id', 'default_tenant_placeholder')


@chart_of_accounts_bp.route('', methods=['POST'])
def handle_create_account():
    data = request.get_json()
    if not data:
        return jsonify({"message": "No input data provided"}), 400

    # Required fields validation (Tax - defaultGstRateId is NOT mandatory here)
    if not data.get('accountType') or not data.get('code') or not data.get('name'):
        return jsonify({"message": "Missing required fields: Account Type, Code, and Name"}), 400

    # Pre-process ObjectId fields: if an empty string is sent from frontend, convert to None
    # This prevents ObjectId("") error in the DAL if the field is optional but present as empty.
    if 'defaultGstRateId' in data and data['defaultGstRateId'] == "":
        data['defaultGstRateId'] = None
    if 'subAccountOf' in data and data['subAccountOf'] == "":
        data['subAccountOf'] = None

    # Validation for subAccountOf if isSubAccount is true
    if data.get('isSubAccount') and not data.get('subAccountOf'): # Check after potential conversion to None
        return jsonify({"message": "Sub-account Of is required if 'Is Sub-Account' is checked."}), 400

    try:
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()

        account_id = create_account(data, user=current_user, tenant_id=current_tenant)

        created_account = get_account_by_id(str(account_id), tenant_id=current_tenant)
        if created_account:
            created_account['_id'] = str(created_account['_id'])
            if created_account.get('balanceAsOf') and isinstance(created_account['balanceAsOf'], datetime):
                created_account['balanceAsOf'] = created_account['balanceAsOf'].strftime('%Y-%m-%d')
            if created_account.get('defaultGstRateId') and isinstance(created_account['defaultGstRateId'], ObjectId):
                created_account['defaultGstRateId'] = str(created_account['defaultGstRateId'])
            if created_account.get('subAccountOf') and isinstance(created_account['subAccountOf'], ObjectId):
                created_account['subAccountOf'] = str(created_account['subAccountOf'])

            return jsonify({"message": "Account created successfully", "data": created_account}), 201
        else:
            return jsonify({"message": "Account created, but failed to retrieve."}), 201
    except Exception as e:
        logging.error(f"Error in handle_create_account: {e}")
        return jsonify({"message": f"Failed to create account: {str(e)}"}), 500

@chart_of_accounts_bp.route('/<account_id>', methods=['GET'])
def handle_get_account(account_id):
    try:
        if not ObjectId.is_valid(account_id):
            return jsonify({"message": "Invalid account ID format"}), 400
        current_tenant = get_current_tenant_id()
        account = get_account_by_id(account_id, tenant_id=current_tenant)
        if account:
            account['_id'] = str(account['_id'])
            if account.get('balanceAsOf') and isinstance(account['balanceAsOf'], datetime):
                account['balanceAsOf'] = account['balanceAsOf'].strftime('%Y-%m-%d')
            if account.get('defaultGstRateId') and isinstance(account['defaultGstRateId'], ObjectId):
                account['defaultGstRateId'] = str(account['defaultGstRateId'])
            if account.get('subAccountOf') and isinstance(account['subAccountOf'], ObjectId):
                account['subAccountOf'] = str(account['subAccountOf'])
            return jsonify(account), 200
        else:
            return jsonify({"message": "Account not found"}), 404
    except Exception as e:
        logging.error(f"Error fetching account {account_id}: {e}")
        return jsonify({"message": "Failed to fetch account"}), 500

@chart_of_accounts_bp.route('', methods=['GET'])
def handle_get_all_chart_of_accounts():
    try:
        page = int(request.args.get("page", 1))
        limit_str = request.args.get("limit", "10")
        limit = int(limit_str) if limit_str.isdigit() and int(limit_str) != 0 else -1
        current_tenant = get_current_tenant_id()
        search_term = request.args.get("search", None)
        category_filter = request.args.get("category", None)

        filters = {}
        if search_term:
            regex_query = {"$regex": re.escape(search_term), "$options": "i"}
            filters["$or"] = [
                {"name": regex_query}, {"code": regex_query},
                {"description": regex_query}, {"accountType": regex_query}
            ]

        if category_filter and category_filter.lower() != "all accounts" and category_filter.lower() != "inactive" and category_filter.lower() != "tax":
            filters["accountType"] = category_filter
        elif category_filter and category_filter.lower() == "inactive":
            filters["status"] = "Inactive"
        elif category_filter and category_filter.lower() == "all accounts":
            filters["status"] = {"$ne": "Inactive"}

        account_list, total_items = get_all_accounts(page, limit, filters, tenant_id=current_tenant)

        result = []
        for item in account_list:
            item['_id'] = str(item['_id'])
            if item.get('balanceAsOf') and isinstance(item['balanceAsOf'], datetime):
                item['balanceAsOf'] = item['balanceAsOf'].strftime('%Y-%m-%d')
            if item.get('defaultGstRateId') and isinstance(item['defaultGstRateId'], ObjectId):
                item['defaultGstRateId'] = str(item['defaultGstRateId'])
            if item.get('subAccountOf') and isinstance(item['subAccountOf'], ObjectId):
                item['subAccountOf'] = str(item['subAccountOf'])
            result.append(item)

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

    # Required fields check (Tax - defaultGstRateId is NOT mandatory here)
    if not data.get('accountType') or not data.get('code') or not data.get('name'):
        return jsonify({"message": "Missing required fields: Account Type, Code, and Name"}), 400

    # Pre-process ObjectId fields
    if 'defaultGstRateId' in data and data['defaultGstRateId'] == "":
        data['defaultGstRateId'] = None
    if 'subAccountOf' in data and data['subAccountOf'] == "":
        data['subAccountOf'] = None

    if data.get('isSubAccount') and not data.get('subAccountOf'): # Check after potential conversion to None
        return jsonify({"message": "Sub-account Of is required if 'Is Sub-Account' is checked."}), 400

    try:
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()
        matched_count = update_account(account_id, data, user=current_user, tenant_id=current_tenant)
        if matched_count == 0: return jsonify({"message": "Account not found or no changes made"}), 404

        updated_account = get_account_by_id(account_id, tenant_id=current_tenant)
        if updated_account:
            updated_account['_id'] = str(updated_account['_id'])
            if updated_account.get('balanceAsOf') and isinstance(updated_account['balanceAsOf'], datetime):
                updated_account['balanceAsOf'] = updated_account['balanceAsOf'].strftime('%Y-%m-%d')
            if updated_account.get('defaultGstRateId') and isinstance(updated_account['defaultGstRateId'], ObjectId):
                updated_account['defaultGstRateId'] = str(updated_account['defaultGstRateId'])
            if updated_account.get('subAccountOf') and isinstance(updated_account['subAccountOf'], ObjectId):
                updated_account['subAccountOf'] = str(updated_account['subAccountOf'])
            return jsonify({"message": "Account updated successfully", "data": updated_account}), 200
        else:
            return jsonify({"message": "Account updated, but failed to retrieve."}), 200
    except Exception as e:
        logging.error(f"Error updating account {account_id}: {e}")
        return jsonify({"message": f"Failed to update account: {str(e)}"}), 500

@chart_of_accounts_bp.route('/<account_id>', methods=['DELETE'])
def handle_delete_account(account_id):
    try:
        if not ObjectId.is_valid(account_id): return jsonify({"message": "Invalid account ID format"}), 400
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()
        deleted_count = delete_account_by_id(account_id, user=current_user, tenant_id=current_tenant)
        if deleted_count == 0: return jsonify({"message": "Account not found"}), 404
        return jsonify({"message": "Account deleted successfully"}), 200
    except ValueError as ve:
        return jsonify({"message": str(ve)}), 400
    except Exception as e:
        logging.error(f"Error deleting account {account_id}: {e}")
        return jsonify({"message": "Failed to delete account"}), 500

