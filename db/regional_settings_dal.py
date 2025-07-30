# src/db/regional_settings_dal.py
from bson.objectid import ObjectId
from datetime import datetime
import logging
import json
from .activity_log_dal import add_activity

SETTINGS_COLLECTION = 'regional_settings'
logging.basicConfig(level=logging.INFO)

def _sanitize_country_code(code):
    """Ensures the country code starts with a '+' sign."""
    if code and isinstance(code, str) and not code.startswith('+'):
        return f"+{code}"
    return code

def ensure_indexes(db_conn):
    """Ensures a unique index on regionName for the global collection."""
    try:
        db_conn[SETTINGS_COLLECTION].create_index([("regionName", 1)], unique=True)
        logging.info(f"Indexes ensured for collection: {SETTINGS_COLLECTION}")
    except Exception as e:
        logging.error(f"Error creating indexes for {SETTINGS_COLLECTION}: {e}")
        raise

def get_all_regional_settings(db_conn):
    """Fetches all global regional settings."""
    try:
        if SETTINGS_COLLECTION not in db_conn.list_collection_names():
            logging.warning(f"Collection '{SETTINGS_COLLECTION}' does not exist. Creating indexes and returning empty list.")
            ensure_indexes(db_conn)
            return []

        settings = list(db_conn[SETTINGS_COLLECTION].find({}))
        for setting in settings:
            setting['_id'] = str(setting['_id'])
            for state in setting.get('states', []):
                state['_id'] = str(state.get('_id'))
        return settings
    except Exception as e:
        logging.error(f"Error fetching global regional settings: {e}")
        raise

def add_regional_setting(db_conn, data, user="System"):
    """Adds a new global regional setting, checking for duplicates."""
    try:
        # The unique index on 'regionName' will handle duplicate prevention at the DB level.
        payload = {
            "regionName": data.get("regionName"),
            "states": [],
            "currency": data.get("currency"),
            "countryCode": _sanitize_country_code(data.get("countryCode")),
            "flag": data.get("flag"),
            "currencySymbol": data.get("currencySymbol"),
            "isDefaultBase": data.get("isDefaultBase", False),
            "isLocked": data.get("isLocked", False),
            "created_date": datetime.utcnow(),
            "updated_date": datetime.utcnow(),
            "updated_user": user,
        }

        if payload["isDefaultBase"]:
            db_conn[SETTINGS_COLLECTION].update_many({}, {"$set": {"isDefaultBase": False}})

        result = db_conn[SETTINGS_COLLECTION].insert_one(payload)
        add_activity("CREATE_REGIONAL_SETTING", user, f"Created new global regional setting: '{payload['regionName']}'", result.inserted_id, SETTINGS_COLLECTION, "global")
        return str(result.inserted_id)
    except Exception as e:
        if "E11000 duplicate key error" in str(e):
             raise ValueError(f"A region with the name '{data.get('regionName')}' already exists.")
        logging.error(f"Error adding global regional setting: {e}")
        raise

def bulk_add_regional_settings(db_conn, regions, user="System"):
    """Adds multiple global regional settings, including their states, and skipping duplicates."""
    if not regions:
        return {"inserted": 0, "skipped": 0}
    try:
        existing_names = {r['regionName'].lower() for r in db_conn[SETTINGS_COLLECTION].find({}, {"regionName": 1})}
        payloads = []
        skipped_count = 0

        for region_data in regions:
            region_name = region_data.get("regionName")
            if not region_name or region_name.lower() in existing_names:
                skipped_count += 1
                continue

            # Handle states data from CSV
            states_raw = region_data.get("states", "[]")
            sanitized_states = []
            if states_raw and isinstance(states_raw, str):
                try:
                    states_list = json.loads(states_raw)
                    if isinstance(states_list, list):
                        sanitized_states = [
                            {"_id": ObjectId(), "name": s.get('name'), "code": s.get('code', ''), "zone": s.get('zone', 'State')}
                            for s in states_list if s.get('name')
                        ]
                except json.JSONDecodeError:
                    logging.warning(f"Could not parse states for region '{region_name}'. It was not valid JSON.")

            payload = {
                "regionName": region_name,
                "states": sanitized_states,
                "currency": region_data.get("currency"),
                "countryCode": _sanitize_country_code(region_data.get("countryCode")),
                "flag": region_data.get("flag", ""),
                "currencySymbol": region_data.get("currencySymbol", ""),
                "isDefaultBase": False,
                "isLocked": False,
                "created_date": datetime.utcnow(),
                "updated_date": datetime.utcnow(),
                "updated_user": user,
            }
            payloads.append(payload)
            existing_names.add(region_name.lower())

        if not payloads:
            return {"inserted": 0, "skipped": skipped_count}

        result = db_conn[SETTINGS_COLLECTION].insert_many(payloads, ordered=False)
        inserted_count = len(result.inserted_ids)
        if inserted_count > 0:
            add_activity("BULK_CREATE_REGIONAL_SETTINGS", user, f"Bulk imported {inserted_count} new global settings.", None, SETTINGS_COLLECTION, "global")
        return {"inserted": inserted_count, "skipped": skipped_count}
    except Exception as e:
        logging.error(f"Error in bulk adding global regional settings: {e}")
        raise


def update_regional_setting(db_conn, region_id, data, user="System"):
    """Updates an existing global regional setting."""
    try:
        if data.get("isDefaultBase"):
            db_conn[SETTINGS_COLLECTION].update_many({"_id": {"$ne": ObjectId(region_id)}}, {"$set": {"isDefaultBase": False}})

        result = db_conn[SETTINGS_COLLECTION].update_one(
            {"_id": ObjectId(region_id)},
            {"$set": {
                "regionName": data.get("regionName"), "currency": data.get("currency"),
                "countryCode": _sanitize_country_code(data.get("countryCode")), "flag": data.get("flag"),
                "currencySymbol": data.get("currencySymbol"), "isDefaultBase": data.get("isDefaultBase"),
                "isLocked": data.get("isLocked"), "updated_date": datetime.utcnow(), "updated_user": user
            }}
        )
        if result.modified_count > 0:
            add_activity("UPDATE_REGIONAL_SETTING", user, f"Updated global regional setting: '{data.get('regionName')}'", ObjectId(region_id), SETTINGS_COLLECTION, "global")
        return result.modified_count > 0
    except Exception as e:
        if "E11000 duplicate key error" in str(e):
             raise ValueError(f"A region with the name '{data.get('regionName')}' already exists.")
        logging.error(f"Error updating global regional setting ID {region_id}: {e}")
        raise

def delete_regional_setting(db_conn, region_id, user="System"):
    """Deletes a global regional setting."""
    try:
        result = db_conn[SETTINGS_COLLECTION].delete_one({"_id": ObjectId(region_id)})
        if result.deleted_count > 0:
            add_activity("DELETE_REGIONAL_SETTING", user, f"Deleted global regional setting ID: '{region_id}'", None, SETTINGS_COLLECTION, "global")
        return result.deleted_count > 0
    except Exception as e:
        logging.error(f"Error deleting global regional setting ID {region_id}: {e}")
        raise

def update_states_for_region(db_conn, region_id, states, user="System"):
    """Updates the states array for a specific global region."""
    try:
        sanitized_states = [{"_id": ObjectId(), "name": s['name'], "code": s.get('code', ''), "zone": s.get('zone', 'State')} for s in states]
        result = db_conn[SETTINGS_COLLECTION].update_one(
            {"_id": ObjectId(region_id)},
            {"$set": {"states": sanitized_states, "updated_date": datetime.utcnow(), "updated_user": user}}
        )
        if result.modified_count > 0:
            add_activity("UPDATE_STATES", user, f"Updated states for global region ID: '{region_id}'", ObjectId(region_id), SETTINGS_COLLECTION, "global")

        updated_doc = db_conn[SETTINGS_COLLECTION].find_one({"_id": ObjectId(region_id)})
        if updated_doc:
            for state in updated_doc.get('states', []):
                state['_id'] = str(state['_id'])
            return updated_doc['states']
        return None
    except Exception as e:
        logging.error(f"Error updating states for global region ID {region_id}: {e}")
        raise
