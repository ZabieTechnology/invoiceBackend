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

@sales_invoices_bp.route('', methods=['POST'])
def handle_create_invoice():
    """ Handles POST requests to create a new sales invoice. """
    if not request.json:
        return jsonify({"message": "No JSON data provided"}), 400

    data = request.json

    if not data.get('customerId') or not data.get('lineItems'):
        return jsonify({"message": "Missing required fields: customerId and lineItems"}), 400

    try:
        db = get_db()
        invoice_id = create_sales_invoice(
            db_conn=db,
            invoice_data=data,
            user=get_current_user(),
            tenant_id=get_current_tenant_id()
        )
        created_invoice = get_sales_invoice_by_id(db, str(invoice_id), tenant_id=get_current_tenant_id())
        if created_invoice:
            created_invoice['_id'] = str(created_invoice['_id'])
            return jsonify({"message": "Invoice created successfully", "data": created_invoice}), 201
        else:
            return jsonify({"message": "Invoice created, but failed to retrieve."}), 500
    except ValueError as ve:
        return jsonify({"message": str(ve)}), 409
    except Exception as e:
        logging.error(f"Error in handle_create_invoice: {e}")
        return jsonify({"message": "Failed to create invoice", "error": str(e)}), 500

@sales_invoices_bp.route('/<invoice_id>/pdf', methods=['GET'])
def handle_get_invoice_pdf(invoice_id):
    """
    Placeholder for generating and returning a PDF of the invoice.
    In a real application, this would use a library like FPDF or ReportLab.
    """
    if not ObjectId.is_valid(invoice_id):
        return jsonify({"message": "Invalid invoice ID format"}), 400

    # In a real app, you would fetch invoice data, generate a PDF, and return it.
    # For now, we'll just return a success message.
    return jsonify({"message": f"PDF for invoice {invoice_id} would be generated here."}), 200

# You can add other standard routes (GET all, GET by ID, PUT, DELETE) here
# following the pattern of your other API files if needed for other parts of your app.

