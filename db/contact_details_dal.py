# db/contact_details_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging

# This collection name should match your database
CONTACTS_COLLECTION = 'contact_details'

logging.basicConfig(level=logging.INFO)

def get_all_contacts(db_conn, tenant_id):
    """Fetches all contacts for a specific tenant."""
    try:
        return list(db_conn[CONTACTS_COLLECTION].find({"tenant_id": tenant_id}))
    except Exception as e:
        logging.error(f"Error fetching contacts for tenant {tenant_id}: {e}")
        raise

def add_contact(db_conn, tenant_id, data):
    """Adds a new contact for a specific tenant."""
    try:
        data['tenant_id'] = tenant_id
        data['created_date'] = datetime.utcnow()
        data['updated_date'] = datetime.utcnow()

        # If this new contact is the default, unset the default status for all others.
        if data.get('isDefault'):
            db_conn[CONTACTS_COLLECTION].update_many(
                {"tenant_id": tenant_id},
                {"$set": {"isDefault": False}}
            )

        result = db_conn[CONTACTS_COLLECTION].insert_one(data)
        return str(result.inserted_id)
    except Exception as e:
        logging.error(f"Error adding contact for tenant {tenant_id}: {e}")
        raise

def update_contact(db_conn, tenant_id, contact_id, data):
    """Updates an existing contact."""
    try:
        data['updated_date'] = datetime.utcnow()

        # If this contact is being set as default, handle unsetting others.
        if data.get('isDefault'):
            db_conn[CONTACTS_COLLECTION].update_many(
                {"tenant_id": tenant_id, "_id": {"$ne": ObjectId(contact_id)}},
                {"$set": {"isDefault": False}}
            )

        result = db_conn[CONTACTS_COLLECTION].update_one(
            {"_id": ObjectId(contact_id), "tenant_id": tenant_id},
            {"$set": data}
        )
        return result.modified_count > 0
    except Exception as e:
        logging.error(f"Error updating contact {contact_id} for tenant {tenant_id}: {e}")
        raise

def delete_contact(db_conn, tenant_id, contact_id):
    """Deletes a contact."""
    try:
        # Prevent deletion of the default contact
        contact_to_delete = db_conn[CONTACTS_COLLECTION].find_one({"_id": ObjectId(contact_id)})
        if contact_to_delete and contact_to_delete.get('isDefault'):
            raise ValueError("Cannot delete the default contact.")

        result = db_conn[CONTACTS_COLLECTION].delete_one(
            {"_id": ObjectId(contact_id), "tenant_id": tenant_id}
        )
        return result.deleted_count > 0
    except Exception as e:
        logging.error(f"Error deleting contact {contact_id} for tenant {tenant_id}: {e}")
        raise

def set_default_contact(db_conn, tenant_id, contact_id):
    """Sets a contact as the default, unsetting all others."""
    try:
        # Unset the current default
        db_conn[CONTACTS_COLLECTION].update_many(
            {"tenant_id": tenant_id},
            {"$set": {"isDefault": False}}
        )
        # Set the new default
        result = db_conn[CONTACTS_COLLECTION].update_one(
            {"_id": ObjectId(contact_id), "tenant_id": tenant_id},
            {"$set": {"isDefault": True}}
        )
        return result.modified_count > 0
    except Exception as e:
        logging.error(f"Error setting default contact for tenant {tenant_id}: {e}")
        raise