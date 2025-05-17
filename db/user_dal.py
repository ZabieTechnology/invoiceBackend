# db/user_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging
from werkzeug.security import generate_password_hash, check_password_hash

from .database import mongo

USER_COLLECTION = 'users'

def create_user(username, password, email=None, user_data=None):
    """
    Creates a new user document with a hashed password.
    """
    try:
        db = mongo.db
        if db[USER_COLLECTION].find_one({"username": username}):
            logging.warning(f"Attempt to create user with existing username: {username}")
            return None # Username already exists

        now = datetime.utcnow()
        hashed_password = generate_password_hash(password)
        
        new_user = {
            "username": username,
            "password_hash": hashed_password,
            "email": email,
            "created_date": now,
            "updated_date": now,
            "is_active": True, # Default to active
            **(user_data if user_data else {}) # Additional user data
        }
        
        result = db[USER_COLLECTION].insert_one(new_user)
        logging.info(f"User '{username}' created with ID: {result.inserted_id}")
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
