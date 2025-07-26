# db/account_classification_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging
from .activity_log_dal import add_activity

CLASSIFICATION_COLLECTION = 'account_classifications'

logging.basicConfig(level=logging.INFO)

def get_classifications(db_conn, tenant_id="default_tenant"):
    """Fetches and transforms all account classifications for a tenant into a flat list."""
    try:
        # This pipeline flattens the nested structure into a list of paths,
        # which is the format the frontend expects to do its own grouping.
        pipeline = [
            {"$match": {"tenant_id": tenant_id}},
            {"$unwind": { "path": "$mainHeads", "preserveNullAndEmptyArrays": True }},
            {"$unwind": { "path": "$mainHeads.categories", "preserveNullAndEmptyArrays": True }},
            {"$project": {
                "_id": 0,
                "nature": "$nature",
                "isLocked": {"$ifNull": ["$isLocked", False]},
                "mainHead": {"$ifNull": ["$mainHeads.name", None]},
                "mainHeadIsLocked": {"$ifNull": ["$mainHeads.isLocked", False]},
                "category": {"$ifNull": ["$mainHeads.categories.name", None]},
                "categoryIsLocked": {"$ifNull": ["$mainHeads.categories.isLocked", False]},
                "enableOptions": {"$ifNull": ["$mainHeads.categories.enableOptions", []]}
            }}
        ]
        cursor = db_conn[CLASSIFICATION_COLLECTION].aggregate(pipeline)

        # The frontend expects a flat list to perform its own grouping.
        # We return the direct result from the aggregation pipeline.
        results = [doc for doc in cursor]
        return results
    except Exception as e:
        logging.error(f"Error fetching classifications for tenant {tenant_id}: {e}")
        raise

# --- ADD ---
def add_nature(db_conn, nature_name, user="System", tenant_id="default_tenant"):
    """Adds a new nature document."""
    try:
        if db_conn[CLASSIFICATION_COLLECTION].find_one({"nature": nature_name, "tenant_id": tenant_id}):
            raise ValueError(f"Nature '{nature_name}' already exists.")

        payload = {
            "nature": nature_name, "mainHeads": [], "isLocked": False,
            "created_date": datetime.utcnow(), "updated_date": datetime.utcnow(),
            "updated_user": user, "tenant_id": tenant_id
        }
        result = db_conn[CLASSIFICATION_COLLECTION].insert_one(payload)
        add_activity("CREATE_NATURE", user, f"Created new account nature: '{nature_name}'", result.inserted_id, CLASSIFICATION_COLLECTION, tenant_id)
        return result.inserted_id
    except Exception as e:
        logging.error(f"Error adding nature for tenant {tenant_id}: {e}")
        raise

def add_main_head(db_conn, nature_name, main_head_name, user="System", tenant_id="default_tenant"):
    """Adds a new main head to a nature."""
    try:
        result = db_conn[CLASSIFICATION_COLLECTION].update_one(
            {"nature": nature_name, "tenant_id": tenant_id},
            {"$addToSet": {"mainHeads": {"name": main_head_name, "isLocked": False, "categories": []}}}
        )
        if result.matched_count == 0: raise ValueError(f"Nature '{nature_name}' not found.")
        if result.modified_count > 0:
            add_activity("CREATE_MAIN_HEAD", user, f"Added Main Head '{main_head_name}' to Nature '{nature_name}'", None, CLASSIFICATION_COLLECTION, tenant_id)
        return result.modified_count > 0
    except Exception as e:
        logging.error(f"Error adding main head to '{nature_name}': {e}")
        raise

def add_category(db_conn, nature_name, main_head_name, category_name, user="System", tenant_id="default_tenant"):
    """Adds a new category to a main head."""
    try:
        result = db_conn[CLASSIFICATION_COLLECTION].update_one(
            {"nature": nature_name, "mainHeads.name": main_head_name, "tenant_id": tenant_id},
            {"$addToSet": {"mainHeads.$.categories": {"name": category_name, "isLocked": False, "enableOptions": []}}}
        )
        if result.matched_count == 0: raise ValueError(f"Main Head '{main_head_name}' not found.")
        if result.modified_count > 0:
             add_activity("CREATE_CATEGORY", user, f"Added Category '{category_name}' to '{nature_name} -> {main_head_name}'", None, CLASSIFICATION_COLLECTION, tenant_id)
        return result.modified_count > 0
    except Exception as e:
        logging.error(f"Error adding category to '{main_head_name}': {e}")
        raise

def add_option(db_conn, nature_name, main_head_name, category_name, option_name, user="System", tenant_id="default_tenant"):
    """Adds a new option to a category."""
    try:
        result = db_conn[CLASSIFICATION_COLLECTION].update_one(
            {"tenant_id": tenant_id, "nature": nature_name, "mainHeads.name": main_head_name},
            {"$addToSet": {"mainHeads.$[mh].categories.$[ct].enableOptions": option_name}},
            array_filters=[{"mh.name": main_head_name}, {"ct.name": category_name}]
        )
        if result.matched_count == 0: raise ValueError("The specified classification path was not found.")
        if result.modified_count > 0:
            add_activity("CREATE_OPTION", user, f"Added Option '{option_name}' to '{nature_name} -> {main_head_name} -> {category_name}'", None, CLASSIFICATION_COLLECTION, tenant_id)
        return result.modified_count > 0
    except Exception as e:
        logging.error(f"Error adding option to '{category_name}': {e}")
        raise

# --- DELETE ---
def delete_nature(db_conn, nature_name, user="System", tenant_id="default_tenant"):
    """Deletes an entire nature document."""
    try:
        result = db_conn[CLASSIFICATION_COLLECTION].delete_one({"nature": nature_name, "tenant_id": tenant_id})
        if result.deleted_count > 0:
            add_activity("DELETE_NATURE", user, f"Deleted entire account nature: '{nature_name}'", None, CLASSIFICATION_COLLECTION, tenant_id)
        return result.deleted_count > 0
    except Exception as e:
        logging.error(f"Error deleting nature '{nature_name}': {e}")
        raise

def delete_main_head(db_conn, nature_name, main_head_name, user="System", tenant_id="default_tenant"):
    """Deletes a main head from a nature."""
    try:
        result = db_conn[CLASSIFICATION_COLLECTION].update_one(
            {"nature": nature_name, "tenant_id": tenant_id},
            {"$pull": {"mainHeads": {"name": main_head_name}}}
        )
        if result.modified_count > 0:
             add_activity("DELETE_MAIN_HEAD", user, f"Deleted Main Head '{main_head_name}' from Nature '{nature_name}'", None, CLASSIFICATION_COLLECTION, tenant_id)
        return result.modified_count > 0
    except Exception as e:
        logging.error(f"Error deleting main head '{main_head_name}': {e}")
        raise

def delete_category(db_conn, nature_name, main_head_name, category_name, user="System", tenant_id="default_tenant"):
    """Deletes a category from a main head."""
    try:
        result = db_conn[CLASSIFICATION_COLLECTION].update_one(
            {"nature": nature_name, "mainHeads.name": main_head_name, "tenant_id": tenant_id},
            {"$pull": {"mainHeads.$.categories": {"name": category_name}}}
        )
        if result.modified_count > 0:
            add_activity("DELETE_CATEGORY", user, f"Deleted Category '{category_name}' from '{nature_name} -> {main_head_name}'", None, CLASSIFICATION_COLLECTION, tenant_id)
        return result.modified_count > 0
    except Exception as e:
        logging.error(f"Error deleting category '{category_name}': {e}")
        raise

def delete_option(db_conn, nature_name, main_head_name, category_name, option_name, user="System", tenant_id="default_tenant"):
    """Deletes an option from a category."""
    try:
        result = db_conn[CLASSIFICATION_COLLECTION].update_one(
            {"tenant_id": tenant_id, "nature": nature_name, "mainHeads.name": main_head_name},
            {"$pull": {"mainHeads.$[mh].categories.$[ct].enableOptions": option_name}},
            array_filters=[{"mh.name": main_head_name}, {"ct.name": category_name}]
        )
        if result.modified_count > 0:
            add_activity("DELETE_OPTION", user, f"Deleted Option '{option_name}' from '{nature_name} -> {main_head_name} -> {category_name}'", None, CLASSIFICATION_COLLECTION, tenant_id)
        return result.modified_count > 0
    except Exception as e:
        logging.error(f"Error deleting option '{option_name}': {e}")
        raise

# --- EDIT ---
def edit_nature(db_conn, old_name, new_name, user="System", tenant_id="default_tenant"):
    """Edits the name of a nature."""
    try:
        result = db_conn[CLASSIFICATION_COLLECTION].update_one(
            {"nature": old_name, "tenant_id": tenant_id},
            {"$set": {"nature": new_name, "updated_date": datetime.utcnow(), "updated_user": user}}
        )
        if result.modified_count > 0:
            add_activity("EDIT_NATURE", user, f"Renamed Nature from '{old_name}' to '{new_name}'", None, CLASSIFICATION_COLLECTION, tenant_id)
        return result.modified_count > 0
    except Exception as e:
        logging.error(f"Error editing nature '{old_name}': {e}")
        raise

def edit_main_head(db_conn, nature_name, old_name, new_name, user="System", tenant_id="default_tenant"):
    """Edits the name of a main head."""
    try:
        result = db_conn[CLASSIFICATION_COLLECTION].update_one(
            {"nature": nature_name, "tenant_id": tenant_id, "mainHeads.name": old_name},
            {"$set": {"mainHeads.$[mh].name": new_name}},
            array_filters=[{"mh.name": old_name}]
        )
        if result.modified_count > 0:
            add_activity("EDIT_MAIN_HEAD", user, f"Renamed Main Head in '{nature_name}' from '{old_name}' to '{new_name}'", None, CLASSIFICATION_COLLECTION, tenant_id)
        return result.modified_count > 0
    except Exception as e:
        logging.error(f"Error editing main head '{old_name}': {e}")
        raise

def edit_category(db_conn, nature_name, main_head_name, old_name, new_name, user="System", tenant_id="default_tenant"):
    """Edits the name of a category."""
    try:
        result = db_conn[CLASSIFICATION_COLLECTION].update_one(
            {"nature": nature_name, "tenant_id": tenant_id},
            {"$set": {"mainHeads.$[mh].categories.$[ct].name": new_name}},
            array_filters=[{"mh.name": main_head_name}, {"ct.name": old_name}]
        )
        if result.modified_count > 0:
             add_activity("EDIT_CATEGORY", user, f"Renamed Category in '{nature_name}->{main_head_name}' from '{old_name}' to '{new_name}'", None, CLASSIFICATION_COLLECTION, tenant_id)
        return result.modified_count > 0
    except Exception as e:
        logging.error(f"Error editing category '{old_name}': {e}")
        raise

def edit_option(db_conn, nature_name, main_head_name, category_name, old_name, new_name, user="System", tenant_id="default_tenant"):
    """Edits an option in a category."""
    try:
        # Pull the old name first
        pull_result = db_conn[CLASSIFICATION_COLLECTION].update_one(
            {"nature": nature_name, "tenant_id": tenant_id},
            {"$pull": {"mainHeads.$[mh].categories.$[ct].enableOptions": old_name}},
            array_filters=[{"mh.name": main_head_name}, {"ct.name": category_name}]
        )
        if pull_result.modified_count == 0:
            raise ValueError("Option not found to remove.")

        # Then add the new name
        push_result = db_conn[CLASSIFICATION_COLLECTION].update_one(
            {"nature": nature_name, "tenant_id": tenant_id},
            {"$addToSet": {"mainHeads.$[mh].categories.$[ct].enableOptions": new_name}},
            array_filters=[{"mh.name": main_head_name}, {"ct.name": category_name}]
        )
        if push_result.modified_count > 0:
            add_activity("EDIT_OPTION", user, f"Renamed Option in '{nature_name}->{main_head_name}->{category_name}' from '{old_name}' to '{new_name}'", None, CLASSIFICATION_COLLECTION, tenant_id)
        return push_result.modified_count > 0
    except Exception as e:
        logging.error(f"Error editing option '{old_name}': {e}")
        raise

# --- LOCK ---
def update_lock_status(db_conn, level, context, is_locked, user="System", tenant_id="default_tenant"):
    """Updates the lock status for a given level in the hierarchy."""
    try:
        query = {"tenant_id": tenant_id}
        update = {}
        array_filters = []

        if level == "nature":
            query["nature"] = context["name"]
            update["$set"] = {"isLocked": is_locked}
        elif level == "mainHead":
            query["nature"] = context["nature"]
            query["mainHeads.name"] = context["name"]
            update["$set"] = {"mainHeads.$[mh].isLocked": is_locked}
            array_filters.append({"mh.name": context["name"]})
        elif level == "category":
            query["nature"] = context["nature"]
            query["mainHeads.name"] = context["mainHead"]
            update["$set"] = {"mainHeads.$[mh].categories.$[ct].isLocked": is_locked}
            array_filters.append({"mh.name": context["mainHead"]})
            array_filters.append({"ct.name": context["name"]})
        else:
            raise ValueError("Invalid level provided for locking.")

        result = db_conn[CLASSIFICATION_COLLECTION].update_one(query, update, array_filters=array_filters)

        if result.modified_count > 0:
             action_type = f"LOCK_{level.upper()}" if is_locked else f"UNLOCK_{level.upper()}"
             details = f"{'Locked' if is_locked else 'Unlocked'} {level} '{context['name']}'"
             add_activity(action_type, user, details, None, CLASSIFICATION_COLLECTION, tenant_id)
        return result.modified_count > 0
    except Exception as e:
        logging.error(f"Error updating lock status for {level} '{context.get('name')}': {e}")
        raise
