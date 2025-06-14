# api/company_information.py
from flask import Blueprint, request, jsonify, current_app, session
import logging
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from bson import ObjectId # For validating ObjectId if needed, though not directly used for company info ID

# Import DAL functions
from db.company_information_dal import (
    get_company_information,
    create_or_update_company_information
)
# Import utility to get DB instance
from db.database import get_db

company_info_bp = Blueprint(
    'company_info_bp',
    __name__,
    url_prefix='/api/company-information'
)

logging.basicConfig(level=logging.INFO)

def allowed_file(filename):
    allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'svg'})
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def get_current_user():
    # Replace with your actual user retrieval logic
    return session.get('username', 'System_User_Placeholder')

def get_current_tenant_id():
    # Replace with your actual tenant ID retrieval logic
    # This placeholder should match the tenant_id used in your data
    return session.get('tenant_id', 'default_tenant')

@company_info_bp.route('', methods=['GET'])
def handle_get_company_info():
    """Handles GET requests to fetch company information for the current tenant."""
    try:
        db = get_db()
        current_tenant = get_current_tenant_id()
        logging.info(f"API: Fetching company info for tenant_id: {current_tenant}")
        company_info = get_company_information(db_conn=db, tenant_id=current_tenant)

        if company_info:
            # _id is already stringified by the DAL
            # Construct full logo URL if logoFilename exists
            if company_info.get('logoFilename'):
                 # The URL should be relative to the server root if frontend prepends API_BASE_URL
                 # Backend should provide a path that frontend can use.
                 company_info['logoUrl'] = f"/uploads/logos/{company_info['logoFilename']}"
            return jsonify(company_info), 200
        else:
            # Return an empty object or a default structure if no info found,
            # This helps frontend initialize its state.
            logging.info(f"API: No company info found for tenant_id: {current_tenant}. Returning empty object.")
            return jsonify({}), 200 # Or 404 if it's critical that info must exist
    except Exception as e:
        logging.error(f"Error in handle_get_company_info for tenant {get_current_tenant_id()}: {e}")
        current_app.logger.error(f"Error details in handle_get_company_info: {str(e)}")
        return jsonify({"message": "Failed to fetch company information", "error": str(e)}), 500

@company_info_bp.route('', methods=['POST', 'PUT'])
def handle_save_company_info():
    """
    Handles POST (create) or PUT (update) requests to save company information.
    Accepts multipart/form-data.
    """
    try:
        db = get_db()
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()
        logo_filename_to_save = None

        base_upload_folder = current_app.config.get('UPLOAD_FOLDER')
        if not base_upload_folder:
            logging.error("UPLOAD_FOLDER is not configured in the Flask app.")
            return jsonify({"message": "File upload configuration error on server."}), 500

        logos_upload_path = os.path.join(base_upload_folder, 'logos')
        if not os.path.exists(logos_upload_path):
            try:
                os.makedirs(logos_upload_path)
                logging.info(f"Created logos upload folder: {logos_upload_path}")
            except OSError as e_dir:
                logging.error(f"Could not create logos upload folder {logos_upload_path}: {e_dir}")
                return jsonify({"message": "File upload path configuration error on server."}), 500

        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename and allowed_file(file.filename):
                timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
                secure_base_filename = secure_filename(file.filename)
                filename = f"{current_tenant}_{timestamp}_{secure_base_filename}" # Unique filename

                file_path = os.path.join(logos_upload_path, filename)
                file.save(file_path)
                logo_filename_to_save = filename
                logging.info(f"Logo '{filename}' uploaded by {current_user} for tenant {current_tenant} to {file_path}.")
            elif file and file.filename:
                 logging.warning(f"Logo upload attempt by {current_user} for tenant {current_tenant} with disallowed extension: {file.filename}")
                 allowed_types_str = ', '.join(current_app.config.get('ALLOWED_EXTENSIONS', []))
                 return jsonify({"message": f"File type not allowed. Allowed types: {allowed_types_str}"}), 400

        data = request.form.to_dict()

        boolean_fields = [
            'gstRegistered', 'sameAsBilling', 'pfEnabled', 'esicEnabled',
            'iecRegistered', 'tdsEnabled', 'tcsEnabled', 'advanceTaxEnabled'
        ]
        for field in boolean_fields:
            if field in data:
                data[field] = str(data.get(field, 'false')).lower() == 'true'

        if logo_filename_to_save:
            data['logoFilename'] = logo_filename_to_save
        elif 'logoFilename' not in data and request.method == 'PUT':
            # If logoFilename is not in form data during PUT, it means frontend didn't send it.
            # We should preserve the existing one if no new logo is uploaded and no explicit removal.
            # The DAL's create_or_update handles $set, so if logoFilename isn't in `data`, it won't be $set.
            # If frontend wants to remove logo, it should send an empty logoFilename or a specific flag.
            pass

        # If frontend explicitly wants to remove the logo, it should send logoFilename as "" or null,
        # or a specific flag like 'removeLogo': 'true'.
        # For now, if 'logoFilename' is not in data, existing one is preserved by $set logic.
        # If 'logoFilename' is sent as empty string, it will be updated to empty string.

        result_doc_id_str = create_or_update_company_information(
            db_conn=db,
            data=data,
            user=current_user,
            tenant_id=current_tenant
        )

        if result_doc_id_str:
            saved_info = get_company_information(db_conn=db, tenant_id=current_tenant) # Fetch by tenant_id
            if saved_info:
                # _id is already stringified by DAL's get_company_information
                if saved_info.get('logoFilename'):
                    saved_info['logoUrl'] = f"/uploads/logos/{saved_info['logoFilename']}"
                return jsonify({"message": "Company information saved successfully", "data": saved_info}), 200
            else:
                 logging.error(f"Company info saved/updated for tenant {current_tenant}, but failed to retrieve for response.")
                 return jsonify({"message": "Company information saved, but failed to retrieve updated data"}), 200
        else:
            logging.warning(f"Failed to save company information for tenant {current_tenant} (no changes detected or DAL error).")
            # Check if it was an update with no actual changes vs. an error
            # The DAL returns None if upsert had no effect or error.
            # If it was an update and no fields changed, matched_count > 0 but modified_count = 0.
            # The DAL now returns the ID even if only matched_count > 0.
            # So, if result_doc_id_str is None, it's likely an issue.
            return jsonify({"message": "Failed to save company information or no effective changes made."}), 400

    except ValueError as ve: # Catch specific errors like invalid data from DAL
        logging.error(f"ValueError saving company info for tenant {get_current_tenant_id()}: {ve}")
        return jsonify({"message": str(ve)}), 400
    except Exception as e:
        logging.exception(f"Error in handle_save_company_info for tenant {get_current_tenant_id()}: {e}")
        current_app.logger.error(f"Error details in handle_save_company_info: {str(e)}. Form data (keys): {list(request.form.keys())}")
        return jsonify({"message": "An internal error occurred while saving company information", "error": str(e)}), 500

