# api/chart_of_accounts.py
from flask import Blueprint, request, jsonify, session
import logging
from bson import ObjectId
import re

from db.chart_of_accounts_dal import (
    create_account,
    get_account_by_id,
    get_all_accounts,
    update_account,
    delete_account_by_id
)

chart_of_accounts_bp = Blueprint(
    'chart_of_accounts_bp',
    __name__,
    url_prefix='/api/chart-of-accounts' # Kebab-case for URL
)

logging.basicConfig(level=logging.INFO)

def get_current_user():
    return session.get('username', 'System')

@chart_of_accounts_bp.route('', methods=['POST'])
def handle_create_account():
    data = request.get_json()
    if not data:
        return jsonify({"message": "No input data provided"}), 400
    if not data.get('name') or not data.get('code') or not data.get('accountType') or data.get('parentCategory') is None:
        return jsonify({"message": "Missing required fields: name, code, accountType, parentCategory"}), 400

    try:
        current_user = get_current_user()
        account_id = create_account(data, user=current_user)
        created_account = get_account_by_id(str(account_id))
        if created_account:
            created_account['_id'] = str(created_account['_id'])
            if created_account.get('balanceAsOf'): # Convert date back to string for JSON
                created_account['balanceAsOf'] = created_account['balanceAsOf'].strftime('%Y-%m-%d')
            return jsonify({"message": "Account created successfully", "data": created_account}), 201
        else:
            return jsonify({"message": "Account created, but failed to retrieve."}), 201
    except Exception as e:
        logging.error(f"Error in handle_create_account: {e}")
        return jsonify({"message": "Failed to create account"}), 500

@chart_of_accounts_bp.route('/<account_id>', methods=['GET'])
def handle_get_account(account_id):
    try:
        if not ObjectId.is_valid(account_id):
            return jsonify({"message": "Invalid account ID format"}), 400
        
        account = get_account_by_id(account_id)
        if account:
            account['_id'] = str(account['_id'])
            if account.get('balanceAsOf'):
                account['balanceAsOf'] = account['balanceAsOf'].strftime('%Y-%m-%d')
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
        # If limit is -1 or 0, DAL handles fetching all
        limit_str = request.args.get("limit", "25")
        limit = int(limit_str) if limit_str.isdigit() and int(limit_str) != 0 else -1


        search_term = request.args.get("search", None)
        category_filter = request.args.get("category", None) # For tab filtering

        filters = {}
        if search_term:
            regex_query = {"$regex": re.escape(search_term), "$options": "i"}
            filters["$or"] = [
                {"name": regex_query},
                {"code": regex_query},
                {"description": regex_query},
                {"accountType": regex_query},
                {"parentCategory": regex_query} # "Heads" in frontend table
            ]
        
        if category_filter and category_filter.lower() != "all accounts" and category_filter.lower() != "inactive":
            filters["parentCategory"] = category_filter # Filter by the main accounting category
        elif category_filter and category_filter.lower() == "inactive":
            filters["status"] = "Inactive"
        elif category_filter and category_filter.lower() == "all accounts":
            filters["status"] = {"$ne": "Inactive"} # Exclude inactive by default for "All Accounts"

        account_list, total_items = get_all_accounts(page, limit, filters)
        
        result = []
        for item in account_list:
            item['_id'] = str(item['_id'])
            if item.get('balanceAsOf'):
                item['balanceAsOf'] = item['balanceAsOf'].strftime('%Y-%m-%d')
            result.append(item)

        return jsonify({
            "data": result,
            "total": total_items,
            "page": page,
            "limit": limit if limit > 0 else total_items, # Adjust limit in response if all items were fetched
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
    if not data:
        return jsonify({"message": "No input data provided"}), 400
    if not ObjectId.is_valid(account_id):
        return jsonify({"message": "Invalid account ID format"}), 400

    try:
        current_user = get_current_user()
        matched_count = update_account(account_id, data, user=current_user)
        if matched_count == 0:
            return jsonify({"message": "Account not found or no changes made"}), 404
        
        updated_account = get_account_by_id(account_id)
        if updated_account:
            updated_account['_id'] = str(updated_account['_id'])
            if updated_account.get('balanceAsOf'):
                updated_account['balanceAsOf'] = updated_account['balanceAsOf'].strftime('%Y-%m-%d')
            return jsonify({"message": "Account updated successfully", "data": updated_account}), 200
        else:
            return jsonify({"message": "Account updated, but failed to retrieve."}), 200
    except Exception as e:
        logging.error(f"Error updating account {account_id}: {e}")
        return jsonify({"message": "Failed to update account"}), 500

@chart_of_accounts_bp.route('/<account_id>', methods=['DELETE'])
def handle_delete_account(account_id):
    try:
        if not ObjectId.is_valid(account_id):
            return jsonify({"message": "Invalid account ID format"}), 400

        deleted_count = delete_account_by_id(account_id)
        if deleted_count == 0:
            return jsonify({"message": "Account not found"}), 404
        return jsonify({"message": "Account deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error deleting account {account_id}: {e}")
        return jsonify({"message": "Failed to delete account"}), 500

