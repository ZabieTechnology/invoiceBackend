# db/sales_invoice_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging
import re

from .activity_log_dal import add_activity
# We need to interact with inventory and its transactions
from .inventory_dal import add_stock_transaction

SALES_INVOICE_COLLECTION = 'sales_invoices'
logging.basicConfig(level=logging.INFO)

def create_sales_invoice(db_conn, invoice_data, user="System", tenant_id="default_tenant_placeholder"):
    """
    Creates a new sales invoice and, if the invoice is not a draft,
    updates the stock levels by creating stock transactions.
    """
    try:
        now = datetime.utcnow()
        invoice_data['created_date'] = now
        invoice_data['updated_date'] = now
        invoice_data['created_by'] = user
        invoice_data['tenant_id'] = tenant_id

        invoice_data.pop('_id', None)

        # Insert the invoice into the database
        result = db_conn[SALES_INVOICE_COLLECTION].insert_one(invoice_data)
        inserted_id = result.inserted_id
        logging.info(f"Sales Invoice '{inserted_id}' created by {user} for tenant {tenant_id}")

        add_activity(
            action_type="CREATE_SALES_INVOICE",
            user=user,
            details=f"Created Sales Invoice, Customer: {invoice_data.get('customerName', 'N/A')}",
            document_id=inserted_id,
            collection_name=SALES_INVOICE_COLLECTION,
            tenant_id=tenant_id
        )

        # If the invoice is not just a draft, process stock transactions
        if invoice_data.get('status') != 'Draft':
            for item in invoice_data.get('lineItems', []):
                if item.get('itemId'): # Ensure it's an inventory item
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
        logging.error(f"Error creating sales invoice for tenant {tenant_id}: {e}")
        raise

def get_sales_invoice_by_id(db_conn, invoice_id, tenant_id="default_tenant_placeholder"):
    try:
        return db_conn[SALES_INVOICE_COLLECTION].find_one({"_id": ObjectId(invoice_id), "tenant_id": tenant_id})
    except Exception as e:
        logging.error(f"Error fetching invoice by ID {invoice_id} for tenant {tenant_id}: {e}")
        raise

def get_all_sales_invoices(db_conn, page=1, limit=25, filters=None, tenant_id="default_tenant_placeholder"):
    try:
        query = filters if filters else {}
        query["tenant_id"] = tenant_id

        skip = (page - 1) * limit if limit > 0 else 0
        invoices_cursor = db_conn[SALES_INVOICE_COLLECTION].find(query).sort("invoiceDate", -1).skip(skip)

        if limit > 0:
            invoices_cursor = invoices_cursor.limit(limit)

        invoice_list = list(invoices_cursor)
        total_items = db_conn[SALES_INVOICE_COLLECTION].count_documents(query)
        return invoice_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all sales invoices for tenant {tenant_id}: {e}")
        raise

def update_sales_invoice(db_conn, invoice_id, update_data, user="System", tenant_id="default_tenant_placeholder"):
    # Note: A full implementation would require complex logic to handle changes
    # in line items and reverse/update stock transactions accordingly. This is a simplified version.
    try:
        now = datetime.utcnow()
        original_id_obj = ObjectId(invoice_id)

        update_data.pop('_id', None)
        update_payload = {
            "$set": {**update_data, "updated_date": now, "updated_by": user}
        }

        result = db_conn[SALES_INVOICE_COLLECTION].update_one(
            {"_id": original_id_obj, "tenant_id": tenant_id},
            update_payload
        )
        if result.matched_count > 0 and result.modified_count > 0:
            logging.info(f"Invoice {invoice_id} updated by {user} for tenant {tenant_id}")
            add_activity("UPDATE_INVOICE", user, f"Updated Invoice ID: {invoice_id}", original_id_obj, SALES_INVOICE_COLLECTION, tenant_id)

        return result.matched_count
    except Exception as e:
        logging.error(f"Error updating invoice {invoice_id} for tenant {tenant_id}: {e}")
        raise

def delete_sales_invoice(db_conn, invoice_id, user="System", tenant_id="default_tenant_placeholder"):
    # Note: Deleting a saved invoice should ideally create a credit note and reverse
    # stock transactions. This is a simplified direct delete.
    try:
        original_id_obj = ObjectId(invoice_id)

        invoice_to_delete = get_sales_invoice_by_id(db_conn, invoice_id, tenant_id)
        if not invoice_to_delete:
            return 0

        # Optional: Reverse stock transactions if invoice was not a draft
        if invoice_to_delete.get('status') != 'Draft':
             for item in invoice_to_delete.get('lineItems', []):
                if item.get('itemId'):
                    add_stock_transaction(
                        db_conn=db_conn, item_id=item['itemId'], transaction_type='IN',
                        quantity=item.get('quantity', 0), notes=f"Reversal for deleted Invoice #{invoice_to_delete.get('invoiceNumber', invoice_id)}",
                        user=user, tenant_id=tenant_id
                    )

        result = db_conn[SALES_INVOICE_COLLECTION].delete_one({"_id": original_id_obj, "tenant_id": tenant_id})

        if result.deleted_count > 0:
            logging.info(f"Invoice {invoice_id} deleted by {user} for tenant {tenant_id}.")
            add_activity("DELETE_INVOICE", user, f"Deleted Invoice ID: {invoice_id}", original_id_obj, SALES_INVOICE_COLLECTION, tenant_id)

        return result.deleted_count
    except Exception as e:
        logging.error(f"Error deleting invoice {invoice_id} for tenant {tenant_id}: {e}")
        raise
