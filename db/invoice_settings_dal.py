# db/invoice_settings_dal.py
from pymongo import ReturnDocument
from bson import ObjectId
import json

INVOICE_SETTINGS_COLLECTION = 'invoice_settings'

# Default structure for a single theme profile's specific settings
default_single_theme_profile_data = {
    "baseThemeName": "Modern",
    "selectedColor": "#4CAF50",
    "itemTableColumns": {
        "pricePerItem": True, "quantity": True, "batchNo": False, "expDate": False, "mfgDate": False,
        "discountPerItem": False, "taxRate": True, "taxPerItem": True, "hsnSacCode": True, "serialNo": False,
    },
    "customItemColumns": [],
    "invoiceHeading": "TAX INVOICE",
    "invoicePrefix": "INV-",
    "invoiceSuffix": "",
    "invoiceDueAfterDays": 30,
    "showPoNumber": True,  # Added: Default for PO Number visibility per theme
    "customHeaderFields": [], # Added: Default for custom header fields per theme
    "upiId": "",
    "upiQrCodeImageUrl": "",
    "bankAccountId": '',
    "showSaleAgentOnInvoice": False,
    "showBillToSection": True,
    "showShipToSection": True,
    "signatureImageUrl": '',
    "enableReceiverSignature": False,
    "invoiceFooter": "",
    "invoiceFooterImageUrl": "",
    "termsAndConditionsId": '',
    "notesDefault": "Thank you for your business!",
}

# Default for global settings
default_global_settings = {
    "companyLogoUrl": "/images/default_logo.png",
    "nextInvoiceNumber": 1,
    "currency": "INR",
    # "decrementInvoiceNumberOnDelete": False, // REMOVED from global as well if it was here
}

def get_invoice_settings(db_conn, user_id=None):
    """
    Retrieves the entire invoice settings document.
    """
    query = {}
    settings_doc = db_conn[INVOICE_SETTINGS_COLLECTION].find_one(query)

    if settings_doc:
        if 'global' not in settings_doc:
            settings_doc['global'] = default_global_settings
        else:
            settings_doc['global'] = {**default_global_settings, **settings_doc['global']}
            # Remove deprecated global setting if it exists from old saves
            settings_doc['global'].pop('decrementInvoiceNumberOnDelete', None)


        if 'savedThemes' not in settings_doc or not isinstance(settings_doc.get('savedThemes'), list) or not settings_doc['savedThemes']:
            default_theme_id = f"theme_profile_{str(ObjectId())}"
            settings_doc['savedThemes'] = [{
                "id": default_theme_id,
                "profileName": 'Default Theme',
                "isDefault": True,
                **default_single_theme_profile_data
            }]
        else:
            seen_ids = set()
            has_default = False
            processed_themes = []
            for theme_profile in settings_doc['savedThemes']:
                theme_id = theme_profile.get('id', f"theme_profile_{str(ObjectId())}")
                while theme_id in seen_ids:
                    theme_id = f"theme_profile_{str(ObjectId())}"
                seen_ids.add(theme_id)

                for field_key in ['itemTableColumns', 'customItemColumns', 'customHeaderFields']:
                    if field_key in theme_profile and isinstance(theme_profile[field_key], str):
                        try:
                            theme_profile[field_key] = json.loads(theme_profile[field_key])
                        except json.JSONDecodeError:
                            print(f"Warning: Could not parse JSON for nested field {field_key} in theme {theme_id}. Using default.")
                            theme_profile[field_key] = default_single_theme_profile_data.get(field_key, [] if 'Columns' in field_key or 'Fields' in field_key else {})

                full_theme_profile = {
                    **default_single_theme_profile_data,
                    **theme_profile,
                    "id": theme_id
                }
                processed_themes.append(full_theme_profile)
                if full_theme_profile.get('isDefault'):
                    has_default = True

            if not has_default and processed_themes:
                processed_themes[0]['isDefault'] = True
            settings_doc['savedThemes'] = processed_themes

        if '_id' in settings_doc:
            settings_doc['_id'] = str(settings_doc['_id'])
        return settings_doc
    else:
        default_theme_id = f"theme_profile_{str(ObjectId())}"
        return {
            "_id": None,
            "global": default_global_settings,
            "savedThemes": [{
                "id": default_theme_id,
                "profileName": 'Default Initial Theme',
                "isDefault": True,
                **default_single_theme_profile_data
            }]
        }

def save_invoice_settings(db_conn, global_settings_data, saved_themes_list, user_id=None):
    """
    Saves the entire invoice settings document.
    """
    collection = db_conn[INVOICE_SETTINGS_COLLECTION]

    # Clean global settings data from deprecated fields
    if global_settings_data and 'decrementInvoiceNumberOnDelete' in global_settings_data:
        del global_settings_data['decrementInvoiceNumberOnDelete']

    if not isinstance(saved_themes_list, list) or not saved_themes_list:
        default_theme_id = f"theme_profile_{str(ObjectId())}"
        saved_themes_list = [{
            "id": default_theme_id, "profileName": 'Fallback Default', "isDefault": True,
            **default_single_theme_profile_data
        }]
    elif not any(theme.get('isDefault') for theme in saved_themes_list):
        if saved_themes_list:
             saved_themes_list[0]['isDefault'] = True

    processed_themes = []
    seen_ids = set()
    for theme_profile_from_api in saved_themes_list:
        theme_profile = dict(theme_profile_from_api)

        nested_json_fields = ['itemTableColumns', 'customItemColumns', 'customHeaderFields']
        for field_key in nested_json_fields:
            if field_key in theme_profile and isinstance(theme_profile[field_key], str):
                try:
                    theme_profile[field_key] = json.loads(theme_profile[field_key])
                except json.JSONDecodeError:
                    print(f"Warning: Could not parse JSON for nested field {field_key} in theme profile. Using default.")
                    theme_profile[field_key] = default_single_theme_profile_data.get(field_key, [] if 'Columns' in field_key or 'Fields' in field_key else {})
            elif field_key not in theme_profile:
                 theme_profile[field_key] = default_single_theme_profile_data.get(field_key, [] if 'Columns' in field_key or 'Fields' in field_key else {})

        # Remove deprecated setting if it somehow exists in a theme profile
        theme_profile.pop('decrementInvoiceNumberOnDelete', None)


        theme_id = theme_profile.get('id', f"theme_profile_{str(ObjectId())}")
        while theme_id in seen_ids:
            theme_id = f"theme_profile_{str(ObjectId())}"
        seen_ids.add(theme_id)

        processed_themes.append({
            **default_single_theme_profile_data,
            **theme_profile,
            "id": theme_id
        })

    full_settings_data = {
        "global": {**default_global_settings, **global_settings_data},
        "savedThemes": processed_themes
    }

    query = {}
    existing_settings = collection.find_one(query)

    if existing_settings:
        settings_id = existing_settings['_id']
        collection.update_one({"_id": settings_id}, {"$set": full_settings_data})
        updated_doc = collection.find_one({"_id": settings_id})
        if updated_doc and '_id' in updated_doc:
            updated_doc['_id'] = str(updated_doc['_id'])
        return updated_doc
    else:
        insert_result = collection.insert_one(full_settings_data)
        new_doc = collection.find_one({"_id": insert_result.inserted_id})
        if new_doc and '_id' in new_doc:
            new_doc['_id'] = str(new_doc['_id'])
        return new_doc

def get_default_theme(db_conn, user_id=None):
    settings = get_invoice_settings(db_conn, user_id)
    if settings and settings.get('savedThemes'):
        for theme_profile in settings['savedThemes']:
            if theme_profile.get('isDefault'):
                return theme_profile
    default_theme_id = f"theme_profile_{str(ObjectId())}"
    return {
        "id": default_theme_id, "profileName": 'Fallback Default Theme', "isDefault": True,
        **default_single_theme_profile_data
    }
