# api/payment.py
from flask import Blueprint, request, jsonify, session
import logging
import traceback

from db.payment_dal import record_payment
from db.database import get_db

payment_bp = Blueprint(
    'payment_bp',
    __name__,
    url_prefix='/api/payments'
)

logging.basicConfig(level=logging.INFO)

def get_current_user():
    return session.get('username', 'System_User')

def get_current_tenant_id():
    return session.get('tenant_id', 'default_tenant_placeholder')

@payment_bp.route('/', methods=['POST'], strict_slashes=False)
def handle_record_payment():
    """
    API endpoint to record a new payment and apply it to invoices.
    """
    if not request.json:
        return jsonify({"message": "No JSON data provided"}), 400

    data = request.json
    tenant_id = get_current_tenant_id()
    user = get_current_user()

    required_fields = ['customerId', 'amount', 'paymentDate', 'invoices']
    if not all(field in data for field in required_fields) or not data['invoices']:
        return jsonify({"message": "Missing required fields: customerId, amount, paymentDate, and at least one invoice."}), 400

    try:
        db = get_db()
        payment_id = record_payment(db, data, user, tenant_id)

        return jsonify({
            "message": "Payment recorded successfully",
            "data": {"paymentId": str(payment_id)}
        }), 201
    # Catch the specific ValueError for overpayments
    except ValueError as ve:
        logging.warning(f"Validation error in handle_record_payment: {ve}")
        return jsonify({"message": str(ve), "error": "Validation Error"}), 400
    except Exception as e:
        logging.error(f"Error in handle_record_payment for tenant {tenant_id}: {e}\n{traceback.format_exc()}")
        return jsonify({"message": "Failed to record payment", "error": str(e)}), 500
