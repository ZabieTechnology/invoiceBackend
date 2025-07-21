# db/sales_invoices_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging
import re
import traceback
from pymongo import ReturnDocument
from pymongo.errors import WriteError

from .activity_log_dal import add_activity
from .inventory_dal import add_stock_transaction
from .invoice_settings_dal import get_invoice_settings

SALES_INVOICE_COLLECTION = 'sales_invoices'
INVOICE_SETTINGS_COLLECTION = 'invoice_settings'
INVENTORY_COLLECTION = 'inventory'
logging.basicConfig(level=logging.INFO)

def _serialize_invoice(invoice):
    if not invoice: return None
    if '_id' in invoice and isinstance(invoice.get('_id'), ObjectId): invoice['_id'] = str(invoice['_id'])
    if 'customer' in invoice and isinstance(invoice.get('customer'), dict):
        if '_id' in invoice['customer'] and isinstance(invoice['customer'].get('_id'), ObjectId): invoice['customer']['_id'] = str(invoice['customer']['_id'])
    if 'lineItems' in invoice and isinstance(invoice.get('lineItems'), list):
        for item in invoice['lineItems']:
            if 'itemId' in item and isinstance(item.get('itemId'), ObjectId): item['itemId'] = str(item['itemId'])
    return invoice

def create_sales_invoice(db_conn, invoice_data, user="System", tenant_id="default_tenant_placeholder"):
    """
    Creates a new sales invoice, validates stock only for products, and ensures customer data is nested.
    """
    try:
        # --- START: Stock Validation Logic ---
        if not invoice_data.get("ignoreStockWarning", False):
            inventory_collection = db_conn[INVENTORY_COLLECTION]
            items_with_insufficient_stock = []

            for item in invoice_data.get('lineItems', []):
                # UPDATED: Only check stock for items explicitly marked as 'product'
                if item.get('itemType') == 'product':
                    item_id_str = item.get('itemId')
                    if not item_id_str: continue

                    try:
                        item_id_obj = ObjectId(item_id_str)
                    except Exception:
                        logging.warning(f"Invalid itemId format '{item_id_str}'. Skipping stock check.")
                        continue

                    inventory_item = inventory_collection.find_one({"_id": item_id_obj, "tenant_id": tenant_id})
                    if inventory_item:
                        stock_in_hand = float(inventory_item.get('stockInHand', 0))
                        quantity_to_sell = float(item.get('quantity', 0))
                        if quantity_to_sell > stock_in_hand:
                            items_with_insufficient_stock.append(
                                f"{inventory_item.get('itemName', 'item')} (Requested: {quantity_to_sell}, Available: {stock_in_hand})"
                            )

            if items_with_insufficient_stock:
                error_message = "Insufficient stock for: " + ", ".join(items_with_insufficient_stock)
                # Use a specific error type or code if needed for frontend handling
                raise ValueError(error_message)
        # --- END: Stock Validation Logic ---

        now = datetime.utcnow()
        settings_collection = db_conn[INVOICE_SETTINGS_COLLECTION]

        settings = get_invoice_settings(db_conn, tenant_id)

        try:
            next_number = int(settings.get('global', {}).get('nextInvoiceNumber', 1))
        except (ValueError, TypeError):
            next_number = 1

        try:
            settings_collection.update_one(
                {"_id": ObjectId(settings['_id']) if settings.get('_id') else None},
                {"$inc": {"global.nextInvoiceNumber": 1}},
                upsert=True
            )
        except WriteError as e:
            if "non-numeric type" in str(e):
                logging.warning(f"Correcting non-numeric nextInvoiceNumber in database for tenant {tenant_id}.")
                settings_collection.update_one(
                    {"_id": ObjectId(settings['_id']) if settings.get('_id') else None},
                    {"$set": {"global.nextInvoiceNumber": next_number + 1}}
                )
            else:
                raise

        selected_theme_id = invoice_data.get('selectedThemeProfileId')
        all_themes = settings.get('savedThemes', [])

        selected_theme = None
        if selected_theme_id and all_themes:
            selected_theme = next((theme for theme in all_themes if theme.get('id') == selected_theme_id), None)

        if not selected_theme and all_themes:
            selected_theme = next((theme for theme in all_themes if theme.get('isDefault')), all_themes[0])
        elif not selected_theme:
            selected_theme = {}

        if selected_theme and 'accountLinkSettings' in selected_theme:
            invoice_data['accountLinkSettings'] = selected_theme.get('accountLinkSettings')

        if selected_theme and 'customHeaderFields' in selected_theme:
            for field in selected_theme.get('customHeaderFields', []):
                field_id = field.get('id')
                field_type = field.get('type')
                if field_id in invoice_data and invoice_data[field_id]:
                    try:
                        if field_type == 'date':
                            date_str = invoice_data[field_id]
                            if date_str:
                                invoice_data[field_id] = datetime.strptime(date_str.split('T')[0], '%Y-%m-%d')
                        elif field_type == 'number':
                            invoice_data[field_id] = float(invoice_data[field_id])
                    except (ValueError, TypeError) as e:
                        logging.warning(f"Could not convert custom field {field_id} with value {invoice_data[field_id]} to type {field_type}: {e}")

        if selected_theme.get('taxDisplayMode') == 'no_tax':
            sub_total = 0
            for item in invoice_data.get('lineItems', []):
                qty = float(item.get('quantity', 0))
                rate = float(item.get('rate', 0))
                discount = float(item.get('discountPerItem', 0))
                taxable_value = (qty * rate) - discount

                item['taxRate'] = 0
                item['taxAmount'] = 0
                item['cgstAmount'] = 0
                item['sgstAmount'] = 0
                item['igstAmount'] = 0
                item['amount'] = taxable_value
                sub_total += taxable_value

            invoice_data['subTotal'] = sub_total
            invoice_data['taxTotal'] = 0
            invoice_data['cgstAmount'] = 0
            invoice_data['sgstAmount'] = 0
            invoice_data['igstAmount'] = 0

            discount_value_str = str(invoice_data.get('discountValue', '0'))
            discount_amount = 0
            if '%' in discount_value_str:
                percentage = float(discount_value_str.replace('%', ''))
                discount_amount = (sub_total * percentage) / 100
            else:
                discount_amount = float(discount_value_str)

            invoice_data['discountAmountCalculated'] = discount_amount

            grand_total = sub_total - discount_amount
            invoice_data['grandTotal'] = grand_total
            invoice_data['balanceDue'] = grand_total - float(invoice_data.get('amountPaid', 0))


        prefix = selected_theme.get('invoicePrefix', '')
        suffix = selected_theme.get('invoiceSuffix', '')
        invoice_data['invoiceNumber'] = f"{prefix}{next_number}{suffix}"

        customer_id = invoice_data.pop('customerId', None)
        customer_name = invoice_data.pop('customerName', 'N/A')
        invoice_data['customer'] = {
            '_id': customer_id,
            'name': customer_name
        }

        invoice_data['created_date'] = now
        invoice_data['updated_date'] = now
        invoice_data['created_by'] = user
        invoice_data['tenant_id'] = tenant_id
        invoice_data.pop('_id', None)

        result = db_conn[SALES_INVOICE_COLLECTION].insert_one(invoice_data)
        inserted_id = result.inserted_id

        logging.info(f"Successfully created invoice {invoice_data['invoiceNumber']} with ID {inserted_id}")

        add_activity("CREATE_SALES_INVOICE", user, f"Created Sales Invoice: {invoice_data['invoiceNumber']}, Customer: {customer_name}", inserted_id, SALES_INVOICE_COLLECTION, tenant_id)

        # UPDATED: Only create stock transactions for products
        if invoice_data.get('status') != 'Draft':
            for item in invoice_data.get('lineItems', []):
                if item.get('itemId') and item.get('itemType') == 'product':
                    add_stock_transaction(db_conn=db_conn, item_id=item['itemId'], transaction_type='OUT', quantity=item.get('quantity', 0), price_per_item=item.get('rate'), notes=f"Sale against Invoice #{invoice_data.get('invoiceNumber', inserted_id)}", user=user, tenant_id=tenant_id)

        created_invoice = get_sales_invoice_by_id(db_conn, str(inserted_id), tenant_id)
        return created_invoice
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
    try:
        query = filters if filters else {}
        query["tenant_id"] = tenant_id
        skip = (page - 1) * limit if limit > 0 else 0
        if limit == -1: invoices_cursor = db_conn[SALES_INVOICE_COLLECTION].find(query).sort("invoiceDate", -1)
        else: invoices_cursor = db_conn[SALES_INVOICE_COLLECTION].find(query).sort("invoiceDate", -1).skip(skip).limit(limit)
        invoice_list = list(invoices_cursor)
        serialized_list = [_serialize_invoice(invoice) for invoice in invoice_list]
        total_items = db_conn[SALES_INVOICE_COLLECTION].count_documents(query)
        return serialized_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all sales invoices for tenant {tenant_id}: {e}\n{traceback.format_exc()}")
        raise

def update_sales_invoice(db_conn, invoice_id, update_data, user="System", tenant_id="default_tenant_placeholder"):
    try:
        now = datetime.utcnow()
        original_id_obj = ObjectId(invoice_id)

        # Get the original invoice to compare status
        original_invoice = db_conn[SALES_INVOICE_COLLECTION].find_one({"_id": original_id_obj, "tenant_id": tenant_id})
        if not original_invoice:
            return 0 # Or raise an error

        original_status = original_invoice.get('status', 'Draft')
        new_status = update_data.get('status', original_status)

        update_data.pop('_id', None)
        update_payload = {"$set": {**update_data, "updated_date": now, "updated_by": user}}
        result = db_conn[SALES_INVOICE_COLLECTION].update_one({"_id": original_id_obj, "tenant_id": tenant_id}, update_payload)

        if result.matched_count > 0 and result.modified_count > 0:
            add_activity("UPDATE_INVOICE", user, f"Updated Invoice ID: {invoice_id}", original_id_obj, SALES_INVOICE_COLLECTION, tenant_id)

            # --- Add stock transaction logic ---
            if original_status == 'Draft' and new_status != 'Draft':
                logging.info(f"Invoice {invoice_id} status changed from Draft. Adjusting stock.")
                for item in update_data.get('lineItems', []):
                    if item.get('itemId') and item.get('itemType') == 'product':
                        add_stock_transaction(
                            db_conn=db_conn,
                            item_id=item['itemId'],
                            transaction_type='OUT',
                            quantity=item.get('quantity', 0),
                            price_per_item=item.get('rate'),
                            notes=f"Sale against Invoice #{update_data.get('invoiceNumber', invoice_id)}",
                            user=user,
                            tenant_id=tenant_id
                        )
            # (More complex logic for other status changes/item updates could be added here)

        return result.matched_count
    except Exception as e:
        logging.error(f"Error updating invoice {invoice_id} for tenant {tenant_id}: {e}\n{traceback.format_exc()}")
        raise

def delete_sales_invoice(db_conn, invoice_id, user="System", tenant_id="default_tenant_placeholder"):
    try:
        original_id_obj = ObjectId(invoice_id)
        invoice_to_delete = get_sales_invoice_by_id(db_conn, invoice_id, tenant_id)
        if not invoice_to_delete: return 0
        if invoice_to_delete.get('status') != 'Draft':
             for item in invoice_to_delete.get('lineItems', []):
                if item.get('itemId'):
                    add_stock_transaction(db_conn=db_conn, item_id=item['itemId'], transaction_type='IN', quantity=item.get('quantity', 0), notes=f"Reversal for deleted Invoice #{invoice_to_delete.get('invoiceNumber', invoice_id)}", user=user, tenant_id=tenant_id)
        result = db_conn[SALES_INVOICE_COLLECTION].delete_one({"_id": original_id_obj, "tenant_id": tenant_id})
        if result.deleted_count > 0:
            add_activity("DELETE_INVOICE", user, f"Deleted Invoice ID: {invoice_id}", original_id_obj, SALES_INVOICE_COLLECTION, tenant_id)
        return result.deleted_count
    except Exception as e:
        logging.error(f"Error deleting invoice {invoice_id} for tenant {tenant_id}: {e}\n{traceback.format_exc()}")
        raise

def update_sales_invoice_payment_status(db_conn, invoice_id, new_amount_paid, tenant_id):
    """
    Updates the payment status of an invoice based on the total amount paid.
    Validates that the total paid amount does not exceed the invoice total.
    """
    try:
        invoice = db_conn[SALES_INVOICE_COLLECTION].find_one({"_id": ObjectId(invoice_id), "tenant_id": tenant_id})
        if not invoice:
            logging.warning(f"update_sales_invoice_payment_status: Invoice {invoice_id} not found.")
            raise ValueError(f"Invoice with ID {invoice_id} not found.")

        grand_total = float(invoice.get('grandTotal', 0))

        # --- START: Overpayment Validation ---
        # Add a small tolerance (e.g., 0.01) for floating point comparisons
        if new_amount_paid > (grand_total + 0.01):
            error_msg = f"Payment for invoice {invoice.get('invoiceNumber')} exceeds amount due. Amount Due: {grand_total}, Submitted Total Paid: {new_amount_paid}."
            logging.warning(error_msg)
            raise ValueError(error_msg)
        # --- END: Overpayment Validation ---

        current_status = invoice.get('status')
        new_status = current_status
        new_balance_due = grand_total - new_amount_paid

        logging.info(f"Checking status for Invoice {invoice_id}: Grand Total=${grand_total}, New Amount Paid=${new_amount_paid}, Current Status='{current_status}'")

        # Use a small tolerance for floating point comparison to determine if paid
        if new_amount_paid >= (grand_total - 0.01):
            new_status = 'Paid'
            new_balance_due = 0 # Ensure balance is exactly zero if paid
        elif new_amount_paid > 0:
            new_status = 'Partially Paid'

        # If for some reason a payment was reversed, it might go back to Approved
        else:
            new_status = 'Approved'


        logging.info(f"Determined new status for Invoice {invoice_id} should be '{new_status}'.")

        update_fields = {
            "status": new_status,
            "balanceDue": new_balance_due,
            "amountPaid": new_amount_paid # Also update the amountPaid field
        }

        # Check if anything actually changed before updating
        if new_status != current_status or invoice.get('balanceDue') != new_balance_due:
            result = db_conn[SALES_INVOICE_COLLECTION].update_one(
                {"_id": ObjectId(invoice_id)},
                {"$set": update_fields}
            )
            logging.info(f"Updated payment status for invoice {invoice_id}. Status: '{new_status}', Balance Due: {new_balance_due}. Matched: {result.matched_count}, Modified: {result.modified_count}")
        else:
            logging.info(f"No payment status update needed for invoice {invoice_id}. Status remains '{current_status}'.")

    except ValueError as ve:
        # Re-raise the ValueError to be caught by the API layer
        raise ve
    except Exception as e:
        logging.error(f"Error updating payment status for invoice {invoice_id}: {e}\n{traceback.format_exc()}")
        raise Exception(f"An unexpected error occurred while updating payment status for invoice {invoice_id}.")
