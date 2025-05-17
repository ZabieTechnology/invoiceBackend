# db/contact_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging

# Import the mongo instance and the company info DAL to get the company ID
from .database import mongo
from .company_information_dal import get_company_information # To link contacts to company

CONTACTS_COLLECTION = 'contacts' # New collection name

# Helper function to get the current company ID (assumes single company doc)
def _get_current_company_id():
    """Fetches the _id of the single company information document."""
    company_info = get_company_information()
    if company_info and '_id' in company_info:
        return company_info['_id']
    else:
        # Handle case where company info doesn't exist yet.
        # Should ideally be created before contacts are added.
        logging.warning("Company information document not found. Cannot associate contacts.")
        return None

def get_contacts_by_company():
    """
    Fetches all contacts associated with the current company.
    """
    try:
        db = mongo.db
        company_id = _get_current_company_id()
        if not company_id:
            return [] # Return empty list if no company found

        contacts_cursor = db[CONTACTS_COLLECTION].find({"company_id": company_id})
        return list(contacts_cursor)
    except Exception as e:
        logging.error(f"Error fetching contacts by company: {e}")
        raise

def replace_all_contacts(contacts_list, user="System"):
    """
    Replaces all contacts for the current company with the provided list.
    Deletes existing contacts for the company and inserts the new ones.

    Args:
        contacts_list (list): A list of contact dictionaries to save.
        user (str): The user performing the action.

    Returns:
        bool: True if the operation was successful, False otherwise.
    """
    try:
        db = mongo.db
        company_id = _get_current_company_id()
        if not company_id:
            logging.error("Cannot replace contacts: Company ID not found.")
            return False # Cannot proceed without a company to link to

        now = datetime.utcnow()

        # Add company_id and metadata to each contact in the new list
        processed_contacts = []
        for contact in contacts_list:
            # Remove any client-sent _id to ensure new ones are generated if needed
            contact.pop('_id', None)
            contact['company_id'] = company_id
            contact['created_date'] = now # Treat replacement as new creation for simplicity
            contact['updated_date'] = now
            contact['updated_user'] = user
            processed_contacts.append(contact)

        # --- Perform deletion and insertion within a transaction for atomicity ---
        # Note: Transactions require a replica set or specific MongoDB setup.
        # If transactions are not available, perform delete then insert,
        # acknowledging it's not truly atomic.

        with mongo.cx.start_session() as session:
             with session.with_transaction():
                # 1. Delete all existing contacts for this company
                delete_result = db[CONTACTS_COLLECTION].delete_many(
                    {"company_id": company_id},
                    session=session
                )
                logging.info(f"Deleted {delete_result.deleted_count} existing contacts for company {company_id}.")

                # 2. Insert the new list of contacts if it's not empty
                if processed_contacts:
                    insert_result = db[CONTACTS_COLLECTION].insert_many(
                        processed_contacts,
                        session=session
                    )
                    logging.info(f"Inserted {len(insert_result.inserted_ids)} new contacts for company {company_id}.")
                    # Check if insertion was successful
                    if len(insert_result.inserted_ids) != len(processed_contacts):
                         logging.error("Mismatch in inserted contacts count during transaction.")
                         # Transaction will automatically abort on unhandled exception
                         raise Exception("Failed to insert all contacts during replacement.")

                # If we reach here, the transaction was successful
                # Update the main company document's timestamp
                db.company_information.update_one(
                     {"_id": company_id},
                     {"$set": {"updated_date": now, "updated_user": user}},
                     session=session
                )

        logging.info(f"Successfully replaced contacts for company {company_id} by user {user}.")
        return True

    except Exception as e:
        # Catch potential transaction errors or other exceptions
        logging.error(f"Error replacing contacts: {e}")
        # Don't raise here, return False to indicate failure to the API layer
        return False


# --- Optional: Functions for individual CRUD if needed later ---

# def add_contact(contact_data, user="System"): ...
# def update_contact(contact_id, contact_data, user="System"): ...
# def delete_contact(contact_id): ...

