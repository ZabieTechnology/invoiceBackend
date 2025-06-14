# db/customer_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging
import re # Import re for case-insensitive regex

from .activity_log_dal import add_activity

CUSTOMER_COLLECTION = 'customers'
logging.basicConfig(level=logging.INFO)


def create_customer_minimal(db_conn, display_name, payment_terms, user="System", tenant_id="default_tenant_placeholder", email="", mobile=""):
    """
    Creates a new customer with minimal information (displayName and paymentTerms).
    Other fields are set to defaults or None.
    Checks for displayName uniqueness (case-insensitive) within the tenant.
    """
    try:
        now = datetime.utcnow()

        # Check for existing customer with the same displayName (case-insensitive)
        existing_customer = db_conn[CUSTOMER_COLLECTION].find_one({
            "displayName": {"$regex": f"^{re.escape(display_name)}$", "$options": "i"},
            "tenant_id": tenant_id # Query uses the passed tenant_id
        })
        if existing_customer:
            raise ValueError(f"A customer with the display name '{display_name}' already exists.")

        customer_data = {
            "displayName": display_name,
            "paymentTerms": payment_terms,
            "customerType": "Business",
            "companyName": display_name,
            "salutation": None,
            "firstName": None,
            "lastName": None,
            "primaryContact": {
                "name": None,
                "email": email or "",
                "mobile": mobile or "",
                "phone": None,
                "skype": None,
                "designation": None,
                "department": None
            },
            "billingAddress": {
                "attention": None, "street": None, "city": None, "state": None,
                "zipCode": None, "country": None, "phone": None, "fax": None
            },
            "shippingAddress": {
                "attention": None, "street": None, "city": None, "state": None,
                "zipCode": None, "country": None, "phone": None, "fax": None
            },
            "gstTreatment": "UnregisteredBusiness",
            "gstNo": None,
            "placeOfSupply": None,
            "taxPreference": "Taxable",
            "currency": "INR",
            "openingBalance": 0.0,
            "asOfDate": now,
            "notes": None,
            "status": "Active",
            "created_date": now,
            "updated_date": now,
            "updated_user": user,
            "tenant_id": tenant_id # Use the passed tenant_id for saving
        }

        result = db_conn[CUSTOMER_COLLECTION].insert_one(customer_data)
        inserted_id = result.inserted_id
        logging.info(f"Minimal customer '{display_name}' created with ID: {inserted_id} by {user} for tenant {tenant_id}")

        add_activity(
            action_type="CREATE_CUSTOMER_MINIMAL",
            user=user,
            details=f"Created Customer (Minimal): Name='{display_name}', Payment Terms='{payment_terms}'",
            document_id=inserted_id,
            collection_name=CUSTOMER_COLLECTION,
            tenant_id=tenant_id
        )
        return inserted_id
    except ValueError as ve:
        raise
    except Exception as e:
        logging.error(f"Error creating minimal customer for tenant {tenant_id}: {e}")
        raise


def create_customer(db_conn, customer_data, user="System", tenant_id="default_tenant_placeholder"):
    """
    Creates a new customer document in the database with more complete data.
    Checks for displayName uniqueness (case-insensitive) within the tenant.
    """
    try:
        now = datetime.utcnow()

        display_name_to_check = customer_data.get("displayName")
        if not display_name_to_check:
            display_name_to_check = customer_data.get("companyName")

        if not display_name_to_check:
            raise ValueError("displayName or companyName is required to create a customer.")

        existing_customer = db_conn[CUSTOMER_COLLECTION].find_one({
            "displayName": {"$regex": f"^{re.escape(display_name_to_check)}$", "$options": "i"},
            "tenant_id": tenant_id
        })
        if existing_customer:
            raise ValueError(f"A customer with the display name '{display_name_to_check}' already exists.")

        customer_data.setdefault('primaryContact', {})
        customer_data.setdefault('billingAddress', {})
        customer_data.setdefault('shippingAddress', {})

        customer_data['created_date'] = now
        customer_data['updated_date'] = now
        customer_data['updated_user'] = user
        customer_data['tenant_id'] = tenant_id

        customer_data.pop('_id', None)

        result = db_conn[CUSTOMER_COLLECTION].insert_one(customer_data)
        inserted_id = result.inserted_id
        logging.info(f"Customer created with ID: {result.inserted_id} by {user} for tenant {tenant_id}")

        add_activity(
            action_type="CREATE_CUSTOMER",
            user=user,
            details=f"Created Customer: Name='{customer_data.get('displayName', customer_data.get('companyName', 'N/A'))}'",
            document_id=inserted_id,
            collection_name=CUSTOMER_COLLECTION,
            tenant_id=tenant_id
        )
        return inserted_id
    except ValueError as ve:
        raise
    except Exception as e:
        logging.error(f"Error creating customer for tenant {tenant_id}: {e}")
        raise

def get_customer_by_id(db_conn, customer_id, tenant_id="default_tenant_placeholder"):
    try:
        return db_conn[CUSTOMER_COLLECTION].find_one({"_id": ObjectId(customer_id), "tenant_id": tenant_id})
    except Exception as e:
        logging.error(f"Error fetching customer by ID {customer_id} for tenant {tenant_id}: {e}")
        raise

def get_all_customers(db_conn, page=1, limit=25, filters=None, tenant_id="default_tenant_placeholder"):
    try:
        query = filters if filters else {}
        query["tenant_id"] = tenant_id

        skip = (page - 1) * limit if limit > 0 and limit is not None else 0

        if limit is not None and limit > 0:
            customers_cursor = db_conn[CUSTOMER_COLLECTION].find(query).sort("displayName", 1).skip(skip).limit(limit)
        else:
            customers_cursor = db_conn[CUSTOMER_COLLECTION].find(query).sort("displayName", 1).skip(skip)

        customer_list = list(customers_cursor)
        total_items = db_conn[CUSTOMER_COLLECTION].count_documents(query)
        return customer_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all customers for tenant {tenant_id}: {e}")
        raise

def update_customer(db_conn, customer_id, update_data, user="System", tenant_id="default_tenant_placeholder"):
    try:
        now = datetime.utcnow()
        original_id_obj = ObjectId(customer_id)

        if "displayName" in update_data:
            display_name_to_check = update_data["displayName"]
            existing_customer = db_conn[CUSTOMER_COLLECTION].find_one({
                "_id": {"$ne": original_id_obj},
                "displayName": {"$regex": f"^{re.escape(display_name_to_check)}$", "$options": "i"},
                "tenant_id": tenant_id
            })
            if existing_customer:
                raise ValueError(f"Another customer with the display name '{display_name_to_check}' already exists.")

        update_data.pop('_id', None)

        update_payload = {
            "$set": {
                **update_data,
                "updated_date": now,
                "updated_user": user
            }
        }

        result = db_conn[CUSTOMER_COLLECTION].update_one(
            {"_id": original_id_obj, "tenant_id": tenant_id},
            update_payload
        )
        if result.matched_count > 0:
            logging.info(f"Customer {customer_id} updated by {user} for tenant {tenant_id}")
            if result.modified_count > 0:
                 add_activity(
                    action_type="UPDATE_CUSTOMER",
                    user=user,
                    details=f"Updated Customer ID: {customer_id}. Changed fields: {list(update_data.keys())}",
                    document_id=original_id_obj,
                    collection_name=CUSTOMER_COLLECTION,
                    tenant_id=tenant_id
                )
        return result.matched_count
    except ValueError as ve:
        raise
    except Exception as e:
        logging.error(f"Error updating customer {customer_id} for tenant {tenant_id}: {e}")
        raise

def delete_customer_by_id(db_conn, customer_id, user="System", tenant_id="default_tenant_placeholder"):
    try:
        original_id_obj = ObjectId(customer_id)

        doc_to_delete = db_conn[CUSTOMER_COLLECTION].find_one({"_id": original_id_obj, "tenant_id": tenant_id})
        doc_name = doc_to_delete.get('displayName', str(original_id_obj)) if doc_to_delete else str(original_id_obj)

        result = db_conn[CUSTOMER_COLLECTION].delete_one({"_id": original_id_obj, "tenant_id": tenant_id})
        if result.deleted_count > 0:
            logging.info(f"Customer {customer_id} ('{doc_name}') deleted by {user} for tenant {tenant_id}.")
            add_activity(
                action_type="DELETE_CUSTOMER",
                user=user,
                details=f"Deleted Customer: '{doc_name}' (ID: {customer_id})",
                document_id=original_id_obj,
                collection_name=CUSTOMER_COLLECTION,
                tenant_id=tenant_id
            )
        return result.deleted_count
    except ValueError as ve:
        raise ve
    except Exception as e:
        logging.error(f"Error deleting customer {customer_id} for tenant {tenant_id}: {e}")
        raise
