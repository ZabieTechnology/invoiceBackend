# api/company_information.py
from flask import Blueprint, request, jsonify, current_app, session
import logging
import os
from werkzeug.utils import secure_filename
from datetime import datetime # Import datetime

# Import DAL functions
from db.company_information_dal import (
    get_company_information,
    create_or_update_company_information
)

# Define the blueprint
company_info_bp = Blueprint(
    'company_info_bp',
    __name__,
    url_prefix='/api/company-information'
)

# Configure basic logging
logging.basicConfig(level=logging.INFO)

# --- REMOVE UPLOAD_FOLDER and ALLOWED_EXTENSIONS definitions from module level ---
# UPLOAD_FOLDER = os.path.join(current_app.root_path, 'uploads', 'logos') # REMOVE THIS
# ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'svg'} # REMOVE THIS

# --- Move allowed_file function or define it inside the route ---
# Helper function to check allowed file extensions
def allowed_file(filename):
    # Access allowed extensions from app config *when the function is called*
    allowed_extensions = current_app.config['ALLOWED_EXTENSIONS']
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

# Helper function to get current user (replace with actual auth logic later)
def get_current_user():
    return session.get('username', 'System')

@company_info_bp.route('', methods=['GET'])
def handle_get_company_info():
    """Handles GET requests to fetch company information."""
    try:
        company_info = get_company_information()
        if company_info:
            company_info['_id'] = str(company_info['_id'])
            # Construct logo URL if filename exists
            if company_info.get('logoFilename'):
                 # Assuming you configure Flask to serve static files from 'uploads'
                 # You might need to adjust the base URL depending on your setup
                 # For development, accessing via backend URL might be needed
                 # In production, usually served by Nginx/Apache directly
                 # This example assumes direct access via backend route or static config
                 # TODO: Configure static file serving for uploads
                 company_info['logoUrl'] = f"/uploads/logos/{company_info['logoFilename']}" # Example URL path
            return jsonify(company_info), 200
        else:
            return jsonify({}), 200
    except Exception as e:
        logging.error(f"Error in handle_get_company_info: {e}")
        return jsonify({"message": "Failed to fetch company information"}), 500

@company_info_bp.route('', methods=['POST', 'PUT'])
def handle_save_company_info():
    """
    Handles POST (create) or PUT (update) requests to save company information.
    Accepts multipart/form-data.
    """
    try:
        current_user = get_current_user()
        logo_filename = None

        # --- Get config values within the request context ---
        upload_folder = current_app.config['UPLOAD_FOLDER']
        # allowed_extensions = current_app.config['ALLOWED_EXTENSIONS'] # Used by allowed_file()

        # --- Handle File Upload ---
        if 'logo' in request.files:
            file = request.files['logo']
            # Check if a file was selected and if it's allowed
            if file and file.filename and allowed_file(file.filename):
                # Generate a secure, unique filename
                timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f') # More unique timestamp
                secure_base_filename = secure_filename(file.filename)
                filename = f"{current_user}_{timestamp}_{secure_base_filename}"

                # Ensure upload directory exists (optional here if done at app start)
                # if not os.path.exists(upload_folder):
                #     os.makedirs(upload_folder)
                #     logging.info(f"Created upload folder: {upload_folder}")

                file_path = os.path.join(upload_folder, filename)
                file.save(file_path)
                logo_filename = filename # Store filename to save in DB
                logging.info(f"Logo '{filename}' uploaded successfully by {current_user}.")

            elif file and file.filename: # Check if a file was selected but not allowed
                 logging.warning(f"Logo upload attempt with disallowed extension: {file.filename}")
                 allowed_types_str = ', '.join(current_app.config['ALLOWED_EXTENSIONS'])
                 return jsonify({"message": f"File type not allowed. Allowed types: {allowed_types_str}"}), 400
            # If file.filename is empty, no file was actually selected, so do nothing.


        # --- Process Form Data ---
        data = request.form.to_dict()

        boolean_fields = [
            'gstRegistered', 'sameAsBilling', 'pfEnabled', 'esicEnabled',
            'iecRegistered', 'tdsEnabled', 'tcsEnabled', 'advanceTaxEnabled'
        ]
        for field in boolean_fields:
            if field in data:
                # Handle potential missing fields gracefully
                data[field] = data.get(field, 'false').lower() == 'true'

        # Add logo filename to data if a new one was uploaded
        if logo_filename:
            # TODO: Optionally delete the old logo file if replacing
            data['logoFilename'] = logo_filename
        # If no new logo uploaded, keep the existing logoFilename (if any) from being overwritten unless explicitly cleared
        elif 'logoFilename' not in data and request.method == 'PUT':
             # Prevent accidentally clearing the logo if not included in PUT form data
             # Fetch existing data to preserve logo if needed, or handle on frontend
             pass # Or fetch existing doc and merge if necessary


        # --- Save to Database ---
        result_id = create_or_update_company_information(data, user=current_user)

        if result_id:
            saved_info = get_company_information() # Fetch the latest data
            if saved_info:
                saved_info['_id'] = str(saved_info['_id'])
                # Construct logo URL for response
                if saved_info.get('logoFilename'):
                    saved_info['logoUrl'] = f"/uploads/logos/{saved_info['logoFilename']}" # Example URL path
                return jsonify({"message": "Company information saved successfully", "data": saved_info}), 200
            else:
                 return jsonify({"message": "Company information saved, but failed to retrieve updated data"}), 200
        else:
            return jsonify({"message": "Failed to save company information (no changes detected or error)"}), 500 # Changed status code

    except Exception as e:
        logging.exception(f"Error in handle_save_company_info: {e}")
        return jsonify({"message": "An internal error occurred while saving company information"}), 500

