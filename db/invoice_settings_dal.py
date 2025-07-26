# db/invoice_settings_dal.py
from pymongo import ReturnDocument
from bson import ObjectId
import json

INVOICE_SETTINGS_COLLECTION = 'invoice_settings'

# Default structure for a single theme profile's specific settings
# Updated to match the latest frontend structure from InvoiceSettingsPage.js
default_single_theme_profile_data = {
    "baseThemeName": "Simple",
    "selectedColor": "#757575",
    "textColor": "#212121",
    "itemTableColumns": {
        "pricePerItem": True,
        "quantity": True,
        "batchNo": False,
        "expDate": False,
        "mfgDate": False,
        "discountPerItem": False,
        "hsnSacCode": True,
        "serialNo": False,
        "showCess": False,
        "showVat": False,
        "showGrossValue": True,
    },
    "taxDisplayMode": "breakdown",  # 'no_tax' or 'breakdown'
    "customItemColumns": [],
    "invoiceHeading": "TAX INVOICE",
    "invoicePrefix": "INV-",
    "invoiceSuffix": "",
    "showPoNumber": True,
    "customHeaderFields": [],
    "upiId": "",
    "upiQrCodeImageUrl": "",
    "bankAccountId": '',
    "defaultSalesAccountId": '',
    "showSaleAgentOnInvoice": False,
    "showBillToSection": True,
    "showShipToSection": True,
    "showAmountReceived": True,
    "showCreditNoteIssued": True,
    "showExpensesAdjusted": True,
    "signatureImageUrl": '',
    "authorisedSignatory": 'For (Your Company Name)',
    "invoiceFooter": "",
    "invoiceFooterImageUrl": "",
    "termsAndConditionsId": '',
    "notesDefault": "Thank you for your business!",
    "enableRounding": False,
    "roundingMethod": 'auto',
    "invoiceTotalCalculation": 'auto',
    "roundOffAccountId": '',
    "additionalCharges": [
        {
            "id": 'mandatory_discount',
            "label": 'Discount',
            "valueType": 'percentage',
            "value": 0,
            "accountId": '',
            "isMandatory": True,
            "showInPreview": True,
        }
    ],
}

# Default for global settings
default_global_settings = {
    "companyLogoUrl": "/images/default_logo.png",
    "nextInvoiceNumber": 1,
    "currency": "INR",
}

def get_invoice_settings(db_conn, user_id=None):
    """
    Retrieves the entire invoice settings document, ensuring it conforms to the latest structure.
    """
    query = {}
    settings_doc = db_conn[INVOICE_SETTINGS_COLLECTION].find_one(query)

    if settings_doc:
        # Ensure global settings are up-to-date
        settings_doc['global'] = {**default_global_settings, **settings_doc.get('global', {})}
        settings_doc['global'].pop('decrementInvoiceNumberOnDelete', None) # Remove obsolete key

        if 'savedThemes' not in settings_doc or not isinstance(settings_doc.get('savedThemes'), list) or not settings_doc['savedThemes']:
            # If themes are missing, create a default one
            default_theme_id = f"theme_profile_{str(ObjectId())}"
            settings_doc['savedThemes'] = [{
                "id": default_theme_id,
                "profileName": 'Default Theme',
                "isDefault": True,
                **default_single_theme_profile_data
            }]
        else:
            # Process existing themes to merge with new defaults
            seen_ids = set()
            has_default = False
            processed_themes = []
            for theme_profile in settings_doc['savedThemes']:
                theme_id = theme_profile.get('id', f"theme_profile_{str(ObjectId())}")
                while theme_id in seen_ids:
                    theme_id = f"theme_profile_{str(ObjectId())}"
                seen_ids.add(theme_id)

                # Handle legacy fields stored as JSON strings
                for field_key in ['itemTableColumns', 'customItemColumns', 'customHeaderFields', 'additionalCharges']:
                    if field_key in theme_profile and isinstance(theme_profile[field_key], str):
                        try:
                            theme_profile[field_key] = json.loads(theme_profile[field_key])
                        except json.JSONDecodeError:
                            print(f"Warning: Could not parse JSON for nested field {field_key} in theme {theme_id}. Using default.")
                            theme_profile[field_key] = default_single_theme_profile_data.get(field_key, [])

                # Remove deprecated fields
                theme_profile.pop('invoiceDueAfterDays', None)
                theme_profile.pop('showGstBreakdown', None)
                theme_profile.pop('enableReceiverSignature', None)
                if 'itemTableColumns' in theme_profile:
                    theme_profile['itemTableColumns'].pop('taxRate', None)
                    theme_profile['itemTableColumns'].pop('taxPerItem', None)

                # Merge with the latest default structure
                full_theme_profile = {
                    **default_single_theme_profile_data,
                    **theme_profile,
                    "id": theme_id
                }

                # **NEW**: For backward compatibility, ensure the mandatory discount charge exists.
                # This mirrors the logic from the frontend.
                if not isinstance(full_theme_profile.get('additionalCharges'), list):
                    full_theme_profile['additionalCharges'] = []

                if not any(charge.get('id') == 'mandatory_discount' for charge in full_theme_profile['additionalCharges']):
                    full_theme_profile['additionalCharges'].insert(0, {
                        "id": 'mandatory_discount',
                        "label": 'Discount',
                        "valueType": 'percentage',
                        "value": 0,
                        "accountId": '',
                        "isMandatory": True,
                        "showInPreview": True,
                    })

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
        # Return a completely new, default settings document if none exists
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
    Saves the entire invoice settings document, merging with defaults to ensure integrity.
    """
    collection = db_conn[INVOICE_SETTINGS_COLLECTION]

    # Clean up global settings
    if global_settings_data:
        global_settings_data.pop('decrementInvoiceNumberOnDelete', None)

    # Ensure there is at least one theme and one default
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

        # Handle fields that might be sent as JSON strings
        nested_json_fields = ['itemTableColumns', 'customItemColumns', 'customHeaderFields', 'additionalCharges']
        for field_key in nested_json_fields:
            if field_key in theme_profile and isinstance(theme_profile[field_key], str):
                try:
                    theme_profile[field_key] = json.loads(theme_profile[field_key])
                except json.JSONDecodeError:
                    print(f"Warning: Could not parse JSON for nested field {field_key}. Using default.")
                    theme_profile[field_key] = default_single_theme_profile_data.get(field_key, [])

        # Remove deprecated settings
        theme_profile.pop('invoiceDueAfterDays', None)
        theme_profile.pop('showGstBreakdown', None)
        theme_profile.pop('enableReceiverSignature', None)
        if 'itemTableColumns' in theme_profile:
            theme_profile['itemTableColumns'].pop('taxRate', None)
            theme_profile['itemTableColumns'].pop('taxPerItem', None)

        # Ensure unique IDs
        theme_id = theme_profile.get('id', f"theme_profile_{str(ObjectId())}")
        while theme_id in seen_ids:
            theme_id = f"theme_profile_{str(ObjectId())}"
        seen_ids.add(theme_id)

        # Merge with defaults before saving
        processed_themes.append({
            **default_single_theme_profile_data,
            **theme_profile,
            "id": theme_id
        })

    # Prepare the final document for database operation
    full_settings_data = {
        "global": {**default_global_settings, **global_settings_data},
        "savedThemes": processed_themes
    }

    query = {}
    existing_settings = collection.find_one(query)

    if existing_settings:
        # Update existing document
        settings_id = existing_settings['_id']
        collection.update_one({"_id": settings_id}, {"$set": full_settings_data})
        updated_doc = collection.find_one({"_id": settings_id})
    else:
        # Insert a new document
        insert_result = collection.insert_one(full_settings_data)
        updated_doc = collection.find_one({"_id": insert_result.inserted_id})

    if updated_doc and '_id' in updated_doc:
        updated_doc['_id'] = str(updated_doc['_id'])
    return updated_doc

def get_default_theme(db_conn, user_id=None):
    """
    Retrieves the default theme profile from the settings.
    """
    settings = get_invoice_settings(db_conn, user_id)
    if settings and settings.get('savedThemes'):
        for theme_profile in settings['savedThemes']:
            if theme_profile.get('isDefault'):
                return theme_profile

    # Fallback if no default is found
    default_theme_id = f"theme_profile_{str(ObjectId())}"
    return {
        "id": default_theme_id, "profileName": 'Fallback Default Theme', "isDefault": True,
        **default_single_theme_profile_data
    }
