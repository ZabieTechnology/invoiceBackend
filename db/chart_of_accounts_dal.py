# db/chart_of_accounts_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging

from .database import mongo
from .activity_log_dal import add_activity # Assuming you want to log these activities

CHART_OF_ACCOUNTS_COLLECTION = 'chart_of_accounts'

def create_account(account_data, user="System", tenant_id="default_tenant"):
    """
    Creates a new account in the Chart of Accounts.
    The 'account_data' comes directly from the API layer after basic validation
    and pre-processing (like converting empty strings for IDs to None).
    """
    try:
        db = mongo.db
        now = datetime.utcnow()

        # Construct the payload to be inserted, ensuring correct types
        payload = {
            "accountType": account_data.get("accountType"),
            "code": account_data.get("code"),
            "name": account_data.get("name"),
            "description": account_data.get("description"),
            "defaultGstRateId": ObjectId(account_data["defaultGstRateId"]) if account_data.get("defaultGstRateId") else None,
            "isSubAccount": account_data.get("isSubAccount", False),
            "subAccountOf": ObjectId(account_data["subAccountOf"]) if account_data.get("isSubAccount") and account_data.get("subAccountOf") else None,
            "allowPayments": account_data.get("allowPayments", False),
            "openingBalance": None, # Initialize, will be set below if valid
            "balanceAsOf": None,    # Initialize, will be set below if valid
            "status": account_data.get("status", "Active"),

            # Metadata
            "created_date": now,
            "updated_date": now,
            "updated_user": user,
            "tenant_id": tenant_id
        }

        # Handle numeric and date fields carefully
        try:
            if account_data.get("openingBalance") not in [None, '']:
                payload["openingBalance"] = float(account_data.get("openingBalance"))
        except (ValueError, TypeError):
            logging.warning(f"Invalid openingBalance format: {account_data.get('openingBalance')} for account '{payload['name']}'. Setting to None.")
            # payload["openingBalance"] remains None

        if account_data.get("balanceAsOf") and account_data.get("balanceAsOf") != '':
            try:
                payload["balanceAsOf"] = datetime.strptime(account_data.get("balanceAsOf"), '%Y-%m-%d')
            except (ValueError, TypeError):
                logging.warning(f"Invalid balanceAsOf date format: {account_data.get('balanceAsOf')} for account '{payload['name']}'. Setting to None.")
                # payload["balanceAsOf"] remains None

        result = db[CHART_OF_ACCOUNTS_COLLECTION].insert_one(payload)
        inserted_id = result.inserted_id
        logging.info(f"Account '{payload.get('name')}' created with ID: {inserted_id} by {user} for tenant {tenant_id}")

        add_activity(
            action_type="CREATE_CHART_OF_ACCOUNT",
            user=user,
            details=f"Created Chart of Account: Name='{payload.get('name')}', Code='{payload.get('code')}'",
            document_id=inserted_id,
            collection_name=CHART_OF_ACCOUNTS_COLLECTION,
            tenant_id=tenant_id
        )
        return inserted_id
    except Exception as e:
        logging.error(f"Error creating account for tenant {tenant_id}: {e}")
        raise

def get_account_by_id(account_id, tenant_id="default_tenant"):
    try:
        db = mongo.db
        return db[CHART_OF_ACCOUNTS_COLLECTION].find_one({"_id": ObjectId(account_id), "tenant_id": tenant_id})
    except Exception as e:
        logging.error(f"Error fetching account by ID {account_id} for tenant {tenant_id}: {e}")
        raise

def get_all_accounts(page=1, limit=25, filters=None, tenant_id="default_tenant"):
    try:
        db = mongo.db
        query = filters if filters else {}
        query["tenant_id"] = tenant_id

        skip = (page - 1) * limit if limit > 0 else 0

        if limit > 0:
            accounts_cursor = db[CHART_OF_ACCOUNTS_COLLECTION].find(query).sort("name", 1).skip(skip).limit(limit)
        else:
            accounts_cursor = db[CHART_OF_ACCOUNTS_COLLECTION].find(query).sort("name", 1).skip(skip)

        account_list = list(accounts_cursor)
        total_items = db[CHART_OF_ACCOUNTS_COLLECTION].count_documents(query)
        return account_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all accounts for tenant {tenant_id}: {e}")
        raise

def update_account(account_id, update_data, user="System", tenant_id="default_tenant"):
    """
    Updates an existing account.
    'update_data' comes from the API layer after basic validation and pre-processing.
    """
    try:
        db = mongo.db
        now = datetime.utcnow()
        original_id_obj = ObjectId(account_id)

        payload_to_set = {}
        # Define fields that can be updated and their expected types or processing
        allowed_fields_map = {
            "accountType": str,
            "code": str,
            "name": str,
            "description": str,
            "defaultGstRateId": lambda x: ObjectId(x) if x else None,
            "isSubAccount": bool,
            "subAccountOf": lambda x: ObjectId(x) if update_data.get("isSubAccount") and x else None,
            "allowPayments": bool,
            "openingBalance": lambda x: float(x) if x not in [None, ''] else None,
            "balanceAsOf": lambda x: datetime.strptime(x, '%Y-%m-%d') if x and x != '' else None,
            "status": str
        }

        for field, processor in allowed_fields_map.items():
            if field in update_data:
                try:
                    # For booleans from form, they might come as strings "true"/"false" or actual booleans.
                    # The API layer should ideally send correct types, but we can be robust.
                    if processor == bool:
                        payload_to_set[field] = str(update_data[field]).lower() == 'true' if isinstance(update_data[field], str) else bool(update_data[field])
                    else:
                        payload_to_set[field] = processor(update_data[field])
                except (ValueError, TypeError) as e:
                    logging.warning(f"Invalid format for field '{field}' with value '{update_data[field]}' during update of account {account_id}. Skipping field or setting to None.")
                    if field in ["openingBalance", "balanceAsOf", "defaultGstRateId", "subAccountOf"]:
                        payload_to_set[field] = None # Set to None if conversion fails for these optional fields
                    # For other fields, you might choose to skip or raise an error

        # If isSubAccount is explicitly set to false, ensure subAccountOf is cleared
        if "isSubAccount" in update_data and not payload_to_set.get("isSubAccount"):
            payload_to_set["subAccountOf"] = None

        if not payload_to_set:
            logging.info(f"No valid fields provided for updating account {account_id}")
            return 0 # No effective update

        payload_to_set["updated_date"] = now
        payload_to_set["updated_user"] = user

        result = db[CHART_OF_ACCOUNTS_COLLECTION].update_one(
            {"_id": original_id_obj, "tenant_id": tenant_id},
            {"$set": payload_to_set}
        )

        if result.matched_count > 0:
            logging.info(f"Account {account_id} updated by {user} for tenant {tenant_id}")
            # Check if any actual modification happened, not just updated_date/user
            if result.modified_count > 0 or (len(payload_to_set) > 2): # >2 because updated_date and updated_user are always set
                add_activity(
                    action_type="UPDATE_CHART_OF_ACCOUNT",
                    user=user,
                    details=f"Updated Chart of Account ID: {account_id}. Changed fields: {list(payload_to_set.keys())}",
                    document_id=original_id_obj,
                    collection_name=CHART_OF_ACCOUNTS_COLLECTION,
                    tenant_id=tenant_id
                )
        return result.matched_count
    except Exception as e:
        logging.error(f"Error updating account {account_id} for tenant {tenant_id}: {e}")
        raise

def delete_account_by_id(account_id, user="System", tenant_id="default_tenant"):
    try:
        db = mongo.db
        original_id_obj = ObjectId(account_id)

        doc_to_delete = db[CHART_OF_ACCOUNTS_COLLECTION].find_one({"_id": original_id_obj, "tenant_id": tenant_id})
        doc_name = doc_to_delete.get('name', str(original_id_obj)) if doc_to_delete else str(original_id_obj)

        children_count = db[CHART_OF_ACCOUNTS_COLLECTION].count_documents({"subAccountOf": original_id_obj, "tenant_id": tenant_id})
        if children_count > 0:
            raise ValueError(f"Cannot delete account '{doc_name}' as it is a parent to other sub-accounts. Please reassign sub-accounts first.")

        result = db[CHART_OF_ACCOUNTS_COLLECTION].delete_one({"_id": original_id_obj, "tenant_id": tenant_id})
        if result.deleted_count > 0:
            logging.info(f"Account {account_id} ('{doc_name}') deleted by {user} for tenant {tenant_id}.")
            add_activity(
                action_type="DELETE_CHART_OF_ACCOUNT",
                user=user,
                details=f"Deleted Chart of Account: '{doc_name}' (ID: {account_id})",
                document_id=original_id_obj,
                collection_name=CHART_OF_ACCOUNTS_COLLECTION,
                tenant_id=tenant_id
            )
        return result.deleted_count
    except ValueError as ve:
        raise ve
    except Exception as e:
        logging.error(f"Error deleting account {account_id} for tenant {tenant_id}: {e}")
        raise
