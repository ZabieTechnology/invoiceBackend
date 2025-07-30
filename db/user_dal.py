# db/user_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging
import random
import uuid  # Import the UUID module
from werkzeug.security import generate_password_hash, check_password_hash

from .database import mongo

USER_COLLECTION = 'users'

# --- THIS IS THE UPDATED TENANT ID FUNCTION ---
def generate_tenant_id(company_name):
    """
    Generates a tenant ID using a UUIDv4, embedding the first four
    letters of the company name into the ID for easy identification.

    Format: xxxxxxxx-NAME-xxxx-xxxx-xxxxxxxxxxxx
    """
    if not company_name:
        return None

    # Take the first 4 letters, convert to uppercase, and pad if less than 4 chars
    name_prefix = company_name[:4].upper().ljust(4, 'X')

    # Generate a new UUID
    generated_uuid = str(uuid.uuid4())

    # Split the UUID into its parts
    parts = generated_uuid.split('-')

    # Replace the second part of the UUID with the company name prefix
    parts[1] = name_prefix

    # Join the parts back together to form the new tenant ID
    tenant_id = '-'.join(parts)

    return tenant_id

def create_user(username, password, email=None, company_legal_name=None, user_data=None):
    """
    Creates a new user document with a hashed password and a tenant ID.
    """
    try:
        user_data = user_data or {}
        # Handle potential camelCase key from frontend JSON if not passed directly
        if not company_legal_name:
            company_legal_name = user_data.get('companyLegalName')

        # Enforce that company_legal_name is provided.
        if not company_legal_name:
            logging.error("Attempt to create user without a company legal name.")
            raise ValueError("Company legal name is required to create a user.")

        db = mongo.db
        if db[USER_COLLECTION].find_one({"username": username}):
            logging.warning(f"Attempt to create user with existing username: {username}")
            return None # Username already exists

        now = datetime.utcnow()
        hashed_password = generate_password_hash(password)

        tenant_id = generate_tenant_id(company_legal_name)

        # Ensure a tenant_id was successfully generated.
        if not tenant_id:
            logging.error(f"Failed to generate tenant_id for company: {company_legal_name}")
            raise ValueError("Could not generate a tenant ID from the provided company name.")

        new_user = {
            "username": username,
            "password_hash": hashed_password,
            "email": email,
            "company_legal_name": company_legal_name,
            "tenant_id": tenant_id,
            "created_date": now,
            "updated_date": now,
            "is_active": True,
            **user_data
        }

        result = db[USER_COLLECTION].insert_one(new_user)
        logging.info(f"User '{username}' created with ID: {result.inserted_id} and Tenant ID: {tenant_id}")
        return result.inserted_id
    except Exception as e:
        logging.error(f"Error creating user '{username}': {e}")
        raise

def get_user_by_username(username):
    """
    Fetches a user by their username.
    """
    try:
        db = mongo.db
        return db[USER_COLLECTION].find_one({"username": username})
    except Exception as e:
        logging.error(f"Error fetching user by username '{username}': {e}")
        raise

def verify_password(password_hash, password):
    """
    Verifies a password against a stored hash.
    """
    return check_password_hash(password_hash, password)

def get_user_by_id(user_id):
    """
    Fetches a user by their ObjectId.
    """
    try:
        db = mongo.db
        return db[USER_COLLECTION].find_one({"_id": ObjectId(user_id)})
    except Exception as e:
        logging.error(f"Error fetching user by ID {user_id}: {e}")
        raise

def get_test_users(limit=5):
    """
    Fetches a specified number of users (username and email only) for testing.
    """
    try:
        db = mongo.db
        # Fetch specified fields, limit the results, and sort by creation date (optional)
        users_cursor = db[USER_COLLECTION].find(
            {}, # Empty filter to get all users
            {"username": 1, "email": 1, "_id": 0} # Projection: 1 to include, 0 to exclude
        ).sort("created_date", 1).limit(limit) # Sort by oldest first, limit to N users
        return list(users_cursor)
    except Exception as e:
        logging.error(f"Error fetching test users: {e}")
        raise
