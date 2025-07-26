# db/chart_of_accounts_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging
import re

from .activity_log_dal import add_activity

CHART_OF_ACCOUNTS_COLLECTION = 'chart_of_accounts'

def create_account(db_conn, account_data, user="System", tenant_id="default_tenant"):
    """
    Creates a new account using the new classification structure.
    'db_conn' is the database connection instance.
    """
    try:
        now = datetime.utcnow()

        payload = {
            "nature": account_data.get("nature"),
            "mainHead": account_data.get("mainHead"),
            "category": account_data.get("category"),
            "enabledOptions": account_data.get("enabledOptions", {}),
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
            "isLocked": account_data.get("isLocked", False),
            "bankName": account_data.get("bankName"),
            "accountNumber": account_data.get("accountNumber"),
            "ifscCode": account_data.get("ifscCode"),
            "swiftCode": account_data.get("swiftCode"),
            "currency": account_data.get("currency"),
            "created_date": now,
            "updated_date": now,
            "updated_user": user,
            "tenant_id": tenant_id
        }

        try:
            if account_data.get("openingBalance") not in [None, '']:
                payload["openingBalance"] = float(account_data.get("openingBalance"))
        except (ValueError, TypeError):
            logging.warning(f"Invalid openingBalance format: {account_data.get('openingBalance')}. Setting to None.")

        if account_data.get("balanceAsOf") and account_data.get("balanceAsOf") != '':
            try:
                payload["balanceAsOf"] = datetime.strptime(account_data.get("balanceAsOf"), '%Y-%m-%d')
            except (ValueError, TypeError):
                logging.warning(f"Invalid balanceAsOf date format: {account_data.get('balanceAsOf')}. Setting to None.")

        result = db_conn[CHART_OF_ACCOUNTS_COLLECTION].insert_one(payload)
        inserted_id = result.inserted_id
        logging.info(f"Account '{payload.get('name')}' created with ID: {inserted_id}")

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
        logging.error(f"Error creating account: {e}")
        raise

def get_account_by_id(db_conn, account_id, tenant_id="default_tenant"):
    """
    Fetches a single account by its ID.
    """
    try:
        return db_conn[CHART_OF_ACCOUNTS_COLLECTION].find_one({"_id": ObjectId(account_id), "tenant_id": tenant_id})
    except Exception as e:
        logging.error(f"Error fetching account by ID {account_id}: {e}")
        raise

def get_all_accounts(db_conn, page=1, limit=25, filters=None, tenant_id="default_tenant"):
    """
    Fetches all accounts with pagination and filtering.
    """
    try:
        query = filters if filters else {}
        query["tenant_id"] = tenant_id

        skip = (page - 1) * limit if limit > 0 else 0

        if limit > 0:
            accounts_cursor = db_conn[CHART_OF_ACCOUNTS_COLLECTION].find(query).sort("name", 1).skip(skip).limit(limit)
        else:
            accounts_cursor = db_conn[CHART_OF_ACCOUNTS_COLLECTION].find(query).sort("name", 1)

        account_list = list(accounts_cursor)
        total_items = db_conn[CHART_OF_ACCOUNTS_COLLECTION].count_documents(query)

        return account_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all accounts with filters {filters}: {e}")
        raise

def update_account(db_conn, account_id, update_data, user="System", tenant_id="default_tenant"):
    """
    Updates an existing account.
    """
    try:
        now = datetime.utcnow()
        original_id_obj = ObjectId(account_id)

        payload_to_set = {}
        allowed_fields_map = {
            "nature": str, "mainHead": str, "category": str, "enabledOptions": dict,
            "code": str, "name": str, "description": str,
            "defaultGstRateId": lambda x: ObjectId(x) if x else None,
            "isSubAccount": bool,
            "subAccountOf": lambda x: ObjectId(x) if update_data.get("isSubAccount") and x else None,
            "allowPayments": bool,
            "openingBalance": lambda x: float(x) if x not in [None, ''] else None,
            "balanceAsOf": lambda x: datetime.strptime(x, '%Y-%m-%d') if x and x != '' else None,
            "status": str, "isLocked": bool,
            "bankName": str, "accountNumber": str, "ifscCode": str, "swiftCode": str, "currency": str
        }

        for field, processor in allowed_fields_map.items():
            if field in update_data:
                try:
                    payload_to_set[field] = processor(update_data[field])
                except (ValueError, TypeError, AttributeError) as e:
                    logging.warning(f"Invalid format for field '{field}' during update. Setting to None or default. Error: {e}")
                    if field in ["openingBalance", "balanceAsOf", "defaultGstRateId", "subAccountOf"]:
                        payload_to_set[field] = None

        if "isSubAccount" in update_data and not payload_to_set.get("isSubAccount"):
            payload_to_set["subAccountOf"] = None

        if not payload_to_set:
            return 0

        payload_to_set["updated_date"] = now
        payload_to_set["updated_user"] = user

        result = db_conn[CHART_OF_ACCOUNTS_COLLECTION].update_one(
            {"_id": original_id_obj, "tenant_id": tenant_id},
            {"$set": payload_to_set}
        )

        if result.matched_count > 0 and result.modified_count > 0:
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
        logging.error(f"Error updating account {account_id}: {e}")
        raise

def delete_account_by_id(db_conn, account_id, user="System", tenant_id="default_tenant"):
    """
    Deletes an account, ensuring it is not a parent to sub-accounts.
    """
    try:
        original_id_obj = ObjectId(account_id)
        doc_to_delete = db_conn[CHART_OF_ACCOUNTS_COLLECTION].find_one({"_id": original_id_obj, "tenant_id": tenant_id})
        doc_name = doc_to_delete.get('name', str(original_id_obj)) if doc_to_delete else str(original_id_obj)

        children_count = db_conn[CHART_OF_ACCOUNTS_COLLECTION].count_documents({"subAccountOf": original_id_obj, "tenant_id": tenant_id})
        if children_count > 0:
            raise ValueError(f"Cannot delete account '{doc_name}' as it is a parent to other sub-accounts.")

        result = db_conn[CHART_OF_ACCOUNTS_COLLECTION].delete_one({"_id": original_id_obj, "tenant_id": tenant_id})
        if result.deleted_count > 0:
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
        logging.error(f"Error deleting account {account_id}: {e}")
        raise
