# db/expense_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging
import re # For robust date parsing if needed

from .database import mongo

EXPENSE_COLLECTION = 'expenses'

def parse_date_string(date_string):
    """
    Parses a date string (DD/MM/YYYY or YYYY-MM-DD) into a datetime object.
    Returns None if parsing fails.
    """
    if not date_string or not isinstance(date_string, str):
        return None
    formats_to_try = ["%d/%m/%Y", "%Y-%m-%d"]
    for fmt in formats_to_try:
        try:
            return datetime.strptime(date_string, fmt)
        except ValueError:
            continue
    logging.warning(f"Could not parse date string: {date_string} with known formats.")
    return None

def create_expense(expense_data, user="System"):
    """
    Creates a new expense document in the database.
    """
    try:
        db = mongo.db
        now = datetime.utcnow()

        expense_data['created_date'] = now
        expense_data['updated_date'] = now
        expense_data['updated_user'] = user
        expense_data.pop('_id', None)

        # Convert date string from frontend to datetime object for storage
        if 'date' in expense_data and isinstance(expense_data['date'], str):
            parsed_date = parse_date_string(expense_data['date'])
            if parsed_date:
                expense_data['date'] = parsed_date
            else:
                # Handle invalid date - either raise error or store as is/None
                logging.warning(f"Invalid date format for expense: {expense_data['date']}. Storing as None.")
                expense_data['date'] = None # Or raise ValueError("Invalid date format")

        # Convert currency strings (total, tax) to numbers
        for field in ['total', 'tax']:
            if field in expense_data and isinstance(expense_data[field], str):
                try:
                    # Remove currency symbols and commas before parsing
                    value_str = re.sub(r'[$,]', '', expense_data[field])
                    expense_data[field] = float(value_str)
                except ValueError:
                    logging.warning(f"Could not convert {field} '{expense_data[field]}' to float. Storing as None.")
                    expense_data[field] = None # Or 0 or raise error

        result = db[EXPENSE_COLLECTION].insert_one(expense_data)
        logging.info(f"Expense created with ID: {result.inserted_id} by {user}")
        return result.inserted_id
    except Exception as e:
        logging.error(f"Error creating expense: {e}")
        raise

def get_expense_by_id(expense_id):
    """
    Fetches a single expense by its ObjectId.
    """
    try:
        db = mongo.db
        return db[EXPENSE_COLLECTION].find_one({"_id": ObjectId(expense_id)})
    except Exception as e:
        logging.error(f"Error fetching expense by ID {expense_id}: {e}")
        raise

def get_all_expenses(page=1, limit=25, filters=None, sort_by='date', sort_order=-1):
    """
    Fetches a paginated list of expenses, optionally filtered and sorted.
    sort_order: 1 for ascending, -1 for descending.
    """
    try:
        db = mongo.db
        query = filters if filters else {}
        skip = (page - 1) * limit if limit > 0 else 0

        # Basic date range filter example (can be expanded)
        if filters and filters.get('dateFrom') and filters.get('dateTo'):
            query['date'] = {
                "$gte": filters.pop('dateFrom'), # Expecting datetime objects
                "$lte": filters.pop('dateTo')   # Expecting datetime objects
            }
        elif filters and filters.get('dateFrom'):
             query['date'] = {"$gte": filters.pop('dateFrom')}
        elif filters and filters.get('dateTo'):
             query['date'] = {"$lte": filters.pop('dateTo')}


        if limit > 0:
            expenses_cursor = db[EXPENSE_COLLECTION].find(query).sort(sort_by, sort_order).skip(skip).limit(limit)
        else:
            expenses_cursor = db[EXPENSE_COLLECTION].find(query).sort(sort_by, sort_order).skip(skip)

        expense_list = list(expenses_cursor)
        total_items = db[EXPENSE_COLLECTION].count_documents(query)
        return expense_list, total_items
    except Exception as e:
        logging.error(f"Error fetching all expenses: {e}")
        raise

def update_expense(expense_id, update_data, user="System"):
    """
    Updates an existing expense document.
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

        # Convert date string from frontend to datetime object for storage
        if 'date' in update_payload_set and isinstance(update_payload_set['date'], str):
            parsed_date = parse_date_string(update_payload_set['date'])
            if parsed_date:
                update_payload_set['date'] = parsed_date
            else:
                logging.warning(f"Invalid date format for expense update: {update_payload_set['date']}. Keeping original or setting to None.")
                # Decide if you want to remove the field or keep the old value if parsing fails
                # For now, let's assume frontend sends valid or it's okay to store as is/None
                update_payload_set['date'] = None


        # Convert currency strings (total, tax) to numbers
        for field in ['total', 'tax']:
            if field in update_payload_set and isinstance(update_payload_set[field], str):
                try:
                    value_str = re.sub(r'[$,]', '', update_payload_set[field])
                    update_payload_set[field] = float(value_str)
                except ValueError:
                    logging.warning(f"Could not convert {field} '{update_payload_set[field]}' to float for update. Keeping as is or setting to None.")
                    # update_payload_set[field] = None # Or 0 or keep original

        result = db[EXPENSE_COLLECTION].update_one(
            {"_id": ObjectId(expense_id)},
            {"$set": update_payload_set}
        )
        if result.matched_count > 0:
            logging.info(f"Expense {expense_id} updated by {user}")
        return result.matched_count
    except Exception as e:
        logging.error(f"Error updating expense {expense_id}: {e}")
        raise

def delete_expense_by_id(expense_id):
    """
    Deletes an expense by its ObjectId.
    """
    try:
        db = mongo.db
        result = db[EXPENSE_COLLECTION].delete_one({"_id": ObjectId(expense_id)})
        if result.deleted_count > 0:
            logging.info(f"Expense {expense_id} deleted.")
        return result.deleted_count
    except Exception as e:
        logging.error(f"Error deleting expense {expense_id}: {e}")
        raise
