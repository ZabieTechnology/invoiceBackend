# api/expenses.py
from flask import Blueprint, request, jsonify, session, current_app
import logging
from bson import ObjectId
import re
from datetime import datetime
import os
from werkzeug.utils import secure_filename
import json

from db.expense_dal import (
    create_expense,
    get_expense_by_id,
    get_all_expenses,
    update_expense,
    delete_expense_by_id,
    parse_date_string
)
# from db.activity_log_dal import add_activity # Logging is now primarily in DAL

expenses_bp = Blueprint(
    'expenses_bp',
    __name__,
    url_prefix='/api/expenses'
)

logging.basicConfig(level=logging.INFO)

# Placeholder: Implement these based on your authentication/session management
def get_current_user():
    return session.get('username', 'System_User_Placeholder')

def get_current_tenant_id():
    return session.get('tenant_id', 'default_tenant_placeholder')

def save_invoice_file(file_storage, tenant_id):
    """Saves the uploaded invoice file and returns its filename or path."""
    if file_storage and file_storage.filename:
        upload_folder = current_app.config.get('EXPENSE_INVOICE_UPLOAD_FOLDER')

        # Robustly get allowed_extensions
        allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS')
        if allowed_extensions is None:
            logging.warning(
                "ALLOWED_EXTENSIONS not found in app.config. "
                "Using a default set: {'png', 'jpg', 'jpeg', 'gif', 'svg', 'pdf'}"
            )
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'pdf'}
        elif not isinstance(allowed_extensions, set): # Ensure it's a set
            logging.warning(
                f"ALLOWED_EXTENSIONS in app.config is not a set (type: {type(allowed_extensions)}). "
                "Converting or using default."
            )
            try:
                allowed_extensions = set(allowed_extensions)
            except TypeError:
                logging.error("Failed to convert ALLOWED_EXTENSIONS to a set. Using default.")
                allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'pdf'}


        if not upload_folder:
            logging.error("Expense invoice upload folder is not configured.")
            raise ValueError("File upload path not configured on server.")

        filename = secure_filename(file_storage.filename)
        if '.' not in filename or filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
            # Construct the error message with the now guaranteed 'allowed_extensions' set
            allowed_extensions_str = ', '.join(allowed_extensions)
            raise ValueError(f"File type not allowed. Allowed: {allowed_extensions_str}")

        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
        unique_filename = f"{tenant_id}_{timestamp}_{filename}"

        if not os.path.exists(upload_folder):
            os.makedirs(upload_folder)

        file_path = os.path.join(upload_folder, unique_filename)
        file_storage.save(file_path)
        logging.info(f"Expense invoice '{unique_filename}' uploaded to {upload_folder}")
        return unique_filename
    return None


@expenses_bp.route('', methods=['POST'])
def handle_create_expense():
    if 'multipart/form-data' not in request.content_type:
        return jsonify({"message": "Content-Type must be multipart/form-data"}), 415

    if not request.form:
        return jsonify({"message": "No form data provided"}), 400

    data = request.form.to_dict(flat=True)

    if not data.get('billDate') or not data.get('supplierId') or \
       not data.get('expenseHeadId') or not data.get('totalAmount'):
        return jsonify({"message": "Missing required fields: Bill Date, Supplier, Expense Head, Total Amount"}), 400

    try:
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()

        invoice_filename = None
        if 'invoice' in request.files:
            invoice_file = request.files['invoice']
            if invoice_file and invoice_file.filename:
                invoice_filename = save_invoice_file(invoice_file, current_tenant)
                data['invoiceFilename'] = invoice_filename

        expense_id = create_expense(data, user=current_user, tenant_id=current_tenant)

        created_expense = get_expense_by_id(str(expense_id), tenant_id=current_tenant)
        if created_expense:
            created_expense['_id'] = str(created_expense['_id'])
            if isinstance(created_expense.get('billDate'), datetime):
                created_expense['billDate'] = created_expense['billDate'].strftime('%Y-%m-%d')
            if isinstance(created_expense.get('dueDate'), datetime):
                created_expense['dueDate'] = created_expense['dueDate'].strftime('%Y-%m-%d')
            for key in ['supplierId', 'expenseHeadId', 'gstRateId']:
                if key in created_expense and isinstance(created_expense[key], ObjectId):
                    created_expense[key] = str(created_expense[key])
            return jsonify({"message": "Expense created successfully", "data": created_expense}), 201
        else:
            return jsonify({"message": "Expense created, but failed to retrieve."}), 201
    except ValueError as ve:
        logging.warning(f"ValueError during expense creation: {ve}")
        return jsonify({"message": str(ve)}), 400
    except Exception as e:
        logging.exception(f"Error in handle_create_expense: {e}")
        return jsonify({"message": "Failed to create expense"}), 500

@expenses_bp.route('/<expense_id>', methods=['GET'])
def handle_get_expense(expense_id):
    try:
        if not ObjectId.is_valid(expense_id):
            return jsonify({"message": "Invalid expense ID format"}), 400
        current_tenant = get_current_tenant_id()
        expense = get_expense_by_id(expense_id, tenant_id=current_tenant)
        if expense:
            expense['_id'] = str(expense['_id'])
            if isinstance(expense.get('billDate'), datetime):
                expense['billDate'] = expense['billDate'].strftime('%Y-%m-%d')
            if isinstance(expense.get('dueDate'), datetime):
                expense['dueDate'] = expense['dueDate'].strftime('%Y-%m-%d')
            for key in ['supplierId', 'expenseHeadId', 'gstRateId']:
                if key in expense and isinstance(expense[key], ObjectId):
                    expense[key] = str(expense[key])
            return jsonify(expense), 200
        else:
            return jsonify({"message": "Expense not found"}), 404
    except Exception as e:
        logging.error(f"Error fetching expense {expense_id}: {e}")
        return jsonify({"message": "Failed to fetch expense"}), 500

@expenses_bp.route('', methods=['GET'])
def handle_get_all_api_expenses():
    try:
        page = int(request.args.get("page", 1))
        limit_str = request.args.get("limit", "10")
        limit = int(limit_str) if limit_str.isdigit() and int(limit_str) != 0 else -1
        current_tenant = get_current_tenant_id()
        search_term = request.args.get("search", None)
        sort_by = request.args.get("sortBy", "billDate")
        order_str = request.args.get("sortOrder", "desc")
        sort_order = -1 if order_str.lower() == "desc" else 1

        supplier_filter = request.args.get("supplier", None)
        date_from_str = request.args.get("dateFrom", None)
        date_to_str = request.args.get("dateTo", None)

        filters = {}
        if search_term:
            regex_query = {"$regex": re.escape(search_term), "$options": "i"}
            filters["$or"] = [
                {"billNo": regex_query},
                {"narration": regex_query},
                {"lineItems.description": regex_query}
            ]
        if supplier_filter and ObjectId.is_valid(supplier_filter):
            filters["supplierId"] = ObjectId(supplier_filter)

        if date_from_str:
            parsed_date_from = parse_date_string(date_from_str)
            if parsed_date_from: filters['dateFrom'] = parsed_date_from
        if date_to_str:
            parsed_date_to = parse_date_string(date_to_str)
            if parsed_date_to: filters['dateTo'] = datetime.combine(parsed_date_to, datetime.max.time())

        expense_list, total_items = get_all_expenses(page, limit, filters, sort_by, sort_order, tenant_id=current_tenant)

        result = []
        for item in expense_list:
            item['_id'] = str(item['_id'])
            if isinstance(item.get('billDate'), datetime):
                item['billDate'] = item['billDate'].strftime('%d/%m/%Y')
            if isinstance(item.get('dueDate'), datetime):
                item['dueDate'] = item['dueDate'].strftime('%d/%m/%Y')
            for key in ['supplierId', 'expenseHeadId', 'gstRateId']:
                if key in item and isinstance(item[key], ObjectId):
                    item[key] = str(item[key])
            for field in ['totalAmount', 'gstVatAmount', 'netAmount', 'subTotalFromItems', 'discountAmount', 'taxFromItems', 'grandTotalFromItems']:
                if field in item and isinstance(item[field], (int, float)):
                    item[field] = f"{item[field]:.2f}"
            result.append(item)

        return jsonify({
            "data": result, "total": total_items, "page": page,
            "limit": limit if limit > 0 else total_items,
            "totalPages": (total_items + limit - 1) // limit if limit > 0 and total_items > 0 else 1
        }), 200
    except ValueError:
         return jsonify({"message": "Invalid page or limit parameter."}), 400
    except Exception as e:
        logging.exception(f"Error fetching all expenses API: {e}")
        return jsonify({"message": "Failed to fetch expenses"}), 500

@expenses_bp.route('/<expense_id>', methods=['PUT'])
def handle_update_expense(expense_id):
    if not ObjectId.is_valid(expense_id):
        return jsonify({"message": "Invalid expense ID format"}), 400
    if 'multipart/form-data' not in request.content_type:
        data = request.get_json()
        if not data:
            return jsonify({"message": "No JSON data provided for update"}), 400
    else:
        data = request.form.to_dict(flat=True)
        if not data:
            return jsonify({"message": "No form data provided for update"}), 400

    if not data.get('billDate') or not data.get('supplierId') or \
       not data.get('expenseHeadId') or not data.get('totalAmount'):
        return jsonify({"message": "Missing required fields for update"}), 400

    try:
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()

        if 'invoice' in request.files:
            invoice_file = request.files['invoice']
            if invoice_file and invoice_file.filename:
                invoice_filename = save_invoice_file(invoice_file, current_tenant)
                data['invoiceFilename'] = invoice_filename

        matched_count = update_expense(expense_id, data, user=current_user, tenant_id=current_tenant)
        if matched_count == 0:
            return jsonify({"message": "Expense not found or no changes made"}), 404

        updated_expense = get_expense_by_id(expense_id, tenant_id=current_tenant)
        if updated_expense:
            updated_expense['_id'] = str(updated_expense['_id'])
            if isinstance(updated_expense.get('billDate'), datetime):
                updated_expense['billDate'] = updated_expense['billDate'].strftime('%Y-%m-%d')
            if isinstance(updated_expense.get('dueDate'), datetime):
                updated_expense['dueDate'] = updated_expense['dueDate'].strftime('%Y-%m-%d')
            for key in ['supplierId', 'expenseHeadId', 'gstRateId']:
                if key in updated_expense and isinstance(updated_expense[key], ObjectId):
                    updated_expense[key] = str(updated_expense[key])
            return jsonify({"message": "Expense updated successfully", "data": updated_expense}), 200
        else:
            return jsonify({"message": "Expense updated, but failed to retrieve."}), 200
    except ValueError as ve:
        logging.warning(f"ValueError during expense update {expense_id}: {ve}")
        return jsonify({"message": str(ve)}), 400
    except Exception as e:
        logging.error(f"Error updating expense {expense_id}: {e}")
        return jsonify({"message": "Failed to update expense"}), 500

@expenses_bp.route('/<expense_id>', methods=['DELETE'])
def handle_delete_expense(expense_id):
    try:
        if not ObjectId.is_valid(expense_id):
            return jsonify({"message": "Invalid expense ID format"}), 400
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()

        deleted_count = delete_expense_by_id(expense_id, user=current_user, tenant_id=current_tenant)
        if deleted_count == 0:
            return jsonify({"message": "Expense not found"}), 404
        return jsonify({"message": "Expense deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error deleting expense {expense_id}: {e}")
        return jsonify({"message": "Failed to delete expense"}), 500
