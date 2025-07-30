# api/company_information.py
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt, get_jwt_identity
import logging
import os
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import re
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
import json

from db.company_information_dal import get_company_information, create_or_update_company_information
from db.database import get_db
from db.user_dal import get_user_by_id
from db.document_rules_dal import get_or_create_rules

company_info_bp = Blueprint(
    'company_info_bp',
    __name__,
    url_prefix='/api/company-information'
)

logging.basicConfig(level=logging.INFO)

# --- Azure Blob Storage Configuration ---
AZURE_CONNECTION_STRING = os.environ.get("AZURE_STORAGE_CONNECTION_STRING")
AZURE_CONTAINER_NAME = os.environ.get("AZURE_STORAGE_CONTAINER_NAME")

def get_azure_storage_creds():
    creds = {}
    if AZURE_CONNECTION_STRING:
        parts = AZURE_CONNECTION_STRING.split(';')
        creds['account_name'] = next((p.split('=', 1)[1] for p in parts if p.startswith('AccountName=')), None)
        creds['account_key'] = next((p.split('=', 1)[1] for p in parts if p.startswith('AccountKey=')), None)
    return creds

AZURE_STORAGE_CREDS = get_azure_storage_creds()

def allowed_file(filename):
    allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'svg'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

def get_requesting_user_name():
    user_id = get_jwt_identity()
    user = get_user_by_id(user_id)
    return user.get("username", "System") if user else "System"

def get_tenant_id_from_token():
    claims = get_jwt()
    return claims.get("tenant_id")

def _generate_sas_url(blob_name):
    """Generates a SAS URL for a given blob name."""
    if not AZURE_STORAGE_CREDS.get('account_name') or not AZURE_STORAGE_CREDS.get('account_key'):
        logging.error("Azure Storage credentials for SAS token generation are not configured.")
        return None

    sas_token = generate_blob_sas(
        account_name=AZURE_STORAGE_CREDS['account_name'],
        container_name=AZURE_CONTAINER_NAME,
        blob_name=blob_name,
        account_key=AZURE_STORAGE_CREDS['account_key'],
        permission=BlobSasPermissions(read=True),
        expiry=datetime.utcnow() + timedelta(hours=1)
    )
    return f"https://{AZURE_STORAGE_CREDS['account_name']}.blob.core.windows.net/{AZURE_CONTAINER_NAME}/{blob_name}?{sas_token}"

def validate_data_with_rules(data, rules):
    """
    Validates submitted data against dynamic rules from the database,
    including parsing rule text for specific validation logic.
    """
    errors = []
    org_type = data.get('organizationType')

    if not org_type:
        errors.append({"field": "organizationType", "message": "Organization Type is a required field."})
        return errors # Stop validation if org type is missing

    business_rule = next((rule for rule in rules.get('business_rules', []) if rule['name'] == org_type), None)

    if business_rule:
        # --- Dynamic PAN Validation ---
        pan_rule_text = business_rule.get('pan_rules', '')
        pan_number = data.get('panNumber')

        if 'required' in pan_rule_text.lower() and not pan_number:
            errors.append({"field": "panNumber", "message": "PAN Number is required.", "rule": pan_rule_text})
        elif pan_number:
            # Dynamically create regex from rule text if possible
            # This looks for patterns like "10-character" and "4th character must be 'C'"
            char_match = re.search(r"(\d+)(?:st|nd|rd|th) character must be '([A-Z])'", pan_rule_text, re.IGNORECASE)
            length_match = re.search(r"(\d+)-character", pan_rule_text)

            pan_pattern = r'^[A-Z]{5}[0-9]{4}[A-Z]$' # Default PAN format
            if length_match:
                 pan_pattern = f'^.{{{length_match.group(1)}}}$'

            if char_match:
                pos, char = int(char_match.group(1)), char_match.group(2)
                # Modify pattern to enforce the specific character at the given position
                pattern_list = list('..........') # 10 dots for 10 characters
                pattern_list[0:5] = ['[A-Z]']*5
                pattern_list[5:9] = ['[0-9]']*4
                pattern_list[9] = '[A-Z]'
                pattern_list[pos-1] = char
                pan_pattern = f"^{''.join(pattern_list)}$"


            if not re.match(pan_pattern, pan_number):
                errors.append({"field": "panNumber", "message": "Invalid PAN format.", "rule": pan_rule_text})

        # --- GSTIN Validation ---
        gst_rule_text = business_rule.get('gstin_rules', '')
        gst_number = data.get('gstNumber')
        if data.get('gstRegistered'):
            if 'required' in gst_rule_text.lower() and not gst_number:
                errors.append({"field": "gstNumber", "message": "GST Number is required.", "rule": gst_rule_text})
            elif gst_number and not re.match(r'^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}$', gst_number):
                 errors.append({"field": "gstNumber", "message": "Invalid GSTIN format.", "rule": gst_rule_text})

        # --- TAN Validation ---
        tan_rule_text = business_rule.get('tan_rules', '')
        tan_number = data.get('tanNumber')
        if data.get('tdsTcsEnabled'):
            if 'required' in tan_rule_text.lower() and not tan_number:
                errors.append({"field": "tanNumber", "message": "TAN Number is required.", "rule": tan_rule_text})
            elif tan_number and not re.match(r'^[A-Z]{4}[0-9]{5}[A-Z]{1}$', tan_number):
                errors.append({"field": "tanNumber", "message": "Invalid TAN format.", "rule": tan_rule_text})

    # Basic required field checks (can also be moved to rules)
    if not data.get('mobileNumber'):
        errors.append({"field": "mobileNumber", "message": "Mobile Number is required."})
    if not data.get('email'):
        errors.append({"field": "email", "message": "E-mail is required."})
    elif not re.match(r"[^@]+@[^@]+\.[^@]+", data['email']):
        errors.append({"field": "email", "message": "A valid E-mail format is required."})

    return errors

@company_info_bp.route('', methods=['GET'])
@jwt_required()
def handle_get_company_info():
    try:
        db = get_db()
        current_tenant = get_tenant_id_from_token()
        if not current_tenant:
            return jsonify({"message": "Tenant ID not found in token"}), 400

        company_info = get_company_information(db_conn=db, tenant_id=current_tenant)

        if company_info and company_info.get('logoBlobName'):
            company_info['logoUrl'] = _generate_sas_url(company_info['logoBlobName'])

        return jsonify(company_info if company_info else {}), 200
    except Exception as e:
        logging.error(f"Error in handle_get_company_info: {e}")
        return jsonify({"message": "Failed to fetch company information", "error": str(e)}), 500

@company_info_bp.route('', methods=['POST', 'PUT'])
@jwt_required()
def handle_save_company_info():
    try:
        db = get_db()
        current_user = get_requesting_user_name()
        current_tenant = get_tenant_id_from_token()
        if not current_tenant:
            return jsonify({"message": "Tenant ID not found in token"}), 400

        data = request.form.to_dict()

        # Handle array of businesses
        if 'businesses' in data and isinstance(data['businesses'], str):
            data['businesses'] = json.loads(data['businesses'])

        # Convert form string 'true'/'false' to boolean
        boolean_fields = [
            'gstRegistered', 'sameAsBilling', 'pfEnabled', 'esicEnabled',
            'iecRegistered', 'tdsTcsEnabled', 'advanceTaxEnabled', 'msmeEnabled', 'vatEnabled'
        ]
        for field in boolean_fields:
            data[field] = str(data.get(field, 'false')).lower() in ['true', 'on', '1']

        # --- FIX: Clear dependent fields if their switches are off ---
        if not data.get('gstRegistered'):
            for key in ['gstNumber', 'gstType', 'gstIsdNumber']: data.pop(key, None)
        if not data.get('tdsTcsEnabled'):
            for key in ['tanNumber', 'tdsTcsFinancialYear']: data.pop(key, None)
        if not data.get('vatEnabled'):
            data.pop('vatNumber', None)
        if not data.get('esicEnabled'):
            data.pop('esicNumber', None)
        if not data.get('pfEnabled'):
            data.pop('pfNumber', None)
        if not data.get('iecRegistered'):
            data.pop('iecNumber', None)
        if not data.get('msmeEnabled'):
            data.pop('msmeNumber', None)
        # --- End of fix ---

        document_rules = get_or_create_rules(db)
        validation_errors = validate_data_with_rules(data, document_rules)
        if validation_errors:
            return jsonify({"message": "Please correct the errors below.", "errors": validation_errors}), 400

        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename and allowed_file(file.filename):
                if not AZURE_CONNECTION_STRING or not AZURE_CONTAINER_NAME:
                    return jsonify({"message": "File upload service is not configured."}), 500

                timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
                secure_base_filename = secure_filename(file.filename)
                blob_name = f"{current_tenant}/company_logos/{timestamp}_{secure_base_filename}"

                blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
                blob_client = blob_service_client.get_blob_client(container=AZURE_CONTAINER_NAME, blob=blob_name)

                file.seek(0)
                blob_client.upload_blob(file.read(), blob_type="BlockBlob")
                data['logoBlobName'] = blob_name
                data.pop('logoUrl', None) # Remove any existing URL to prefer the new blob name
            elif file and file.filename:
                 return jsonify({"message": "File type not allowed."}), 400

        result_doc_id_str = create_or_update_company_information(
            db_conn=db,
            data=data,
            user=current_user,
            tenant_id=current_tenant
        )

        if result_doc_id_str:
            saved_info = get_company_information(db_conn=db, tenant_id=current_tenant)
            if saved_info and saved_info.get('logoBlobName'):
                 saved_info['logoUrl'] = _generate_sas_url(saved_info['logoBlobName'])
            return jsonify({"message": "Company information saved successfully", "data": saved_info or {}}), 200
        else:
            return jsonify({"message": "Failed to save company information or no changes made."}), 400
    except Exception as e:
        logging.exception(f"Error in handle_save_company_info for tenant {get_tenant_id_from_token()}: {e}")
        return jsonify({"message": "An internal error occurred", "error": str(e)}), 500
