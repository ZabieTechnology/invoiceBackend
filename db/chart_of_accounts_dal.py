# db/chart_of_accounts_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging

from .database import mongo

CHART_OF_ACCOUNTS_COLLECTION = 'chart_of_accounts'

def create_account(account_data, user="System"):
    """
    Creates a new account in the Chart of Accounts.
    """
    try:
        db = mongo.db
        now = datetime.utcnow()
        account_data['created_date'] = now
        account_data['updated_date'] = now
        account_data['updated_user'] = user
        account_data.pop('_id', None) # Ensure no _id for new creation

        # Ensure boolean fields are correctly stored
        boolean_fields = ['isSubAccount', 'reconcile', 'dashboardWatch', 'isFavorite']
        for field in boolean_fields:
            account_data[field] = account_data.get(field, False)

        # Ensure numeric fields are correctly stored or defaulted
        numeric_fields = ['openingBalance']
        for field in numeric_fields:
            account_data[field] = account_data.get(field) # Allow None, or default to 0 if needed
            if isinstance(account_data[field], str) and account_data[field].strip() == '':
                account_data[field] = None # Store empty string as None for numbers
            elif account_data[field] is not None:
                try:
                    account_data[field] = float(account_data[field])
                except ValueError:
                    logging.warning(f"Could not convert {field} value '{account_data[field]}' to float. Setting to None.")
                    account_data[field] = None


        # Convert date string to datetime object if present
        if account_data.get('balanceAsOf'):
            try:
                # Assuming date is sent in YYYY-MM-DD format from frontend
                account_data['balanceAsOf'] = datetime.strptime(account_data['balanceAsOf'], '%Y-%m-%d')
            except (ValueError, TypeError):
                logging.warning(f"Invalid date format for balanceAsOf: {account_data.get('balanceAsOf')}. Setting to None.")
                account_data['balanceAsOf'] = None


        result = db[CHART_OF_ACCOUNTS_COLLECTION].insert_one(account_data)
        logging.info(f"Account '{account_data.get('name')}' created with ID: {result.inserted_id} by {user}")
        return result.inserted_id
    except Exception as e:
        logging.error(f"Error creating account: {e}")
        raise

def get_account_by_id(account_id):
    """
    Fetches a single account by its ObjectId.
    """
    try:
        db = mongo.db
        return db[CHART_OF_ACCOUNTS_COLLECTION].find_one({"_id": ObjectId(account_id)})
    except Exception as e:
        logging.error(f"Error fetching account by ID {account_id}: {e}")
        raise

def get_all_accounts(page=1, limit=25, filters=None):
    """
    Fetches a paginated list of accounts, optionally filtered.
    """
    try:
        db = mongo.db
        query = filters if filters else {}
        skip = (page - 1) * limit if limit > 0 else 0 # Handle limit=0 or -1 for all items

        if limit > 0:
            accounts_cursor = db[CHART_OF_ACCOUNTS_COLLECTION].find(query).skip(skip).limit(limit)
        else: # Fetch all if limit is not positive
            accounts_cursor = db[CHART_OF_ACCOUNTS_COLLECTION].find(query).skip(skip)

        account_list = list(accounts_cursor)
        total_items = db[CHART_OF_ACCOUNTS_COLLECTION].count_documents(query)
        return account_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all accounts: {e}")
        raise

def update_account(account_id, update_data, user="System"):
    """
    Updates an existing account.
    """
    try:
        db = mongo.db
        now = datetime.utcnow()
        update_data.pop('_id', None)
        
        update_payload_set = {
            **update_data,
            "updated_date": now,
            "updated_user": user
        }

        # Ensure boolean fields are correctly stored
        boolean_fields = ['isSubAccount', 'reconcile', 'dashboardWatch', 'isFavorite']
        for field in boolean_fields:
            if field in update_payload_set:
                 update_payload_set[field] = update_payload_set.get(field, False)

        # Ensure numeric fields are correctly stored or defaulted
        numeric_fields = ['openingBalance']
        for field in numeric_fields:
            if field in update_payload_set:
                current_val = update_payload_set[field]
                if isinstance(current_val, str) and current_val.strip() == '':
                    update_payload_set[field] = None
                elif current_val is not None:
                    try:
                        update_payload_set[field] = float(current_val)
                    except ValueError:
                        logging.warning(f"Could not convert {field} value '{current_val}' to float for update. Keeping as is or setting to None.")
                        # Decide how to handle: keep original, set to None, or raise error
                        # For now, let's assume frontend sends valid data or it's handled there
                        # If it's critical, you might want to fetch the old value or reject the update.
                        update_payload_set[field] = None


        # Convert date string to datetime object if present
        if update_payload_set.get('balanceAsOf'):
            try:
                update_payload_set['balanceAsOf'] = datetime.strptime(update_payload_set['balanceAsOf'], '%Y-%m-%d')
            except (ValueError, TypeError):
                logging.warning(f"Invalid date format for balanceAsOf during update: {update_payload_set.get('balanceAsOf')}. Setting to None.")
                update_payload_set['balanceAsOf'] = None
        
        result = db[CHART_OF_ACCOUNTS_COLLECTION].update_one(
            {"_id": ObjectId(account_id)},
            {"$set": update_payload_set}
        )
        if result.matched_count > 0:
            logging.info(f"Account {account_id} updated by {user}")
        return result.matched_count
    except Exception as e:
        logging.error(f"Error updating account {account_id}: {e}")
        raise

def delete_account_by_id(account_id):
    """
    Deletes an account by its ObjectId.
    """
    try:
        db = mongo.db
        # TODO: Add logic to check if this account is a parent to others before deleting,
        # or handle re-parenting of child accounts.
        result = db[CHART_OF_ACCOUNTS_COLLECTION].delete_one({"_id": ObjectId(account_id)})
        if result.deleted_count > 0:
            logging.info(f"Account {account_id} deleted.")
        return result.deleted_count
    except Exception as e:
        logging.error(f"Error deleting account {account_id}: {e}")
        raise
