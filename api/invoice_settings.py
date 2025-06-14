# api/invoice_settings.py
from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
import os
import json
from db.invoice_settings_dal import get_invoice_settings, save_invoice_settings, get_default_theme
from db.database import get_db

invoice_settings_bp = Blueprint('invoice_settings_bp', __name__, url_prefix='/api/invoice-settings')

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@invoice_settings_bp.route('', methods=['GET'])
def handle_get_invoice_settings(current_user_id=None): # Replace with actual user handling
    db = get_db()
    settings = get_invoice_settings(db, user_id=current_user_id)
    # get_invoice_settings from DAL v3 returns a structure with defaults if not found
    return jsonify(settings), 200

@invoice_settings_bp.route('', methods=['POST'])
def handle_save_invoice_settings(current_user_id=None): # Replace with actual user handling
    db = get_db()

    try:
        global_settings_data_str = request.form.get('global')
        saved_themes_list_str = request.form.get('savedThemes')

        if not global_settings_data_str or not saved_themes_list_str:
            current_app.logger.error("Missing 'global' or 'savedThemes' in form data.")
            return jsonify({"message": "Missing 'global' or 'savedThemes' data."}), 400

        global_settings_data = json.loads(global_settings_data_str)
        saved_themes_list = json.loads(saved_themes_list_str) # This should be a list of theme profile dicts

        if not isinstance(global_settings_data, dict) or not isinstance(saved_themes_list, list):
            raise ValueError("Parsed 'global' must be a dict and 'savedThemes' must be a list.")

        # Deprecated field 'decrementInvoiceNumberOnDelete' is handled by DAL if present in old data.
        # API layer doesn't need to explicitly remove it from global_settings_data if DAL does.

    except json.JSONDecodeError as e:
        current_app.logger.error(f"JSON Decode Error in settings: {e}. Global: '{request.form.get('global', 'Not Provided')}', Themes: '{request.form.get('savedThemes', 'Not Provided')}'")
        return jsonify({"message": "Invalid JSON format for global settings or saved themes."}), 400
    except ValueError as e:
        current_app.logger.error(f"Data type error after parsing: {e}")
        return jsonify({"message": str(e)}), 400
    except Exception as e:
        current_app.logger.error(f"Error parsing form data for settings: {e}")
        return jsonify({"message": "Error processing settings data."}), 400

    upload_folder_base = current_app.config['UPLOAD_FOLDER']
    if not os.path.exists(upload_folder_base):
        os.makedirs(upload_folder_base)

    # Iterate through each theme profile in the list to update its image URLs based on uploaded files
    for theme_profile in saved_themes_list:
        theme_id = theme_profile.get('id')
        if not theme_id:
            # DAL will assign an ID if missing, but file uploads need a stable ID from client
            current_app.logger.warning(f"Theme profile found without ID during file processing: {theme_profile.get('profileName')}")
            # Potentially skip file processing for this theme or assign a temporary ID if absolutely necessary
            # However, frontend should always send theme profiles with IDs.
            continue

        image_fields_map = {
            'signatureImage': {'url_field': 'signatureImageUrl', 'subfolder': 'signatures', 'remove_flag_prefix': 'removeSignature'},
            'upiQrCodeImage': {'url_field': 'upiQrCodeImageUrl', 'subfolder': 'upi_qr', 'remove_flag_prefix': 'removeUpiQrCode'},
            'invoiceFooterImage': {'url_field': 'invoiceFooterImageUrl', 'subfolder': 'footers', 'remove_flag_prefix': 'removeFooterImage'}
        }

        for form_field_key_prefix, details in image_fields_map.items():
            form_file_key = f"{form_field_key_prefix}_{theme_id}" # e.g., signatureImage_themeProfileId123
            form_remove_flag_key = f"{details['remove_flag_prefix']}_{theme_id}" # e.g., removeSignature_themeProfileId123

            subfolder_path = os.path.join(upload_folder_base, details['subfolder'])
            if not os.path.exists(subfolder_path):
                os.makedirs(subfolder_path)

            if request.form.get(form_remove_flag_key) == 'true':
                theme_profile[details['url_field']] = "" # Clear URL if remove flag is set
                # Optionally delete old file from server here if you store the old filename in theme_profile
            elif form_file_key in request.files:
                file = request.files[form_file_key]
                if file and file.filename != '' and allowed_file(file.filename):
                    # Prepend theme_id to filename for better organization and uniqueness
                    filename = secure_filename(f"{theme_id}_{file.filename}")
                    save_path = os.path.join(subfolder_path, filename)
                    try:
                        file.save(save_path)
                        theme_profile[details['url_field']] = f"/uploads/{details['subfolder']}/{filename}"
                    except Exception as e_save:
                        current_app.logger.error(f"Error saving file {filename}: {e_save}")
                        # Decide if this should be a fatal error or just a warning
                        return jsonify({"message": f"Error saving file {filename} for theme '{theme_profile.get('profileName')}'"}), 500
                elif file.filename != '': # File present but not allowed type
                    return jsonify({"message": f"File type not allowed for {form_file_key} of theme '{theme_profile.get('profileName')}'"}), 400
            # If no new file and no remove flag, the existing URL (already in theme_profile from parsed JSON) is kept.

    try:
        # The DAL function will handle merging with defaults and ensuring data integrity
        saved_settings_doc = save_invoice_settings(db, global_settings_data, saved_themes_list, user_id=current_user_id)
        if saved_settings_doc:
            return jsonify({"message": "Invoice settings saved successfully!", "data": saved_settings_doc}), 200
        else:
            # This case might indicate an issue in the DAL if it's supposed to always return a doc
            return jsonify({"message": "Failed to save settings or no changes made."}), 500
    except Exception as e:
        current_app.logger.error(f"Error saving invoice settings to DB: {e}")
        return jsonify({"message": "An error occurred while saving settings to database.", "error": str(e)}), 500


@invoice_settings_bp.route('/default-theme', methods=['GET'])
def handle_get_default_theme(current_user_id=None): # Replace with actual user handling
    db = get_db()
    theme_profile = get_default_theme(db, user_id=current_user_id)
    # get_default_theme from DAL v3 returns a full theme profile object
    return jsonify(theme_profile), 200

