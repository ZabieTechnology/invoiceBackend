# api/sales_invoices.py
from flask import Blueprint, request, jsonify, session, current_app
import logging
from bson import ObjectId

from db.sales_invoices_dal import (
    create_sales_invoice,
    get_sales_invoice_by_id,
    get_all_sales_invoices,
    update_sales_invoice,
    delete_sales_invoice
)
from db.database import get_db

sales_invoices_bp = Blueprint(
    'sales_invoices_bp',
    __name__,
    url_prefix='/api/sales-invoices'
)

logging.basicConfig(level=logging.INFO)

def get_current_user():
    return session.get('username', 'System_User_Placeholder')

def get_current_tenant_id():
    return session.get('tenant_id', 'default_tenant_placeholder')

@sales_invoices_bp.route('/', methods=['POST'], strict_slashes=False)
def handle_create_invoice():
    """ Handles POST requests to create a new sales invoice. """
    if not request.json:
        return jsonify({"message": "No JSON data provided"}), 400

    data = request.json

    if not data.get('customerId') or not data.get('lineItems'):
        return jsonify({"message": "Missing required fields: customerId and lineItems"}), 400

    try:
        db = get_db()
        # The create_sales_invoice function now returns the full created document.
        created_invoice = create_sales_invoice(
            db_conn=db,
            invoice_data=data,
            user=get_current_user(),
            tenant_id=get_current_tenant_id()
        )

        # No need to fetch the invoice again, just return the document we received.
        return jsonify({"message": "Invoice created successfully", "data": created_invoice}), 201
    except ValueError as ve:
        return jsonify({"message": str(ve)}), 409
    except Exception as e:
        logging.error(f"Error in handle_create_invoice: {e}")
        return jsonify({"message": "Failed to create invoice", "error": str(e)}), 500

@sales_invoices_bp.route('/', methods=['GET'], strict_slashes=False)
def handle_get_all_invoices():
    """
    Handles GET requests to fetch all sales invoices with pagination and filters.
    """
    tenant_id = get_current_tenant_id()
    try:
        page = int(request.args.get("page", 1))
        limit_str = request.args.get("limit", "25")
        limit = -1 if limit_str == '-1' else int(limit_str)

        filters = {}
        customer_id = request.args.get("customerId")
        if customer_id:
            filters['customer._id'] = customer_id

        status = request.args.get("status")
        if status:
            # Allow filtering by a comma-separated list of statuses
            status_list = [s.strip() for s in status.split(',')]
            filters['status'] = {'$in': status_list}

        db = get_db()

        invoice_list, total_items = get_all_sales_invoices(db, page, limit, filters=filters, tenant_id=tenant_id)

        return jsonify({
            "data": invoice_list,
            "total": total_items,
            "page": page,
            "limit": limit if limit > 0 else total_items,
            "totalPages": (total_items + limit - 1) // limit if limit > 0 else 1
        }), 200
    except ValueError:
        return jsonify({"message": "Invalid page or limit parameter."}), 400
    except Exception as e:
        logging.error(f"Error in handle_get_all_invoices: {e}")
        return jsonify({"message": "Failed to fetch invoices", "error": str(e)}), 500


@sales_invoices_bp.route('/<invoice_id>', methods=['GET'])
def handle_get_invoice_by_id(invoice_id):
    """ Handles GET requests for a single sales invoice by its ID. """
    if not ObjectId.is_valid(invoice_id):
        return jsonify({"message": "Invalid invoice ID format"}), 400
    try:
        db = get_db()
        invoice = get_sales_invoice_by_id(
            db_conn=db,
            invoice_id=invoice_id,
            tenant_id=get_current_tenant_id()
        )
        if invoice:
            return jsonify({"data": invoice}), 200
        else:
            return jsonify({"message": "Invoice not found"}), 404
    except Exception as e:
        logging.error(f"Error in handle_get_invoice_by_id: {e}")
        return jsonify({"message": "Failed to fetch invoice", "error": str(e)}), 500

@sales_invoices_bp.route('/<invoice_id>', methods=['PATCH'])
def handle_update_invoice(invoice_id):
    """ Handles PATCH requests to update an existing sales invoice. """
    if not ObjectId.is_valid(invoice_id):
        return jsonify({"message": "Invalid invoice ID format"}), 400
    if not request.json:
        return jsonify({"message": "No JSON data provided"}), 400

    data = request.json
    try:
        db = get_db()
        matched_count = update_sales_invoice(
            db_conn=db,
            invoice_id=invoice_id,
            update_data=data,
            user=get_current_user(),
            tenant_id=get_current_tenant_id()
        )
        if matched_count > 0:
            updated_invoice = get_sales_invoice_by_id(db, invoice_id, get_current_tenant_id())
            return jsonify({"message": "Invoice updated successfully", "data": updated_invoice}), 200
        else:
            return jsonify({"message": "Invoice not found or no changes made"}), 404
    except Exception as e:
        logging.error(f"Error in handle_update_invoice: {e}")
        return jsonify({"message": "Failed to update invoice", "error": str(e)}), 500

@sales_invoices_bp.route('/<invoice_id>', methods=['DELETE'])
def handle_delete_invoice(invoice_id):
    """ Handles DELETE requests for a single sales invoice. """
    if not ObjectId.is_valid(invoice_id):
        return jsonify({"message": "Invalid invoice ID format"}), 400
    try:
        db = get_db()
        deleted_count = delete_sales_invoice(
            db_conn=db,
            invoice_id=invoice_id,
            user=get_current_user(),
            tenant_id=get_current_tenant_id()
        )
        if deleted_count > 0:
            return jsonify({"message": "Invoice deleted successfully"}), 200
        else:
            return jsonify({"message": "Invoice not found"}), 404
    except Exception as e:
        logging.error(f"Error in handle_delete_invoice: {e}")
        return jsonify({"message": "Failed to delete invoice", "error": str(e)}), 500


@sales_invoices_bp.route('/<invoice_id>/pdf', methods=['GET'])
def handle_get_invoice_pdf(invoice_id):
    """
    Placeholder for generating and returning a PDF of the invoice.
    """
    if not ObjectId.is_valid(invoice_id):
        return jsonify({"message": "Invalid invoice ID format"}), 400

    return jsonify({"message": f"PDF for invoice {invoice_id} would be generated here."}), 200
