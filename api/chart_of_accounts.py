# api/chart_of_accounts.py
from flask import Blueprint, request, jsonify, session
import logging
from bson import ObjectId
import re
from datetime import datetime # Ensure datetime is imported

# Assuming your DAL functions are correctly defined in this path
from db.chart_of_accounts_dal import (
    create_account,
    get_account_by_id,
    get_all_accounts,
    update_account,
    delete_account_by_id
)
# Assuming get_db is correctly defined in this path
from db.database import get_db


chart_of_accounts_bp = Blueprint(
    'chart_of_accounts_bp',
    __name__,
    url_prefix='/api/chart-of-accounts'
)

logging.basicConfig(level=logging.INFO)

# Placeholder: Implement these based on your authentication/session management
def get_current_user():
    # Replace with your actual user retrieval logic
    return session.get('username', 'System_User_Placeholder')

def get_current_tenant_id():
    # Replace with your actual tenant ID retrieval logic
    return session.get('tenant_id', 'default_tenant_placeholder')


@chart_of_accounts_bp.route('', methods=['POST'])
def handle_create_account():
    data = request.get_json()
    if not data:
        return jsonify({"message": "No input data provided"}), 400

    if not data.get('accountType') or not data.get('code') or not data.get('name'):
        return jsonify({"message": "Missing required fields: Account Type, Code, and Name"}), 400

    if 'defaultGstRateId' in data and data['defaultGstRateId'] == "":
        data['defaultGstRateId'] = None
    if 'subAccountOf' in data and data['subAccountOf'] == "":
        data['subAccountOf'] = None

    if data.get('isSubAccount') and not data.get('subAccountOf'):
        return jsonify({"message": "Sub-account Of is required if 'Is Sub-Account' is checked."}), 400

    try:
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()
        db = get_db() # Get DB instance

        account_id = create_account(db, data, user=current_user, tenant_id=current_tenant) # Pass db

        created_account = get_account_by_id(db, str(account_id), tenant_id=current_tenant) # Pass db
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
        db = get_db() # Get DB instance
        account = get_account_by_id(db, account_id, tenant_id=current_tenant) # Pass db
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
        db = get_db() # Get DB instance

        search_term = request.args.get("search", None)
        # Corrected: Use 'accountType' to match frontend query parameter
        account_type_filter = request.args.get("accountType", None)
        # 'category' was used before, if you still need it for other purposes, add it separately
        # For now, focusing on 'accountType' for bank accounts.
        # category_filter = request.args.get("category", None)


        filters = {}
        if search_term:
            regex_query = {"$regex": re.escape(search_term), "$options": "i"}
            filters["$or"] = [
                {"name": regex_query}, {"code": regex_query},
                {"description": regex_query}, {"accountType": regex_query}
            ]

        # Apply accountType filter if provided
        if account_type_filter:
            filters["accountType"] = account_type_filter
            # If you were using 'category' for other specific filters like "Inactive", "All Accounts",
            # you would need to handle that logic separately or adjust how filters are combined.
            # For example, if 'category' is still sent for those:
            # category_specific_filter = request.args.get("category", None)
            # if category_specific_filter and category_specific_filter.lower() == "inactive":
            #     filters["status"] = "Inactive"
            # elif category_specific_filter and category_specific_filter.lower() == "all accounts":
            #     filters["status"] = {"$ne": "Inactive"}


        # Assuming get_all_accounts DAL function is updated to accept db connection first
        account_list, total_items = get_all_accounts(db, page, limit, filters, tenant_id=current_tenant) # Pass db

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

    if not data.get('accountType') or not data.get('code') or not data.get('name'):
        return jsonify({"message": "Missing required fields: Account Type, Code, and Name"}), 400

    if 'defaultGstRateId' in data and data['defaultGstRateId'] == "":
        data['defaultGstRateId'] = None
    if 'subAccountOf' in data and data['subAccountOf'] == "":
        data['subAccountOf'] = None

    if data.get('isSubAccount') and not data.get('subAccountOf'):
        return jsonify({"message": "Sub-account Of is required if 'Is Sub-Account' is checked."}), 400

    try:
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()
        db = get_db() # Get DB instance

        matched_count = update_account(db, account_id, data, user=current_user, tenant_id=current_tenant) # Pass db
        if matched_count == 0: return jsonify({"message": "Account not found or no changes made"}), 404

        updated_account = get_account_by_id(db, account_id, tenant_id=current_tenant) # Pass db
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
        db = get_db() # Get DB instance

        deleted_count = delete_account_by_id(db, account_id, user=current_user, tenant_id=current_tenant) # Pass db
        if deleted_count == 0: return jsonify({"message": "Account not found"}), 404
        return jsonify({"message": "Account deleted successfully"}), 200
    except ValueError as ve: # Catch specific errors from DAL if raised
        return jsonify({"message": str(ve)}), 400
    except Exception as e:
        logging.error(f"Error deleting account {account_id}: {e}")
        return jsonify({"message": "Failed to delete account"}), 500
