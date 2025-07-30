# src/db/document_rules_dal.py
import logging
from datetime import datetime
from bson.objectid import ObjectId
from .activity_log_dal import add_activity # Import the activity log function

RULES_COLLECTION = 'document_rules'
GLOBAL_DOC_RULES_NAME = "global_document_rules"

logging.basicConfig(level=logging.INFO)

def get_or_create_rules(db_conn):
    """
    Fetches the global document rules. If it doesn't exist,
    it returns an empty structure without creating a new document.
    This version is hardened against null/invalid data within the rule arrays.
    """
    try:
        rules_doc = db_conn[RULES_COLLECTION].find_one({"name": GLOBAL_DOC_RULES_NAME})

        if not rules_doc:
            logging.warning("No global rules document found. Returning empty structure.")
            # Return an empty structure instead of creating one
            return {
                "name": GLOBAL_DOC_RULES_NAME,
                "business_rules": [],
                "other_rules": []
            }

        # Sanitize ObjectIds for the frontend
        rules_doc['_id'] = str(rules_doc.get('_id'))

        # Safely process and sanitize business_rules, filtering out invalid entries
        if 'business_rules' in rules_doc and rules_doc['business_rules']:
            sanitized_rules = []
            for rule in rules_doc['business_rules']:
                if isinstance(rule, dict) and rule.get('_id'):
                    rule['_id'] = str(rule.get('_id'))
                    sanitized_rules.append(rule)
            rules_doc['business_rules'] = sanitized_rules
        else:
            rules_doc['business_rules'] = [] # Ensure key exists and is a list

        # Safely process and sanitize other_rules, filtering out invalid entries
        if 'other_rules' in rules_doc and rules_doc['other_rules']:
            sanitized_rules = []
            for rule in rules_doc['other_rules']:
                if isinstance(rule, dict) and rule.get('_id'):
                    rule['_id'] = str(rule.get('_id'))
                    sanitized_rules.append(rule)
            rules_doc['other_rules'] = sanitized_rules
        else:
            rules_doc['other_rules'] = [] # Ensure key exists and is a list

        return rules_doc
    except Exception as e:
        logging.error(f"Error getting global rules: {e}")
        raise

def save_rules(db_conn, data, user="System"):
    """Saves the entire global rules document and logs the activity."""
    try:
        def sanitize_rule_ids(rules_list):
            """Converts frontend string IDs back to ObjectIds and creates new ones for new rules."""
            if not isinstance(rules_list, list): return []
            for rule in rules_list:
                if 'new_' in str(rule.get('_id')) or not rule.get('_id'):
                    rule['_id'] = ObjectId()
                else:
                    rule['_id'] = ObjectId(rule['_id'])
            return rules_list

        update_payload = {
            "$set": {
                "business_rules": sanitize_rule_ids(data.get('business_rules', [])),
                "other_rules": sanitize_rule_ids(data.get('other_rules', [])),
                "updated_date": datetime.utcnow(),
                "updated_user": user
            }
        }

        # The upsert=True will create the document if it's the very first time an admin saves.
        result = db_conn[RULES_COLLECTION].update_one(
            {"name": GLOBAL_DOC_RULES_NAME},
            update_payload,
            upsert=True
        )

        # Log the save activity if any change was made
        if result.modified_count > 0 or result.upserted_id is not None:
            add_activity("SAVE_DOCUMENT_RULES", user, "Updated the global document rules.", None, RULES_COLLECTION, "global")
            logging.info(f"Global document rules were updated by {user}.")

        return result.modified_count > 0 or result.upserted_id is not None
    except Exception as e:
        logging.error(f"Error saving global rules: {e}")
        raise
