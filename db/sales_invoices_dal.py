# db/sales_invoice_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging
import re
import traceback

from .activity_log_dal import add_activity
# We need to interact with inventory and its transactions
from .inventory_dal import add_stock_transaction
# ** FIX **: Import the settings DAL to get the next invoice number
from .invoice_settings_dal import get_invoice_settings

SALES_INVOICE_COLLECTION = 'sales_invoices'
INVOICE_SETTINGS_COLLECTION = 'invoice_settings'
logging.basicConfig(level=logging.INFO)

def _serialize_invoice(invoice):
    """
    Helper function to convert all ObjectId fields in an invoice document to strings.
    """
    if not invoice:
        return None

    # Convert the main _id
    if '_id' in invoice and isinstance(invoice.get('_id'), ObjectId):
        invoice['_id'] = str(invoice['_id'])

    # Convert _id within the nested customer object, if it exists
    if 'customer' in invoice and isinstance(invoice.get('customer'), dict):
        if '_id' in invoice['customer'] and isinstance(invoice['customer'].get('_id'), ObjectId):
            invoice['customer']['_id'] = str(invoice['customer']['_id'])

    # Loop through line items and convert the itemId to a string if it exists.
    if 'lineItems' in invoice and isinstance(invoice.get('lineItems'), list):
        for item in invoice['lineItems']:
            if 'itemId' in item and isinstance(item.get('itemId'), ObjectId):
                item['itemId'] = str(item['itemId'])

    return invoice


def create_sales_invoice(db_conn, invoice_data, user="System", tenant_id="default_tenant_placeholder"):
    """
    Creates a new sales invoice and, if the invoice is not a draft,
    updates the stock levels by creating stock transactions.
    """
    try:
        now = datetime.utcnow()
        settings_collection = db_conn[INVOICE_SETTINGS_COLLECTION]

        # ** FIX **: Get invoice settings to generate the invoice number
        settings = get_invoice_settings(db_conn, tenant_id)
        # Use .get() for safe access to potentially missing keys
        next_number = settings.get('global', {}).get('nextInvoiceNumber', 1)
        # Find the default theme profile to get the prefix
        default_theme = next((theme for theme in settings.get('savedThemes', []) if theme.get('isDefault')), None)
        prefix = default_theme.get('invoicePrefix', 'INV-') if default_theme else 'INV-'

        invoice_data['invoiceNumber'] = f"{prefix}{next_number}"
        invoice_data['created_date'] = now
        invoice_data['updated_date'] = now
        invoice_data['created_by'] = user
        invoice_data['tenant_id'] = tenant_id

        invoice_data.pop('_id', None)

        result = db_conn[SALES_INVOICE_COLLECTION].insert_one(invoice_data)
        inserted_id = result.inserted_id
        logging.info(f"Sales Invoice '{inserted_id}' created with number '{invoice_data['invoiceNumber']}' by {user} for tenant {tenant_id}")

        # Atomically increment the next invoice number in settings
        settings_collection.update_one(
            {"tenant_id": tenant_id},
            {"$inc": {"global.nextInvoiceNumber": 1}}
        )
        logging.info(f"Incremented nextInvoiceNumber for tenant '{tenant_id}'.")

        add_activity(
            action_type="CREATE_SALES_INVOICE",
            user=user,
            details=f"Created Sales Invoice: {invoice_data['invoiceNumber']}, Customer: {invoice_data.get('customerName', 'N/A')}",
            document_id=inserted_id,
            collection_name=SALES_INVOICE_COLLECTION,
            tenant_id=tenant_id
        )

        if invoice_data.get('status') != 'Draft':
            for item in invoice_data.get('lineItems', []):
                if item.get('itemId'):
                    add_stock_transaction(
                        db_conn=db_conn,
                        item_id=item['itemId'],
                        transaction_type='OUT',
                        quantity=item.get('quantity', 0),
                        price_per_item=item.get('rate'),
                        notes=f"Sale against Invoice #{invoice_data.get('invoiceNumber', inserted_id)}",
                        user=user,
                        tenant_id=tenant_id
                    )

        return inserted_id
    except ValueError as ve:
        raise
    except Exception as e:
        logging.error(f"Error creating sales invoice for tenant {tenant_id}: {e}\n{traceback.format_exc()}")
        raise

def get_sales_invoice_by_id(db_conn, invoice_id, tenant_id="default_tenant_placeholder"):
    try:
        invoice = db_conn[SALES_INVOICE_COLLECTION].find_one({"_id": ObjectId(invoice_id), "tenant_id": tenant_id})
        return _serialize_invoice(invoice)
    except Exception as e:
        logging.error(f"Error fetching invoice by ID {invoice_id} for tenant {tenant_id}: {e}\n{traceback.format_exc()}")
        raise

def get_all_sales_invoices(db_conn, page=1, limit=25, filters=None, tenant_id="default_tenant_placeholder"):
    """
    Fetches all sales invoices for a specific tenant.
    """
    try:
        query = filters if filters else {}
        query["tenant_id"] = tenant_id

        skip = (page - 1) * limit if limit > 0 else 0

        if limit == -1:
            invoices_cursor = db_conn[SALES_INVOICE_COLLECTION].find(query).sort("invoiceDate", -1)
        else:
             invoices_cursor = db_conn[SALES_INVOICE_COLLECTION].find(query).sort("invoiceDate", -1).skip(skip).limit(limit)

        invoice_list = list(invoices_cursor)

        serialized_list = []
        for invoice in invoice_list:
            try:
                serialized_list.append(_serialize_invoice(invoice))
            except Exception as serialization_error:
                logging.error(f"Failed to serialize invoice with ID: {invoice.get('_id')}. Error: {serialization_error}")
                raise

        total_items = db_conn[SALES_INVOICE_COLLECTION].count_documents(query)
        return serialized_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all sales invoices for tenant {tenant_id}: {e}\n{traceback.format_exc()}")
        raise

def update_sales_invoice(db_conn, invoice_id, update_data, user="System", tenant_id="default_tenant_placeholder"):
    try:
        now = datetime.utcnow()
        original_id_obj = ObjectId(invoice_id)
        update_data.pop('_id', None)
        update_payload = {"$set": {**update_data, "updated_date": now, "updated_by": user}}
        result = db_conn[SALES_INVOICE_COLLECTION].update_one({"_id": original_id_obj, "tenant_id": tenant_id}, update_payload)

        if result.matched_count > 0 and result.modified_count > 0:
            logging.info(f"Invoice {invoice_id} updated by {user} for tenant {tenant_id}")
            add_activity("UPDATE_INVOICE", user, f"Updated Invoice ID: {invoice_id}", original_id_obj, SALES_INVOICE_COLLECTION, tenant_id)
        return result.matched_count
    except Exception as e:
        logging.error(f"Error updating invoice {invoice_id} for tenant {tenant_id}: {e}\n{traceback.format_exc()}")
        raise

def delete_sales_invoice(db_conn, invoice_id, user="System", tenant_id="default_tenant_placeholder"):
    try:
        original_id_obj = ObjectId(invoice_id)
        invoice_to_delete = get_sales_invoice_by_id(db_conn, invoice_id, tenant_id)
        if not invoice_to_delete:
            return 0

        if invoice_to_delete.get('status') != 'Draft':
             for item in invoice_to_delete.get('lineItems', []):
                if item.get('itemId'):
                    add_stock_transaction(db_conn=db_conn, item_id=item['itemId'], transaction_type='IN', quantity=item.get('quantity', 0), notes=f"Reversal for deleted Invoice #{invoice_to_delete.get('invoiceNumber', invoice_id)}", user=user, tenant_id=tenant_id)

        result = db_conn[SALES_INVOICE_COLLECTION].delete_one({"_id": original_id_obj, "tenant_id": tenant_id})

        if result.deleted_count > 0:
            logging.info(f"Invoice {invoice_id} deleted by {user} for tenant {tenant_id}.")
            add_activity("DELETE_INVOICE", user, f"Deleted Invoice ID: {invoice_id}", original_id_obj, SALES_INVOICE_COLLECTION, tenant_id)
        return result.deleted_count
    except Exception as e:
        logging.error(f"Error deleting invoice {invoice_id} for tenant {tenant_id}: {e}\n{traceback.format_exc()}")
        raise
