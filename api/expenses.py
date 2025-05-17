# api/expenses.py
from flask import Blueprint, request, jsonify, session
import logging
from bson import ObjectId
import re # For search
from datetime import datetime # For date range filtering

from db.expense_dal import (
    create_expense,
    get_expense_by_id,
    get_all_expenses,
    update_expense,
    delete_expense_by_id,
    parse_date_string # Import helper if used for query params
)

expenses_bp = Blueprint(
    'expenses_bp',
    __name__,
    url_prefix='/api/expenses'
)

logging.basicConfig(level=logging.INFO)

def get_current_user():
    return session.get('username', 'System')

@expenses_bp.route('', methods=['POST'])
def handle_create_expense():
    data = request.get_json()
    if not data:
        return jsonify({"message": "No input data provided"}), 400
    # Add required field checks based on your form
    if not data.get('date') or not data.get('supplier') or not data.get('head') or data.get('total') is None:
        return jsonify({"message": "Missing required fields: date, supplier, head, total"}), 400

    try:
        current_user = get_current_user()
        expense_id = create_expense(data, user=current_user)
        created_expense = get_expense_by_id(str(expense_id))
        if created_expense:
            created_expense['_id'] = str(created_expense['_id'])
            if isinstance(created_expense.get('date'), datetime):
                created_expense['date'] = created_expense['date'].strftime('%d/%m/%Y') # Format for frontend
            return jsonify({"message": "Expense created successfully", "data": created_expense}), 201
        else:
            return jsonify({"message": "Expense created, but failed to retrieve."}), 201
    except Exception as e:
        logging.error(f"Error in handle_create_expense: {e}")
        return jsonify({"message": "Failed to create expense"}), 500

@expenses_bp.route('/<expense_id>', methods=['GET'])
def handle_get_expense(expense_id):
    try:
        if not ObjectId.is_valid(expense_id):
            return jsonify({"message": "Invalid expense ID format"}), 400
        
        expense = get_expense_by_id(expense_id)
        if expense:
            expense['_id'] = str(expense['_id'])
            if isinstance(expense.get('date'), datetime):
                expense['date'] = expense['date'].strftime('%d/%m/%Y')
            return jsonify(expense), 200
        else:
            return jsonify({"message": "Expense not found"}), 404
    except Exception as e:
        logging.error(f"Error fetching expense {expense_id}: {e}")
        return jsonify({"message": "Failed to fetch expense"}), 500

@expenses_bp.route('', methods=['GET'])
def handle_get_all_api_expenses(): # Renamed to avoid conflict with DAL function name
    try:
        page = int(request.args.get("page", 1))
        limit_str = request.args.get("limit", "10") # Default to 10 from your frontend
        limit = int(limit_str) if limit_str.isdigit() and int(limit_str) != 0 else -1


        search_term = request.args.get("search", None)
        supplier_filter = request.args.get("supplier", None)
        date_from_str = request.args.get("dateFrom", None)
        date_to_str = request.args.get("dateTo", None)
        # Get sort parameters
        sort_by = request.args.get("sortBy", "date") # Default sort by date
        order_str = request.args.get("sortOrder", "desc") # Default sort descending
        sort_order = -1 if order_str.lower() == "desc" else 1


        filters = {}
        if search_term:
            regex_query = {"$regex": re.escape(search_term), "$options": "i"}
            filters["$or"] = [
                {"supplier": regex_query},
                {"head": regex_query},
                {"source": regex_query},
                {"description": regex_query} # Assuming you add description
            ]
        
        if supplier_filter:
            filters["supplier"] = supplier_filter # Exact match or use regex if needed

        # Date range filtering
        if date_from_str:
            parsed_date_from = parse_date_string(date_from_str)
            if parsed_date_from:
                filters['dateFrom'] = parsed_date_from # Pass datetime object to DAL
        if date_to_str:
            parsed_date_to = parse_date_string(date_to_str)
            if parsed_date_to:
                 # To include the whole day, set time to end of day
                filters['dateTo'] = datetime.combine(parsed_date_to, datetime.max.time())


        expense_list, total_items = get_all_expenses(page, limit, filters, sort_by, sort_order)
        
        result = []
        for item in expense_list:
            item['_id'] = str(item['_id'])
            if isinstance(item.get('date'), datetime): # Ensure date is string for JSON
                item['date'] = item['date'].strftime('%d/%m/%Y')
            # Format currency fields for display if needed, or handle on frontend
            for field in ['total', 'tax']:
                if field in item and isinstance(item[field], (int, float)):
                    item[field] = f"${item[field]:.2f}" # Example formatting
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
        logging.exception(f"Error fetching all expenses API: {e}") # Use .exception for full traceback
        return jsonify({"message": "Failed to fetch expenses"}), 500

@expenses_bp.route('/<expense_id>', methods=['PUT'])
def handle_update_expense(expense_id):
    data = request.get_json()
    if not data:
        return jsonify({"message": "No input data provided"}), 400
    if not ObjectId.is_valid(expense_id):
        return jsonify({"message": "Invalid expense ID format"}), 400

    try:
        current_user = get_current_user()
        matched_count = update_expense(expense_id, data, user=current_user)
        if matched_count == 0:
            return jsonify({"message": "Expense not found or no changes made"}), 404
        
        updated_expense = get_expense_by_id(expense_id)
        if updated_expense:
            updated_expense['_id'] = str(updated_expense['_id'])
            if isinstance(updated_expense.get('date'), datetime):
                updated_expense['date'] = updated_expense['date'].strftime('%d/%m/%Y')
            return jsonify({"message": "Expense updated successfully", "data": updated_expense}), 200
        else:
            return jsonify({"message": "Expense updated, but failed to retrieve."}), 200
    except Exception as e:
        logging.error(f"Error updating expense {expense_id}: {e}")
        return jsonify({"message": "Failed to update expense"}), 500

@expenses_bp.route('/<expense_id>', methods=['DELETE'])
def handle_delete_expense(expense_id):
    try:
        if not ObjectId.is_valid(expense_id):
            return jsonify({"message": "Invalid expense ID format"}), 400

        deleted_count = delete_expense_by_id(expense_id)
        if deleted_count == 0:
            return jsonify({"message": "Expense not found"}), 404
        return jsonify({"message": "Expense deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error deleting expense {expense_id}: {e}")
        return jsonify({"message": "Failed to delete expense"}), 500

