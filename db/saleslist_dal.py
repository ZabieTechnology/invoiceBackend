# db/saleslist_dal.py
from bson.objectid import ObjectId
from datetime import datetime, timedelta
import logging
import re
import json # For parsing lineItems if it's a string

from .database import mongo
from .activity_log_dal import add_activity

SALES_INVOICE_COLLECTION = 'sales_invoices' # Collection name for sales invoices
CUSTOMER_COLLECTION = 'customers' # For customer lookups

def parse_date_for_dal(date_input):
    """Converts string date (YYYY-MM-DD or DD/MM/YYYY) to datetime object, handles None."""
    if not date_input:
        return None
    if isinstance(date_input, datetime):
        return date_input
    try:
        # Frontend sends YYYY-MM-DD from DatePicker when formatted with formatDateFns
        return datetime.strptime(str(date_input).split('T')[0], '%Y-%m-%d')
    except ValueError:
        try:
            return datetime.strptime(str(date_input), '%d/%m/%Y')
        except ValueError:
            logging.warning(f"Could not parse date: {date_input} with YYYY-MM-DD or DD/MM/YYYY format.")
            return None

def parse_float_for_dal(value_input, field_name="field", default_value=0.0):
    """Converts a value to float, handling None, empty strings, and commas."""
    if value_input is None or str(value_input).strip() == '':
        return default_value
    try:
        # Remove commas for robust parsing, keep decimal point
        cleaned_value = str(value_input).replace(',', '')
        return float(cleaned_value)
    except (ValueError, TypeError):
        logging.warning(f"Could not convert {field_name} '{value_input}' to float. Defaulting to {default_value}.")
        return default_value

def create_sales_invoice(invoice_data, user="System", tenant_id="default_tenant"):
    """
    Creates a new sales invoice document in the database.
    'invoice_data' is expected to match the structure from CreateSalesInvoicePage.js.
    """
    try:
        db = mongo.db
        now = datetime.utcnow()

        payload = {
            "invoiceNumber": invoice_data.get("invoiceNumber"), # Frontend might send this or expect backend generation
            "invoiceDate": parse_date_for_dal(invoice_data.get("invoiceDate")),
            "dueDate": parse_date_for_dal(invoice_data.get("dueDate")),
            "customerId": ObjectId(invoice_data["customerId"]) if invoice_data.get("customerId") else None,
            "customerName": invoice_data.get("customerName"),
            "customerGstin": invoice_data.get("customerGstin"),
            "customerAddress": invoice_data.get("customerAddress"),
            "shipToAddress": invoice_data.get("shipToAddress"),
            "lineItems": [],
            "subTotal": parse_float_for_dal(invoice_data.get("subTotal"), "subTotal"),
            "discountType": invoice_data.get("discountType", "Percentage"),
            "discountValue": parse_float_for_dal(invoice_data.get("discountValue", 0), "discountValue"),
            "discountAmountCalculated": parse_float_for_dal(invoice_data.get("discountAmountCalculated", 0), "discountAmountCalculated"),
            "taxableAmount": parse_float_for_dal(invoice_data.get("taxableAmount"), "taxableAmount"),

            "cgstAmount": parse_float_for_dal(invoice_data.get("cgstAmount", 0), "cgstAmount"),
            "sgstAmount": parse_float_for_dal(invoice_data.get("sgstAmount", 0), "sgstAmount"),
            "igstAmount": parse_float_for_dal(invoice_data.get("igstAmount", 0), "igstAmount"),
            "cessAmount": parse_float_for_dal(invoice_data.get("cessAmount", 0), "cessAmount"),
            "taxTotal": parse_float_for_dal(invoice_data.get("taxTotal"), "taxTotal"),

            "grandTotal": parse_float_for_dal(invoice_data.get("grandTotal"), "grandTotal"),
            "amountPaid": parse_float_for_dal(invoice_data.get("amountPaid", 0), "amountPaid"),
            "balanceDue": 0.0,

            "notes": invoice_data.get("notes"),
            "termsAndConditions": invoice_data.get("termsAndConditions"),
            "currency": invoice_data.get("currency", "INR"),
            "bankAccountId": ObjectId(invoice_data["bankAccountId"]) if invoice_data.get("bankAccountId") else None,
            "signatureImageUrl": invoice_data.get("signatureImageUrl"), # Path or filename
            "status": invoice_data.get("status", "Draft"),

            "created_date": now,
            "updated_date": now,
            "updated_user": user,
            "tenant_id": tenant_id
        }

        # Ensure balanceDue is calculated correctly
        payload["balanceDue"] = round(payload["grandTotal"] - payload["amountPaid"], 2)

        line_items_raw = invoice_data.get("lineItems", [])
        # Frontend should send array, but handle string if it's from FormData
        if isinstance(line_items_raw, str):
            try: line_items_raw = json.loads(line_items_raw)
            except json.JSONDecodeError:
                logging.error("Failed to parse lineItems JSON string during invoice creation.")
                line_items_raw = []

        for item_data in line_items_raw:
            payload["lineItems"].append({
                "description": item_data.get("description"),
                "hsnSac": item_data.get("hsnSac"),
                "quantity": parse_float_for_dal(item_data.get("quantity"), "item.quantity", 1),
                "rate": parse_float_for_dal(item_data.get("rate"), "item.rate"),
                "discountPerItem": parse_float_for_dal(item_data.get("discountPerItem", 0), "item.discountPerItem"),
                "taxRate": parse_float_for_dal(item_data.get("taxRate", 0), "item.taxRate"),
                "taxAmount": parse_float_for_dal(item_data.get("taxAmount", 0), "item.taxAmount"),
                "amount": parse_float_for_dal(item_data.get("amount"), "item.amount"),
            })

        result = db[SALES_INVOICE_COLLECTION].insert_one(payload)
        inserted_id = result.inserted_id
        logging.info(f"Sales Invoice '{payload.get('invoiceNumber')}' created with ID: {inserted_id} by {user} for tenant {tenant_id}")
        add_activity("CREATE_SALES_INVOICE", user, f"Created Sales Invoice: {payload.get('invoiceNumber')}", inserted_id, SALES_INVOICE_COLLECTION, tenant_id)
        return inserted_id
    except Exception as e:
        logging.exception(f"Error creating sales invoice for tenant {tenant_id}: {e}")
        raise

def get_sales_invoice_by_id(invoice_id, tenant_id="default_tenant"):
    try:
        db = mongo.db
        pipeline = [
            {"$match": {"_id": ObjectId(invoice_id), "tenant_id": tenant_id}},
            {"$lookup": {"from": CUSTOMER_COLLECTION, "localField": "customerId", "foreignField": "_id", "as": "customerInfo"}},
            {"$unwind": {"path": "$customerInfo", "preserveNullAndEmptyArrays": True}},
            {"$addFields": {"customerNameDisplay": "$customerInfo.displayName"}}, # Use for display
            {"$project": {"customerInfo": 0}}
        ]
        result = list(db[SALES_INVOICE_COLLECTION].aggregate(pipeline))
        return result[0] if result else None
    except Exception as e:
        logging.error(f"Error fetching sales invoice by ID {invoice_id} for tenant {tenant_id}: {e}")
        raise

def get_all_sales_invoices_paginated(page=1, limit=10, filters=None, sort_by='invoiceDate', sort_order=-1, tenant_id="default_tenant"):
    try:
        db = mongo.db
        pipeline = []
        match_stage = {"tenant_id": tenant_id}

        if filters:
            if filters.get("status") and filters["status"].lower() != "all":
                match_stage["status"] = filters["status"]

            # Text search on denormalized customerName or invoiceNumber
            # If searching on actual customer name, the $lookup must happen before this $match
            if filters.get("search"):
                regex_query = {"$regex": re.escape(filters["search"]), "$options": "i"}
                # This search happens on fields available before lookup
                match_stage["$or"] = [
                    {"invoiceNumber": regex_query},
                    {"customerName": regex_query} # Denormalized name stored with invoice
                ]

            if filters.get('dateFrom') and filters.get('dateTo'):
                 match_stage['invoiceDate'] = {"$gte": filters['dateFrom'], "$lte": filters['dateTo']}
            elif filters.get('dateFrom'):
                 match_stage['invoiceDate'] = {"$gte": filters['dateFrom']}
            elif filters.get('dateTo'):
                 match_stage['invoiceDate'] = {"$lte": filters['dateTo']}

        pipeline.append({"$match": match_stage})

        # Lookup customer information to get the most current display name
        pipeline.extend([
            {"$lookup": {"from": CUSTOMER_COLLECTION, "localField": "customerId", "foreignField": "_id", "as": "customerInfo"}},
            {"$unwind": {"path": "$customerInfo", "preserveNullAndEmptyArrays": True}},
            # Use customerInfo.displayName if available, otherwise fallback to stored customerName
            {"$addFields": {
                "customerNameDisplay": {"$ifNull": ["$customerInfo.displayName", "$customerName", "Unknown Customer"]}
            }}
        ])

        # If search term needs to search on actual customer name from lookup (more accurate):
        # This would replace/augment the search on the denormalized customerName
        # if filters and filters.get("search"):
        #     regex_query = {"$regex": re.escape(filters["search"]), "$options": "i"}
        #     pipeline.append({"$match": {
        #         "$or": [
        #             {"invoiceNumber": regex_query},
        #             {"customerNameDisplay": regex_query}
        #         ]
        #     }})


        # Count total matching documents *after* all relevant $match stages
        count_pipeline = pipeline + [{"$count": "totalItems"}]
        total_items_result = list(db[SALES_INVOICE_COLLECTION].aggregate(count_pipeline))
        total_items = total_items_result[0]['totalItems'] if total_items_result else 0

        pipeline.append({"$sort": {sort_by: sort_order}})

        skip = (page - 1) * limit if limit > 0 else 0
        if limit > 0:
            pipeline.append({"$skip": skip})
            pipeline.append({"$limit": limit})

        pipeline.append({"$project": {"customerInfo": 0}}) # Remove full customerInfo object from final result

        invoice_list = list(db[SALES_INVOICE_COLLECTION].aggregate(pipeline))
        return invoice_list, total_items
    except Exception as e:
        logging.exception(f"Error fetching all sales invoices for tenant {tenant_id}: {e}")
        raise

def update_sales_invoice(invoice_id, update_data, user="System", tenant_id="default_tenant"):
    try:
        db = mongo.db
        now = datetime.utcnow()
        original_id_obj = ObjectId(invoice_id)
        payload_to_set = {"updated_date": now, "updated_user": user}

        allowed_fields = [
            "invoiceNumber", "invoiceDate", "dueDate", "customerId", "customerName",
            "customerGstin", "customerAddress", "shipToAddress",
            "subTotal", "discountType", "discountValue", "discountAmountCalculated",
            "taxableAmount", "cgstAmount", "sgstAmount", "igstAmount", "cessAmount", "taxTotal",
            "grandTotal", "amountPaid",
            "status", "termsAndConditions", "notes", "paymentDetails", "currency",
            "bankAccountId", "signatureImageUrl"
        ]
        for field in allowed_fields:
            if field in update_data:
                if field in ["invoiceDate", "dueDate"]:
                    payload_to_set[field] = parse_date_for_dal(update_data[field])
                elif field == "customerId" and update_data[field]:
                    payload_to_set[field] = ObjectId(update_data[field])
                elif field == "bankAccountId" and update_data[field]:
                    payload_to_set[field] = ObjectId(update_data[field])
                elif field in ["subTotal", "discountValue", "discountAmountCalculated", "taxableAmount",
                               "cgstAmount", "sgstAmount", "igstAmount", "cessAmount", "taxTotal",
                               "grandTotal", "amountPaid"]:
                    payload_to_set[field] = parse_float_for_dal(update_data[field], field, 0.0) # Default to 0.0 for updates
                else:
                    payload_to_set[field] = update_data[field]

        # Recalculate balanceDue based on potentially updated grandTotal and amountPaid
        gt_for_balance = payload_to_set.get("grandTotal")
        ap_for_balance = payload_to_set.get("amountPaid")

        if gt_for_balance is None or ap_for_balance is None: # If one is missing in update, fetch existing
            existing_invoice = db[SALES_INVOICE_COLLECTION].find_one({"_id": original_id_obj}, {"grandTotal": 1, "amountPaid": 1})
            if existing_invoice:
                if gt_for_balance is None: gt_for_balance = existing_invoice.get("grandTotal", 0.0)
                if ap_for_balance is None: ap_for_balance = existing_invoice.get("amountPaid", 0.0)

        payload_to_set["balanceDue"] = round( (gt_for_balance or 0.0) - (ap_for_balance or 0.0), 2)


        if "lineItems" in update_data:
            line_items_raw = update_data["lineItems"]
            if isinstance(line_items_raw, str): # Should be array from frontend
                try: line_items_raw = json.loads(line_items_raw)
                except json.JSONDecodeError: line_items_raw = []

            processed_line_items = []
            for item_data in line_items_raw:
                 processed_line_items.append({
                    "description": item_data.get("description"),
                    "hsnSac": item_data.get("hsnSac"),
                    "quantity": parse_float_for_dal(item_data.get("quantity"), "item.quantity", 1),
                    "rate": parse_float_for_dal(item_data.get("rate"), "item.rate"),
                    "discountPerItem": parse_float_for_dal(item_data.get("discountPerItem", 0), "item.discountPerItem"),
                    "taxRate": parse_float_for_dal(item_data.get("taxRate", 0), "item.taxRate"),
                    "taxAmount": parse_float_for_dal(item_data.get("taxAmount", 0), "item.taxAmount"),
                    "amount": parse_float_for_dal(item_data.get("amount"), "item.amount"),
                })
            payload_to_set["lineItems"] = processed_line_items

        if not payload_to_set or len(payload_to_set) <= 2:
            return 0

        result = db[SALES_INVOICE_COLLECTION].update_one(
            {"_id": original_id_obj, "tenant_id": tenant_id},
            {"$set": payload_to_set}
        )
        if result.matched_count > 0:
            logging.info(f"Sales Invoice {invoice_id} updated by {user}")
            add_activity("UPDATE_SALES_INVOICE", user, f"Updated Sales Invoice ID: {invoice_id}", original_id_obj, SALES_INVOICE_COLLECTION, tenant_id)
        return result.matched_count
    except Exception as e:
        logging.exception(f"Error updating sales invoice {invoice_id}: {e}")
        raise

def delete_sales_invoice_by_id(invoice_id, user="System", tenant_id="default_tenant"):
    try:
        db = mongo.db
        original_id_obj = ObjectId(invoice_id)
        doc_to_delete = db[SALES_INVOICE_COLLECTION].find_one({"_id": original_id_obj, "tenant_id": tenant_id})

        result = db[SALES_INVOICE_COLLECTION].delete_one({"_id": original_id_obj, "tenant_id": tenant_id})
        if result.deleted_count > 0:
            doc_ref = doc_to_delete.get('invoiceNumber', str(original_id_obj)) if doc_to_delete else str(original_id_obj)
            logging.info(f"Sales Invoice {invoice_id} ('{doc_ref}') deleted by {user}.")
            add_activity("DELETE_SALES_INVOICE", user, f"Deleted Sales Invoice: '{doc_ref}' (ID: {invoice_id})", original_id_obj, SALES_INVOICE_COLLECTION, tenant_id)
        return result.deleted_count
    except Exception as e:
        logging.error(f"Error deleting sales invoice {invoice_id}: {e}")
        raise

def get_sales_summary_data(tenant_id="default_tenant"):
    try:
        db = mongo.db; now = datetime.utcnow()
        summary = {"totalInvoices": 0, "totalSales": 0.0, "salesReturn": 0.0, "yetToPublish": 0, "totalReceivables": 0.0, "percentOverdue": 0.0, "aging": {"0-30": 0.0, "31-60": 0.0, "61-90": 0.0, "90+": 0.0}}
        summary["totalInvoices"] = db[SALES_INVOICE_COLLECTION].count_documents({"tenant_id": tenant_id})
        summary["yetToPublish"] = db[SALES_INVOICE_COLLECTION].count_documents({"tenant_id": tenant_id, "status": "Draft"})
        sales_result = list(db[SALES_INVOICE_COLLECTION].aggregate([{"$match": {"tenant_id": tenant_id, "status": {"$in": ["Paid", "Partially Paid", "Sent", "Overdue"]}}}, {"$group": {"_id": None, "total": {"$sum": "$grandTotal"}}}]))
        if sales_result: summary["totalSales"] = sales_result[0].get("total", 0.0)

        aging_data = list(db[SALES_INVOICE_COLLECTION].aggregate([{"$match": {"tenant_id": tenant_id, "status": {"$in": ["Sent", "Partially Paid", "Overdue"]}, "balanceDue": {"$gt": 0}, "dueDate": {"$ne": None} }}, {"$project": {"balanceDue": 1, "dueDate": 1, "daysOverdue": {"$cond": { "if": {"$lt": ["$dueDate", now]}, "then": {"$divide": [{"$subtract": [now, "$dueDate"]}, 1000 * 60 * 60 * 24]}, "else": 0 }} }}]))
        total_overdue_amount = 0
        for inv in aging_data:
            balance = inv.get("balanceDue", 0); summary["totalReceivables"] += balance; days_overdue = inv.get("daysOverdue", 0)
            if days_overdue > 0:
                total_overdue_amount += balance
                if 0 < days_overdue <= 30: summary["aging"]["0-30"] += balance
                elif 30 < days_overdue <= 60: summary["aging"]["31-60"] += balance
                elif 60 < days_overdue <= 90: summary["aging"]["61-90"] += balance
                else: summary["aging"]["90+"] += balance
        if summary["totalReceivables"] > 0: summary["percentOverdue"] = round((total_overdue_amount / summary["totalReceivables"]) * 100, 2)
        for key in summary["aging"]: summary["aging"][key] = round(summary["aging"][key], 2)
        summary["totalSales"] = round(summary["totalSales"], 2)
        summary["totalReceivables"] = round(summary["totalReceivables"], 2)
        return summary
    except Exception as e: logging.exception(f"Error fetching sales summary data: {e}"); raise

def get_accounts_receivable_aging(tenant_id="default_tenant"):
    try:
        db = mongo.db; now = datetime.utcnow()
        pipeline = [ {"$match": {"tenant_id": tenant_id, "status": {"$in": ["Sent", "Partially Paid", "Overdue"]}, "balanceDue": {"$gt": 0}, "dueDate": {"$ne": None} }}, {"$lookup": {"from": CUSTOMER_COLLECTION, "localField": "customerId", "foreignField": "_id", "as": "customerInfo"}}, {"$unwind": {"path": "$customerInfo", "preserveNullAndEmptyArrays": True}}, {"$project": {"customerName": {"$ifNull": ["$customerInfo.displayName", "$customerName", "Unknown Customer"]}, "balanceDue": 1, "daysOverdue": {"$cond": { "if": {"$lt": ["$dueDate", now]}, "then": {"$divide": [{"$subtract": [now, "$dueDate"]}, 1000 * 60 * 60 * 24]}, "else": 0 }} }}, {"$group": {"_id": "$customerName", "totalDue": {"$sum": "$balanceDue"}, "bucket_1_30": {"$sum": {"$cond": [{"$and": [{"$gt": ["$daysOverdue", 0]}, {"$lte": ["$daysOverdue", 30]}]}, "$balanceDue", 0]}}, "bucket_31_60": {"$sum": {"$cond": [{"$and": [{"$gt": ["$daysOverdue", 30]}, {"$lte": ["$daysOverdue", 60]}]}, "$balanceDue", 0]}}, "bucket_61_90": {"$sum": {"$cond": [{"$and": [{"$gt": ["$daysOverdue", 60]}, {"$lte": ["$daysOverdue", 90]}]}, "$balanceDue", 0]}}, "bucket_90_plus": {"$sum": {"$cond": [{"$gt": ["$daysOverdue", 90]}, "$balanceDue", 0]}} }}, {"$project": {"_id": 0, "customerName": "$_id", "totalDue": {"$round": ["$totalDue", 2]}, "days_1_30": {"$round": ["$bucket_1_30", 2]}, "days_31_60": {"$round": ["$bucket_31_60", 2]}, "days_61_90": {"$round": ["$bucket_61_90", 2]}, "days_90_plus": {"$round": ["$bucket_90_plus", 2]} }}, {"$sort": {"customerName": 1}} ]
        return list(db[SALES_INVOICE_COLLECTION].aggregate(pipeline))
    except Exception as e: logging.exception(f"Error fetching accounts receivable aging: {e}"); raise