# api/sales_invoices.py
from flask import Blueprint, request, jsonify, session, current_app
import logging
from bson import ObjectId

# ** FIX **
# Changed the import to use the plural 'sales_invoices_dal' to match
# the likely filename and resolve the ModuleNotFoundError.
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
        invoice_id = create_sales_invoice(
            db_conn=db,
            invoice_data=data,
            user=get_current_user(),
            tenant_id=get_current_tenant_id()
        )
        created_invoice = get_sales_invoice_by_id(db, str(invoice_id), tenant_id=get_current_tenant_id())

        return jsonify({"message": "Invoice created successfully", "data": created_invoice}), 201
    except ValueError as ve:
        return jsonify({"message": str(ve)}), 409
    except Exception as e:
        logging.error(f"Error in handle_create_invoice: {e}")
        return jsonify({"message": "Failed to create invoice", "error": str(e)}), 500

@sales_invoices_bp.route('/', methods=['GET'], strict_slashes=False)
def handle_get_all_invoices():
    """ Handles GET requests to fetch all sales invoices with pagination. """
    tenant_id = get_current_tenant_id()
    try:
        page = int(request.args.get("page", 1))
        limit_str = request.args.get("limit", "25")

        limit = -1 if limit_str == '-1' else int(limit_str)

        db = get_db()

        invoice_list, total_items = get_all_sales_invoices(db, page, limit, filters=None, tenant_id=tenant_id)

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


@sales_invoices_bp.route('/<invoice_id>/pdf', methods=['GET'])
def handle_get_invoice_pdf(invoice_id):
    """
    Placeholder for generating and returning a PDF of the invoice.
    """
    if not ObjectId.is_valid(invoice_id):
        return jsonify({"message": "Invalid invoice ID format"}), 400

    return jsonify({"message": f"PDF for invoice {invoice_id} would be generated here."}), 200
