# db/chart_of_accounts_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging
import re # Ensure re is imported for regex usage if any (though not explicitly used for accountType in this version)

# Removed: from .database import mongo (db connection will be passed as an argument)
from .activity_log_dal import add_activity # Assuming you want to log these activities

CHART_OF_ACCOUNTS_COLLECTION = 'chart_of_accounts'

def create_account(db_conn, account_data, user="System", tenant_id="default_tenant"):
    """
    Creates a new account in the Chart of Accounts.
    'db_conn' is the database connection instance.
    'account_data' comes directly from the API layer after basic validation
    and pre-processing (like converting empty strings for IDs to None).
    """
    try:
        # db = mongo.db # Changed: Use passed db_conn
        now = datetime.utcnow()

        payload = {
            "accountType": account_data.get("accountType"),
            "code": account_data.get("code"),
            "name": account_data.get("name"),
            "description": account_data.get("description"),
            "defaultGstRateId": ObjectId(account_data["defaultGstRateId"]) if account_data.get("defaultGstRateId") else None,
            "isSubAccount": account_data.get("isSubAccount", False),
            "subAccountOf": ObjectId(account_data["subAccountOf"]) if account_data.get("isSubAccount") and account_data.get("subAccountOf") else None,
            "allowPayments": account_data.get("allowPayments", False),
            "openingBalance": None,
            "balanceAsOf": None,
            "status": account_data.get("status", "Active"),
            "created_date": now,
            "updated_date": now,
            "updated_user": user,
            "tenant_id": tenant_id
        }

        try:
            if account_data.get("openingBalance") not in [None, '']:
                payload["openingBalance"] = float(account_data.get("openingBalance"))
        except (ValueError, TypeError):
            logging.warning(f"Invalid openingBalance format: {account_data.get('openingBalance')} for account '{payload['name']}'. Setting to None.")

        if account_data.get("balanceAsOf") and account_data.get("balanceAsOf") != '':
            try:
                payload["balanceAsOf"] = datetime.strptime(account_data.get("balanceAsOf"), '%Y-%m-%d')
            except (ValueError, TypeError):
                logging.warning(f"Invalid balanceAsOf date format: {account_data.get('balanceAsOf')} for account '{payload['name']}'. Setting to None.")

        result = db_conn[CHART_OF_ACCOUNTS_COLLECTION].insert_one(payload)
        inserted_id = result.inserted_id
        logging.info(f"Account '{payload.get('name')}' created with ID: {inserted_id} by {user} for tenant {tenant_id}")

        add_activity(
            db_conn, # Pass db_conn to activity log DAL if it requires it
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

def get_account_by_id(db_conn, account_id, tenant_id="default_tenant"):
    """
    'db_conn' is the database connection instance.
    """
    try:
        # db = mongo.db # Changed: Use passed db_conn
        return db_conn[CHART_OF_ACCOUNTS_COLLECTION].find_one({"_id": ObjectId(account_id), "tenant_id": tenant_id})
    except Exception as e:
        logging.error(f"Error fetching account by ID {account_id} for tenant {tenant_id}: {e}")
        raise

def get_all_accounts(db_conn, page=1, limit=25, filters=None, tenant_id="default_tenant"):
    """
    'db_conn' is the database connection instance.
    'filters' dictionary can contain 'accountType' for filtering.
    """
    try:
        # db = mongo.db # Changed: Use passed db_conn
        query = filters if filters else {}
        query["tenant_id"] = tenant_id # Always filter by tenant_id

        # If accountType filter is present, it will be used directly by the query
        # e.g., if filters = {"accountType": "Bank Accounts"}
        # then query will be {"accountType": "Bank Accounts", "tenant_id": "..."}

        skip = (page - 1) * limit if limit > 0 else 0

        if limit > 0:
            accounts_cursor = db_conn[CHART_OF_ACCOUNTS_COLLECTION].find(query).sort("name", 1).skip(skip).limit(limit)
        else: # limit = -1 means fetch all matching documents
            accounts_cursor = db_conn[CHART_OF_ACCOUNTS_COLLECTION].find(query).sort("name", 1).skip(skip)

        account_list = list(accounts_cursor)
        total_items = db_conn[CHART_OF_ACCOUNTS_COLLECTION].count_documents(query)

        # logging.info(f"DAL: Fetching accounts with query: {query}, Found: {total_items}") # For debugging

        return account_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all accounts for tenant {tenant_id} with filters {filters}: {e}")
        raise

def update_account(db_conn, account_id, update_data, user="System", tenant_id="default_tenant"):
    """
    'db_conn' is the database connection instance.
    """
    try:
        # db = mongo.db # Changed: Use passed db_conn
        now = datetime.utcnow()
        original_id_obj = ObjectId(account_id)

        payload_to_set = {}
        allowed_fields_map = {
            "accountType": str, "code": str, "name": str, "description": str,
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
                    if processor == bool:
                        payload_to_set[field] = str(update_data[field]).lower() == 'true' if isinstance(update_data[field], str) else bool(update_data[field])
                    else:
                        payload_to_set[field] = processor(update_data[field])
                except (ValueError, TypeError) as e:
                    logging.warning(f"Invalid format for field '{field}' with value '{update_data[field]}' during update of account {account_id}. Skipping field or setting to None.")
                    if field in ["openingBalance", "balanceAsOf", "defaultGstRateId", "subAccountOf"]:
                        payload_to_set[field] = None

        if "isSubAccount" in update_data and not payload_to_set.get("isSubAccount"):
            payload_to_set["subAccountOf"] = None

        if not payload_to_set:
            logging.info(f"No valid fields provided for updating account {account_id}")
            return 0

        payload_to_set["updated_date"] = now
        payload_to_set["updated_user"] = user

        result = db_conn[CHART_OF_ACCOUNTS_COLLECTION].update_one(
            {"_id": original_id_obj, "tenant_id": tenant_id},
            {"$set": payload_to_set}
        )

        if result.matched_count > 0:
            logging.info(f"Account {account_id} updated by {user} for tenant {tenant_id}")
            if result.modified_count > 0 or (len(payload_to_set) > 2):
                add_activity(
                    db_conn, # Pass db_conn
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

def delete_account_by_id(db_conn, account_id, user="System", tenant_id="default_tenant"):
    """
    'db_conn' is the database connection instance.
    """
    try:
        # db = mongo.db # Changed: Use passed db_conn
        original_id_obj = ObjectId(account_id)

        doc_to_delete = db_conn[CHART_OF_ACCOUNTS_COLLECTION].find_one({"_id": original_id_obj, "tenant_id": tenant_id})
        doc_name = doc_to_delete.get('name', str(original_id_obj)) if doc_to_delete else str(original_id_obj)

        children_count = db_conn[CHART_OF_ACCOUNTS_COLLECTION].count_documents({"subAccountOf": original_id_obj, "tenant_id": tenant_id})
        if children_count > 0:
            raise ValueError(f"Cannot delete account '{doc_name}' as it is a parent to other sub-accounts. Please reassign sub-accounts first.")

        result = db_conn[CHART_OF_ACCOUNTS_COLLECTION].delete_one({"_id": original_id_obj, "tenant_id": tenant_id})
        if result.deleted_count > 0:
            logging.info(f"Account {account_id} ('{doc_name}') deleted by {user} for tenant {tenant_id}.")
            add_activity(
                db_conn, # Pass db_conn
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
