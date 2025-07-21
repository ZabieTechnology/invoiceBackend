# db/payment_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging
import traceback

from .activity_log_dal import add_activity
# Import the function that will be added to the sales_invoice_dal
from .sales_invoices_dal import update_sales_invoice_payment_status

PAYMENTS_COLLECTION = 'payments'
SALES_INVOICE_COLLECTION = 'sales_invoices'
logging.basicConfig(level=logging.INFO)

def record_payment(db_conn, payment_data, user, tenant_id):
    """
    Records a new payment, allocates it to selected invoices,
    and updates the status of those invoices.
    """
    try:
        payments_collection = db_conn[PAYMENTS_COLLECTION]
        invoices_collection = db_conn[SALES_INVOICE_COLLECTION]

        now = datetime.utcnow()
        payment_amount = float(payment_data.get('amount', 0))
        invoice_ids_str = payment_data.get('invoices', [])

        if not invoice_ids_str:
            raise ValueError("No invoices selected for payment.")

        invoice_ids_obj = [ObjectId(id_str) for id_str in invoice_ids_str]

        # --- START: Overpayment Validation ---
        # This pipeline now calculates the due amount on the fly for accuracy,
        # matching the frontend's logic. It also converts fields to numbers
        # to prevent type mismatch errors during subtraction.
        pipeline = [
            {'$match': {'_id': {'$in': invoice_ids_obj}, 'tenant_id': tenant_id}},
            {'$project': {
                'due': {
                    '$subtract': [
                        {'$toDouble': {'$ifNull': ['$grandTotal', 0]}},
                        {'$toDouble': {'$ifNull': ['$amountPaid', 0]}}
                    ]
                }
            }},
            {'$group': {
                '_id': None,
                'totalDue': {'$sum': '$due'}
            }}
        ]

        result = list(invoices_collection.aggregate(pipeline))
        total_amount_due = result[0]['totalDue'] if result else 0

        # Add a small tolerance for floating point comparisons
        if payment_amount > (total_amount_due + 0.01):
            error_msg = f"Payment amount ({payment_amount}) exceeds total amount due ({total_amount_due})."
            logging.warning(error_msg)
            raise ValueError(error_msg)
        # --- END: Overpayment Validation ---


        payment_doc = {
            "tenant_id": tenant_id,
            "customerId": payment_data.get('customerId'),
            "paymentDate": datetime.strptime(payment_data.get('paymentDate'), '%Y-%m-%d'),
            "amount": payment_amount,
            "reference": payment_data.get('reference'),
            "created_date": now,
            "recorded_by": user,
            "applied_to": []
        }

        payment_result = payments_collection.insert_one(payment_doc)
        payment_id = payment_result.inserted_id
        logging.info(f"Payment {payment_id} recorded for customer {payment_data.get('customerId')}")

        amount_to_apply = payment_amount

        for invoice_id_str in invoice_ids_str:
            if amount_to_apply <= 0:
                break

            invoice_id = ObjectId(invoice_id_str)
            invoice = invoices_collection.find_one({"_id": invoice_id, "tenant_id": tenant_id})

            if not invoice:
                logging.warning(f"Invoice {invoice_id_str} not found for payment application.")
                continue

            grand_total = float(invoice.get('grandTotal', 0))
            amount_paid = float(invoice.get('amountPaid', 0))
            balance_due = grand_total - amount_paid

            payment_for_this_invoice = min(amount_to_apply, balance_due)

            new_amount_paid = amount_paid + payment_for_this_invoice

            # Use the dedicated function to update invoice status and amounts
            update_sales_invoice_payment_status(db_conn, str(invoice_id), new_amount_paid, tenant_id)

            payment_doc['applied_to'].append({
                "invoiceId": str(invoice_id),
                "amountApplied": payment_for_this_invoice
            })

            amount_to_apply -= payment_for_this_invoice

        payments_collection.update_one(
            {"_id": payment_id},
            {"$set": {"applied_to": payment_doc['applied_to']}}
        )

        add_activity("RECORD_PAYMENT", user, f"Recorded payment of {payment_amount}", payment_id, PAYMENTS_COLLECTION, tenant_id)

        return payment_id
    except ValueError as ve:
        # Re-raise the validation error to be caught by the API layer
        raise ve
    except Exception as e:
        logging.error(f"Error recording payment for tenant {tenant_id}: {e}\n{traceback.format_exc()}")
        raise
