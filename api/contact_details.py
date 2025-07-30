# api/contact_details_api.py
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, get_jwt
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
import os
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions
import logging

from db.contact_details_dal import (
    get_all_contacts,
    add_contact,
    update_contact,
    delete_contact,
    set_default_contact
)
from db.database import get_db

contact_details_bp = Blueprint(
    'contact_details_bp',
    __name__,
    url_prefix='/api/contact-details'
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
# --- End Azure Config ---

def get_tenant_id_from_token():
    claims = get_jwt()
    return claims.get("tenant_id")

def allowed_file(filename):
    allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions

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


@contact_details_bp.route('', methods=['GET'])
@jwt_required()
def handle_get_contacts():
    tenant_id = get_tenant_id_from_token()
    try:
        db = get_db()
        contacts = get_all_contacts(db, tenant_id)
        # Generate SAS URL for each contact's photo
        for contact in contacts:
            if contact.get('photoBlobName'):
                contact['photoUrl'] = _generate_sas_url(contact['photoBlobName'])
        return jsonify(contacts), 200
    except Exception as e:
        logging.error(f"Error fetching contacts for tenant {tenant_id}: {e}")
        return jsonify({"message": "Failed to fetch contacts"}), 500

@contact_details_bp.route('', methods=['POST'])
@jwt_required()
def handle_add_contact():
    tenant_id = get_tenant_id_from_token()
    data = request.form.to_dict()

    if not data or not data.get('name'):
        return jsonify({"message": "Contact name is required"}), 400

    # Handle boolean value from form data
    data['isDefault'] = str(data.get('isDefault', 'false')).lower() == 'true'

    try:
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename and allowed_file(file.filename):
                if not AZURE_CONNECTION_STRING or not AZURE_CONTAINER_NAME:
                    return jsonify({"message": "File upload service is not configured."}), 500

                timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
                # Store contact photos in a subfolder for better organization
                blob_name = f"{tenant_id}/contacts/{timestamp}_{secure_filename(file.filename)}"

                blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
                blob_client = blob_service_client.get_blob_client(container=AZURE_CONTAINER_NAME, blob=blob_name)

                file.seek(0)
                blob_client.upload_blob(file.read(), blob_type="BlockBlob")
                data['photoBlobName'] = blob_name
            elif file and file.filename:
                return jsonify({"message": "File type not allowed."}), 400

        db = get_db()
        contact_id = add_contact(db, tenant_id, data)
        return jsonify({"message": "Contact added successfully", "id": contact_id}), 201
    except Exception as e:
        logging.error(f"Error adding contact for tenant {tenant_id}: {e}")
        return jsonify({"message": "Failed to add contact"}), 500

@contact_details_bp.route('/<contact_id>', methods=['PUT'])
@jwt_required()
def handle_update_contact(contact_id):
    tenant_id = get_tenant_id_from_token()
    data = request.form.to_dict()
    data['isDefault'] = str(data.get('isDefault', 'false')).lower() == 'true'

    # FIX: Remove the immutable '_id' field before updating.
    data.pop('_id', None)

    try:
        if 'photo' in request.files:
            file = request.files['photo']
            if file and file.filename and allowed_file(file.filename):
                if not AZURE_CONNECTION_STRING or not AZURE_CONTAINER_NAME:
                    return jsonify({"message": "File upload service is not configured."}), 500

                timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S')
                # Organize blobs by tenant and contact for easier management
                blob_name = f"{tenant_id}/contacts/{contact_id}/{timestamp}_{secure_filename(file.filename)}"

                blob_service_client = BlobServiceClient.from_connection_string(AZURE_CONNECTION_STRING)
                blob_client = blob_service_client.get_blob_client(container=AZURE_CONTAINER_NAME, blob=blob_name)

                file.seek(0)
                blob_client.upload_blob(file.read(), blob_type="BlockBlob")
                data['photoBlobName'] = blob_name
            elif file and file.filename:
                return jsonify({"message": "File type not allowed."}), 400

        db = get_db()
        success = update_contact(db, tenant_id, contact_id, data)
        if success:
            return jsonify({"message": "Contact updated successfully"}), 200
        return jsonify({"message": "Contact not found or no changes made"}), 404
    except Exception as e:
        logging.error(f"Error updating contact {contact_id} for tenant {tenant_id}: {e}")
        return jsonify({"message": "Failed to update contact"}), 500

@contact_details_bp.route('/<contact_id>', methods=['DELETE'])
@jwt_required()
def handle_delete_contact(contact_id):
    tenant_id = get_tenant_id_from_token()
    try:
        db = get_db()
        # You might want to add logic here to delete the photo from blob storage as well
        success = delete_contact(db, tenant_id, contact_id)
        if success:
            return jsonify({"message": "Contact deleted successfully"}), 200
        return jsonify({"message": "Contact not found"}), 404
    except Exception as e:
        logging.error(f"Error deleting contact {contact_id} for tenant {tenant_id}: {e}")
        return jsonify({"message": "Failed to delete contact"}), 500

@contact_details_bp.route('/set-default/<contact_id>', methods=['PUT'])
@jwt_required()
def handle_set_default(contact_id):
    tenant_id = get_tenant_id_from_token()
    try:
        db = get_db()
        success = set_default_contact(db, tenant_id, contact_id)
        if success:
            return jsonify({"message": "Default contact set successfully"}), 200
        return jsonify({"message": "Contact not found"}), 404
    except Exception as e:
        logging.error(f"Error setting default contact for tenant {tenant_id}: {e}")
        return jsonify({"message": "Failed to set default contact"}), 500
