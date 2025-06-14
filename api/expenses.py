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
# Activity logging is primarily handled in the DAL.

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
        allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS')
        if allowed_extensions is None:
            logging.warning("ALLOWED_EXTENSIONS not found in app.config. Using default.")
            allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'pdf'}
        elif not isinstance(allowed_extensions, set):
            try: allowed_extensions = set(allowed_extensions)
            except TypeError:
                logging.error("Failed to convert ALLOWED_EXTENSIONS to set. Using default.")
                allowed_extensions = {'png', 'jpg', 'jpeg', 'gif', 'svg', 'pdf'}

        if not upload_folder:
            logging.error("Expense invoice upload folder is not configured.")
            raise ValueError("File upload path not configured on server.")

        filename = secure_filename(file_storage.filename)
        if '.' not in filename or filename.rsplit('.', 1)[1].lower() not in allowed_extensions:
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

def _prepare_document_for_json(doc):
    """
    Recursively converts ObjectId and datetime fields in a document (or sub-document/list)
    to strings for JSON serialization.
    """
    if isinstance(doc, list):
        return [_prepare_document_for_json(item) for item in doc]
    if isinstance(doc, dict):
        new_doc = {}
        for key, value in doc.items():
            if isinstance(value, ObjectId):
                new_doc[key] = str(value)
            elif isinstance(value, datetime):
                new_doc[key] = value.isoformat()
            elif isinstance(value, (dict, list)):
                new_doc[key] = _prepare_document_for_json(value)
            else:
                new_doc[key] = value
        return new_doc
    if hasattr(doc, 'to_decimal'):
        return float(doc.to_decimal())
    return doc


@expenses_bp.route('', methods=['POST'])
def handle_create_expense():
    if 'multipart/form-data' not in request.content_type:
        return jsonify({"message": "Content-Type must be multipart/form-data"}), 415

    if not request.form: return jsonify({"message": "No form data provided"}), 400
    data = request.form.to_dict(flat=True)

    # Required fields check from frontend AddExpensePage
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

        # The DAL (create_expense) handles detailed field mapping,
        # ObjectId conversion, date parsing, float parsing, and lineItems JSON parsing.
        # It also calculates taxAmount from individual components.
        expense_id = create_expense(data, user=current_user, tenant_id=current_tenant)

        created_expense = get_expense_by_id(str(expense_id), tenant_id=current_tenant)
        if created_expense:
            prepared_expense = _prepare_document_for_json(dict(created_expense))
            return jsonify({"message": "Expense created successfully", "data": prepared_expense}), 201
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
            prepared_expense = _prepare_document_for_json(dict(expense))
            return jsonify(prepared_expense), 200
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

        status_filter = request.args.get("status", None)
        supplier_name_filter = request.args.get("supplierName", None)
        date_from_str = request.args.get("dateFrom", None)
        date_to_str = request.args.get("dateTo", None)

        filters = {}
        if search_term:
            filters["$text_search_term"] = search_term

        if supplier_name_filter:
            filters["supplierName"] = {"$regex": re.escape(supplier_name_filter), "$options": "i"}

        if status_filter and status_filter != "All":
            filters["status"] = status_filter

        if date_from_str:
            parsed_date_from = parse_date_string(date_from_str)
            if parsed_date_from: filters['dateFrom'] = parsed_date_from
        if date_to_str:
            parsed_date_to = parse_date_string(date_to_str)
            if parsed_date_to: filters['dateTo'] = datetime.combine(parsed_date_to, datetime.max.time())

        expense_list, total_items = get_all_expenses(page, limit, filters, sort_by, sort_order, tenant_id=current_tenant)

        result = []
        for item in expense_list:
            prepared_item = _prepare_document_for_json(dict(item))
            # Format date for display in list view (dd/MM/yyyy)
            if prepared_item.get('billDate') and isinstance(prepared_item['billDate'], str) and '-' in prepared_item['billDate']:
                 try:
                     dt_obj = datetime.fromisoformat(prepared_item['billDate'].replace('Z', '+00:00'))
                     prepared_item['billDate'] = dt_obj.strftime('%d/%m/%Y')
                 except ValueError: pass
            if prepared_item.get('dueDate') and isinstance(prepared_item['dueDate'], str) and '-' in prepared_item['dueDate']:
                 try:
                     dt_obj = datetime.fromisoformat(prepared_item['dueDate'].replace('Z', '+00:00'))
                     prepared_item['dueDate'] = dt_obj.strftime('%d/%m/%Y')
                 except ValueError: pass

            # Format currency fields for display
            for field in ['totalAmount', 'taxAmount', 'netAmount', 'subTotalFromItems', 'discountAmount', 'cgstAmount', 'sgstAmount', 'igstAmount', 'cessAmount', 'tdsAmountCalculated']:
                if field in prepared_item and isinstance(prepared_item[field], (int, float)):
                    prepared_item[field] = f"{prepared_item[field]:.2f}"
            result.append(prepared_item)

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

    data = {}
    if 'multipart/form-data' in request.content_type:
        data = request.form.to_dict(flat=True)
    elif request.is_json:
        data = request.get_json()

    if not data: return jsonify({"message": "No data provided for update"}), 400

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
            elif 'invoiceFilename' not in data:
                data['invoiceFilename'] = None # Explicitly clear if no new file and not in form

        matched_count = update_expense(expense_id, data, user=current_user, tenant_id=current_tenant)
        if matched_count == 0:
            return jsonify({"message": "Expense not found or no changes made"}), 404

        updated_expense = get_expense_by_id(expense_id, tenant_id=current_tenant)
        if updated_expense:
            prepared_expense = _prepare_document_for_json(dict(updated_expense))
            return jsonify({"message": "Expense updated successfully", "data": prepared_expense}), 200
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
