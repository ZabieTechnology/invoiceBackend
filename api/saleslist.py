# api/saleslist.py
from flask import Blueprint, request, jsonify, session, current_app
import logging
from bson import ObjectId
from datetime import datetime, timedelta
import re
import json

# Corrected import from the new DAL filename
from db.saleslist_dal import (
    create_sales_invoice,
    get_sales_invoice_by_id,
    get_all_sales_invoices_paginated,
    update_sales_invoice,
    delete_sales_invoice_by_id,
    get_sales_summary_data,
    get_accounts_receivable_aging,
    parse_date_for_dal
)

# Renamed blueprint variable to match your request, and using consistent URL prefix
sales_list_bp = Blueprint( # Renamed
    'sales_list_bp',
    __name__,
    url_prefix='/api/sales-invoices' # Keeping prefix for consistency with frontend calls
)

logging.basicConfig(level=logging.INFO)

def get_current_user():
    return session.get('username', 'System_User_Placeholder')

def get_current_tenant_id():
    return session.get('tenant_id', 'default_tenant_placeholder')

def _prepare_invoice_for_json(invoice_doc):
    if not invoice_doc: return None
    if not isinstance(invoice_doc, dict): invoice_doc = dict(invoice_doc)
    if '_id' in invoice_doc and isinstance(invoice_doc.get('_id'), ObjectId):
        invoice_doc['_id'] = str(invoice_doc['_id'])
    if 'customerId' in invoice_doc and isinstance(invoice_doc.get('customerId'), ObjectId):
        invoice_doc['customerId'] = str(invoice_doc['customerId'])
    if 'bankAccountId' in invoice_doc and isinstance(invoice_doc.get('bankAccountId'), ObjectId):
        invoice_doc['bankAccountId'] = str(invoice_doc['bankAccountId'])

    date_fields = ['invoiceDate', 'dueDate', 'created_date', 'updated_date']
    for field in date_fields:
        if field in invoice_doc and isinstance(invoice_doc.get(field), datetime):
            invoice_doc[field] = invoice_doc[field].strftime('%Y-%m-%d')

    if 'lineItems' in invoice_doc and isinstance(invoice_doc['lineItems'], list):
        for item in invoice_doc['lineItems']: pass # Add conversions if needed

    return invoice_doc

@sales_list_bp.route('', methods=['POST'])
def handle_create_sales_invoice_api(): # Renamed to avoid conflict if imported elsewhere
    data = request.get_json()
    if not data: return jsonify({"message": "No input data provided"}), 400

    required_fields = ['invoiceNumber', 'invoiceDate', 'customerId', 'lineItems', 'grandTotal']
    missing_fields = [field for field in required_fields if not data.get(field)]
    if 'lineItems' in data and not isinstance(data.get('lineItems'), list):
        missing_fields.append("lineItems (must be an array)")
    elif 'lineItems' in data and not data.get('lineItems'):
         missing_fields.append("lineItems (cannot be empty)")

    if missing_fields:
        return jsonify({"message": f"Missing required fields: {', '.join(missing_fields)}"}), 400

    try:
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()
        invoice_id = create_sales_invoice(data, user=current_user, tenant_id=current_tenant)
        created_invoice = get_sales_invoice_by_id(str(invoice_id), tenant_id=current_tenant)
        if created_invoice:
            return jsonify({"message": "Sales invoice created successfully", "data": _prepare_invoice_for_json(created_invoice)}), 201
        else:
            logging.error(f"Sales invoice created (ID: {invoice_id}) but failed to retrieve for tenant {current_tenant}.")
            return jsonify({"message": "Sales invoice created, but failed to retrieve immediately."}), 207
    except ValueError as ve:
        logging.warning(f"ValueError during sales invoice creation: {ve}")
        return jsonify({"message": str(ve)}), 400
    except Exception as e:
        logging.exception(f"Error in handle_create_sales_invoice_api: {e}")
        return jsonify({"message": "Failed to create sales invoice"}), 500

@sales_list_bp.route('/<invoice_id>', methods=['GET'])
def handle_get_sales_invoice_api(invoice_id): # Renamed
    try:
        if not ObjectId.is_valid(invoice_id): return jsonify({"message": "Invalid invoice ID format"}), 400
        current_tenant = get_current_tenant_id()
        invoice = get_sales_invoice_by_id(invoice_id, tenant_id=current_tenant)
        if invoice: return jsonify(_prepare_invoice_for_json(invoice)), 200
        else: return jsonify({"message": "Sales invoice not found"}), 404
    except Exception as e:
        logging.error(f"Error fetching sales invoice {invoice_id}: {e}")
        return jsonify({"message": "Failed to fetch sales invoice"}), 500

@sales_list_bp.route('', methods=['GET'])
def handle_get_all_api_sales_invoices_list(): # Renamed
    try:
        page = int(request.args.get("page", 1))
        limit_str = request.args.get("limit", "10")
        limit = int(limit_str) if limit_str.isdigit() and int(limit_str) != 0 else -1
        current_tenant = get_current_tenant_id()

        search_term = request.args.get("search", None)
        status_filter = request.args.get("status", None)
        date_filter_type = request.args.get("dateFilter", None)
        custom_date_from_str = request.args.get("dateFrom", None)
        custom_date_to_str = request.args.get("dateTo", None)

        sort_by = request.args.get("sortBy", "invoiceDate")
        order_str = request.args.get("sortOrder", "desc")
        sort_order = -1 if order_str.lower() == "desc" else 1

        filters = {}
        if search_term: filters["search"] = search_term
        if status_filter and status_filter.lower() != "all": filters["status"] = status_filter

        if date_filter_type:
            today = datetime.utcnow().date()
            if date_filter_type == "this_month":
                filters['dateFrom'] = datetime.combine(today.replace(day=1), datetime.min.time())
                next_month_start = (today.replace(day=28) + timedelta(days=4)).replace(day=1)
                filters['dateTo'] = datetime.combine(next_month_start - timedelta(days=1), datetime.max.time())
            elif date_filter_type == "last_month":
                first_day_current_month = today.replace(day=1)
                last_day_last_month = first_day_current_month - timedelta(days=1)
                filters['dateFrom'] = datetime.combine(last_day_last_month.replace(day=1), datetime.min.time())
                filters['dateTo'] = datetime.combine(last_day_last_month, datetime.max.time())
            elif date_filter_type == "custom" and custom_date_from_str and custom_date_to_str:
                date_from_obj = parse_date_for_dal(custom_date_from_str) # DAL expects datetime
                date_to_obj = parse_date_for_dal(custom_date_to_str)
                if date_from_obj: filters['dateFrom'] = datetime.combine(date_from_obj, datetime.min.time())
                if date_to_obj: filters['dateTo'] = datetime.combine(date_to_obj, datetime.max.time())

        invoice_list, total_items = get_all_sales_invoices_paginated(
            page, limit, filters, sort_by, sort_order, tenant_id=current_tenant
        )

        result = []
        for item in invoice_list:
            prepared_item = _prepare_invoice_for_json(dict(item))
            if prepared_item.get('invoiceDate') and isinstance(prepared_item['invoiceDate'], str) and '-' in prepared_item['invoiceDate']:
                try: prepared_item['invoiceDate'] = datetime.strptime(prepared_item['invoiceDate'], '%Y-%m-%d').strftime('%d/%m/%Y')
                except: pass
            if prepared_item.get('dueDate') and isinstance(prepared_item['dueDate'], str) and '-' in prepared_item['dueDate']:
                try: prepared_item['dueDate'] = datetime.strptime(prepared_item['dueDate'], '%Y-%m-%d').strftime('%d/%m/%Y')
                except: pass
            result.append(prepared_item)

        return jsonify({
            "data": result, "total": total_items, "page": page,
            "limit": limit if limit > 0 else total_items,
            "totalPages": (total_items + limit - 1) // limit if limit > 0 and total_items > 0 else 1
        }), 200
    except ValueError:
         return jsonify({"message": "Invalid page or limit parameter."}), 400
    except Exception as e:
        logging.exception(f"Error fetching all sales invoices API: {e}")
        return jsonify({"message": "Failed to fetch sales invoices"}), 500

@sales_list_bp.route('/<invoice_id>', methods=['PUT'])
def handle_update_sales_invoice_api(invoice_id): # Renamed
    if not ObjectId.is_valid(invoice_id): return jsonify({"message": "Invalid invoice ID format"}), 400
    data = request.get_json()
    if not data: return jsonify({"message": "No data provided for update"}), 400
    if not data.get('invoiceNumber') or not data.get('invoiceDate') or not data.get('customerId'):
        return jsonify({"message": "Missing required fields for update"}), 400
    try:
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()
        matched_count = update_sales_invoice(invoice_id, data, user=current_user, tenant_id=current_tenant)
        if matched_count == 0: return jsonify({"message": "Sales invoice not found or no changes made"}), 404
        updated_invoice = get_sales_invoice_by_id(invoice_id, tenant_id=current_tenant)
        if updated_invoice: return jsonify({"message": "Sales invoice updated successfully", "data": _prepare_invoice_for_json(updated_invoice)}), 200
        else: return jsonify({"message": "Sales invoice updated, but failed to retrieve."}), 200
    except ValueError as ve:
        logging.warning(f"ValueError during sales invoice update {invoice_id}: {ve}")
        return jsonify({"message": str(ve)}), 400
    except Exception as e:
        logging.error(f"Error updating sales invoice {invoice_id}: {e}")
        return jsonify({"message": "Failed to update sales invoice"}), 500

@sales_list_bp.route('/<invoice_id>', methods=['DELETE'])
def handle_delete_sales_invoice_api(invoice_id): # Renamed
    try:
        if not ObjectId.is_valid(invoice_id): return jsonify({"message": "Invalid invoice ID format"}), 400
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()
        deleted_count = delete_sales_invoice_by_id(invoice_id, user=current_user, tenant_id=current_tenant)
        if deleted_count == 0: return jsonify({"message": "Sales invoice not found"}), 404
        return jsonify({"message": "Sales invoice deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error deleting sales invoice {invoice_id}: {e}")
        return jsonify({"message": "Failed to delete sales invoice"}), 500

@sales_list_bp.route('/summary', methods=['GET'])
def handle_get_summary_api(): # Renamed
    try:
        current_tenant = get_current_tenant_id()
        summary_data = get_sales_summary_data(tenant_id=current_tenant)
        return jsonify(summary_data), 200
    except Exception as e:
        logging.exception(f"Error fetching sales summary: {e}")
        return jsonify({"message": "Failed to fetch sales summary"}), 500

@sales_list_bp.route('/accounts-receivable', methods=['GET'])
def handle_get_accounts_receivable_api(): # Renamed
    try:
        current_tenant = get_current_tenant_id()
        aging_data = get_accounts_receivable_aging(tenant_id=current_tenant)
        return jsonify({"data": aging_data}), 200
    except Exception as e:
        logging.exception(f"Error fetching accounts receivable: {e}")
        return jsonify({"message": "Failed to fetch accounts receivable"}), 500

