# api/customers.py
from flask import Blueprint, request, jsonify, session, current_app
import logging
from bson import ObjectId
import re
import json # For parsing JSON strings from FormData
import os
from werkzeug.utils import secure_filename
from datetime import datetime


# Import DAL functions and db utility
from db.customer_dal import (
    create_customer_minimal,
    create_customer,
    get_customer_by_id,
    get_all_customers,
    update_customer,
    delete_customer_by_id
)
from db.database import get_db

customers_bp = Blueprint(
    'customers_bp',
    __name__,
    url_prefix='/api/customers'
)

logging.basicConfig(level=logging.INFO)

def get_current_user():
    return session.get('username', 'System_User_Placeholder')

def get_current_tenant_id():
    return session.get('tenant_id', 'default_tenant_placeholder')

def allowed_file(filename):
    allowed_extensions = current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif', 'svg'})
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in allowed_extensions

def parse_form_data(form_data_dict):
    """ Parses stringified JSON and boolean fields from FormData """
    parsed_data = {}
    boolean_fields = [
        'gstRegistered', 'sameAsBilling', 'pfEnabled', 'esicEnabled',
        'iecRegistered', 'tdsEnabled', 'tcsEnabled', 'advanceTaxEnabled'
    ]
    # Fields that frontend stringifies because they are objects
    json_fields = ['primaryContact', 'financialDetails', 'billingAddress', 'shippingAddress']

    for key, value in form_data_dict.items():
        if key in boolean_fields:
            parsed_data[key] = str(value).lower() == 'true'
        elif key in json_fields:
            try:
                parsed_data[key] = json.loads(value)
            except json.JSONDecodeError:
                logging.warning(f"Could not parse JSON for field {key}: {value}")
                parsed_data[key] = {} # Default to empty dict if parse fails
        else:
            parsed_data[key] = value
    return parsed_data


@customers_bp.route('', methods=['POST'])
def handle_create_customer():
    """
    Handles POST requests to create a new customer from the full CustomerForm.js.
    Expects multipart/form-data.
    """
    if not request.form:
        return jsonify({"message": "No form data provided"}), 400

    data = parse_form_data(request.form.to_dict())

    if not data.get('displayName') or not data.get('financialDetails', {}).get('paymentTerms'):
        logging.warning(f"Create customer attempt failed due to missing fields. displayName or paymentTerms. Data: {data}")
        return jsonify({"message": "Missing required fields: displayName and paymentTerms"}), 400

    try:
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()
        db = get_db()
        logo_filename = None

        base_upload_folder = current_app.config.get('UPLOAD_FOLDER')
        if not base_upload_folder:
            logging.error("UPLOAD_FOLDER is not configured in the Flask app.")
            return jsonify({"message": "File upload configuration error on server."}), 500

        logos_upload_path = os.path.join(base_upload_folder, 'logos')
        if not os.path.exists(logos_upload_path):
            try:
                os.makedirs(logos_upload_path)
            except OSError as e_dir:
                logging.error(f"Could not create logos upload folder {logos_upload_path}: {e_dir}")
                return jsonify({"message": "File upload path error on server."}), 500

        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename and allowed_file(file.filename):
                timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
                secure_base_filename = secure_filename(file.filename)
                filename = f"{current_tenant}_{timestamp}_{secure_base_filename}"
                file_path = os.path.join(logos_upload_path, filename)
                file.save(file_path)
                data['logoFilename'] = filename
            elif file and file.filename:
                 allowed_types_str = ', '.join(current_app.config.get('ALLOWED_EXTENSIONS', []))
                 return jsonify({"message": f"File type not allowed. Allowed types: {allowed_types_str}"}), 400

        # Use create_customer for full form data
        customer_id = create_customer(
            db_conn=db,
            customer_data=data,
            user=current_user,
            tenant_id=current_tenant
        )

        created_customer = get_customer_by_id(db, str(customer_id), tenant_id=current_tenant)
        if created_customer:
            created_customer['_id'] = str(created_customer['_id'])
            if created_customer.get('logoFilename'): # Construct URL for response
                created_customer['logoUrl'] = f"/uploads/logos/{created_customer['logoFilename']}"
            return jsonify({"message": "Customer created successfully", "data": created_customer}), 201
        else:
            logging.error(f"Customer created with ID {customer_id}, but failed to retrieve for response.")
            return jsonify({"message": "Customer created, but failed to retrieve."}), 500
    except ValueError as ve:
        logging.warning(f"ValueError in handle_create_customer: {ve}")
        return jsonify({"message": str(ve)}), 409
    except Exception as e:
        logging.error(f"Error in handle_create_customer: {e}")
        current_app.logger.error(f"Error details in handle_create_customer: {str(e)}. Form Data Keys: {list(request.form.keys())}")
        return jsonify({"message": "Failed to create customer", "error": str(e)}), 500

@customers_bp.route('/<customer_id>', methods=['PUT'])
def handle_update_customer(customer_id):
    """Handles PUT requests to update an existing customer. Expects multipart/form-data."""
    if not request.form:
        return jsonify({"message": "No form data provided for update"}), 400
    if not ObjectId.is_valid(customer_id):
        return jsonify({"message": "Invalid customer ID format"}), 400

    data = parse_form_data(request.form.to_dict())

    try:
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()
        db = get_db()
        logo_filename = None

        base_upload_folder = current_app.config.get('UPLOAD_FOLDER')
        if not base_upload_folder:
            logging.error("UPLOAD_FOLDER is not configured in the Flask app.")
            return jsonify({"message": "File upload configuration error on server."}), 500

        logos_upload_path = os.path.join(base_upload_folder, 'logos')
        if not os.path.exists(logos_upload_path):
            try:
                os.makedirs(logos_upload_path)
            except OSError as e_dir:
                logging.error(f"Could not create logos upload folder {logos_upload_path}: {e_dir}")
                return jsonify({"message": "File upload path error on server."}), 500

        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename and allowed_file(file.filename):
                timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
                secure_base_filename = secure_filename(file.filename)
                filename = f"{current_tenant}_{timestamp}_{secure_base_filename}"
                file_path = os.path.join(logos_upload_path, filename)
                file.save(file_path)
                data['logoFilename'] = filename
                # TODO: Consider deleting the old logo file if replacing
            elif file and file.filename:
                 allowed_types_str = ', '.join(current_app.config.get('ALLOWED_EXTENSIONS', []))
                 return jsonify({"message": f"File type not allowed. Allowed types: {allowed_types_str}"}), 400

        # If logoFilename is explicitly sent as empty, it means user wants to remove logo
        if 'logoFilename' in data and not data['logoFilename']:
            # TODO: Add logic to delete the actual file from server if this means removal
            data['logoFilename'] = None # Ensure it's stored as null or removed from DB field

        matched_count = update_customer(db, customer_id, data, user=current_user, tenant_id=current_tenant)
        if matched_count == 0:
            return jsonify({"message": "Customer not found or no changes made"}), 404

        updated_customer = get_customer_by_id(db, customer_id, tenant_id=current_tenant)
        if updated_customer:
            updated_customer['_id'] = str(updated_customer['_id'])
            if updated_customer.get('logoFilename'): # Construct URL for response
                updated_customer['logoUrl'] = f"/uploads/logos/{updated_customer['logoFilename']}"
            return jsonify({"message": "Customer updated successfully", "data": updated_customer}), 200
        else:
            logging.error(f"CRITICAL: Customer {customer_id} updated (matched_count: {matched_count}), but failed to retrieve.")
            return jsonify({"message": "Customer updated, but failed to retrieve updated data."}), 500
    except ValueError as ve:
        logging.warning(f"ValueError in handle_update_customer for ID {customer_id}: {ve}")
        return jsonify({"message": str(ve)}), 409
    except Exception as e:
        logging.error(f"Error in handle_update_customer for ID {customer_id}: {e}")
        current_app.logger.error(f"Error details in handle_update_customer: {str(e)}. Form Data Keys: {list(request.form.keys())}")
        return jsonify({"message": "Failed to update customer", "error": str(e)}), 500

@customers_bp.route('/<customer_id>', methods=['GET'])
def handle_get_customer(customer_id):
    try:
        if not ObjectId.is_valid(customer_id):
            return jsonify({"message": "Invalid customer ID format"}), 400

        current_tenant = get_current_tenant_id()
        db = get_db()
        customer = get_customer_by_id(db, customer_id, tenant_id=current_tenant)
        if customer:
            customer['_id'] = str(customer['_id'])
            if customer.get('primaryContact') and customer['primaryContact'].get('_id') and isinstance(customer['primaryContact']['_id'], ObjectId):
                 customer['primaryContact']['_id'] = str(customer['primaryContact']['_id'])
            if customer.get('logoFilename'):
                 customer['logoUrl'] = f"/uploads/logos/{customer['logoFilename']}"
            return jsonify(customer), 200
        else:
            return jsonify({"message": "Customer not found"}), 404
    except Exception as e:
        logging.error(f"Error in handle_get_customer for ID {customer_id}: {e}")
        current_app.logger.error(f"Error details in handle_get_customer for ID {customer_id}: {str(e)}")
        return jsonify({"message": "Failed to fetch customer", "error": str(e)}), 500

@customers_bp.route('', methods=['GET'])
def handle_get_all_customers():
    try:
        page_str = request.args.get("page", "1")
        limit_str = request.args.get("limit", "25")

        page = int(page_str) if page_str.isdigit() else 1
        limit = int(limit_str) if limit_str.isdigit() else 25

        if limit == -1:
            pass
        elif limit < 1:
            limit = 1
        if limit > 200 and limit != -1 :
            limit = 200

        search_term = request.args.get("search", None)
        current_tenant = get_current_tenant_id()
        db = get_db()

        filters = {}
        if search_term:
            regex_query = {"$regex": re.escape(search_term), "$options": "i"}
            filters["$or"] = [
                {"displayName": regex_query}, {"companyName": regex_query},
                {"primaryContact.email": regex_query}, {"primaryContact.name": regex_query},
                {"primaryContact.mobile": regex_query}, {"gstNo": regex_query},
            ]

        customer_list, total_items = get_all_customers(db, page, limit, filters, tenant_id=current_tenant)

        result = []
        for item in customer_list:
            item['_id'] = str(item['_id'])
            if item.get('primaryContact') and item['primaryContact'].get('_id') and isinstance(item['primaryContact']['_id'], ObjectId):
                 item['primaryContact']['_id'] = str(item['primaryContact']['_id'])
            if item.get('logoFilename'): # Add logoUrl for list view as well
                 item['logoUrl'] = f"/uploads/logos/{item['logoFilename']}"
            result.append(item)

        actual_limit_for_response = limit if limit > 0 else total_items
        total_pages = 0
        if total_items > 0:
            if limit == -1:
                total_pages = 1
            elif limit > 0:
                total_pages = (total_items + limit - 1) // limit

        response_data = {
            "data": result, "total": total_items,
            "page": page if limit != -1 else 1,
            "limit": actual_limit_for_response,
            "totalPages": total_pages
        }
        return jsonify(response_data), 200
    except ValueError:
         return jsonify({"message": "Invalid page or limit parameter. Must be integers."}), 400
    except Exception as e:
        logging.error(f"Error in handle_get_all_customers: {e}")
        current_app.logger.error(f"Error details in handle_get_all_customers: {str(e)}")
        return jsonify({"message": "Failed to fetch customers", "error": str(e)}), 500


@customers_bp.route('/<customer_id>', methods=['DELETE'])
def handle_delete_customer(customer_id):
    try:
        if not ObjectId.is_valid(customer_id):
            return jsonify({"message": "Invalid customer ID format"}), 400

        current_user = get_current_user()
        current_tenant = get_current_tenant_id()
        db = get_db()

        # TODO: Optionally, fetch customer to get logoFilename to delete the logo file from server
        # customer_doc = get_customer_by_id(db, customer_id, tenant_id=current_tenant)
        # if customer_doc and customer_doc.get('logoFilename'):
        #     old_logo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'logos', customer_doc['logoFilename'])
        #     if os.path.exists(old_logo_path):
        #         os.remove(old_logo_path)
        #         logging.info(f"Deleted old logo file: {old_logo_path}")

        deleted_count = delete_customer_by_id(db, customer_id, user=current_user, tenant_id=current_tenant)
        if deleted_count == 0:
            return jsonify({"message": "Customer not found"}), 404
        return jsonify({"message": "Customer deleted successfully"}), 200
    except ValueError as ve:
        logging.warning(f"ValueError in handle_delete_customer for ID {customer_id}: {ve}")
        return jsonify({"message": str(ve)}), 400
    except Exception as e:
        logging.error(f"Error in handle_delete_customer for ID {customer_id}: {e}")
        current_app.logger.error(f"Error details in handle_delete_customer: {str(e)}")
        return jsonify({"message": "Failed to delete customer", "error": str(e)}), 500

# This route was duplicated in the user's provided code. Ensuring it's unique.
# If you intend to have a separate GET for a single item by ID, it's fine.
# If it was meant to be part of the main GET /api/customers with an optional ID, that's a different pattern.
@customers_bp.route('/item/<item_id>', methods=['GET'])
def handle_get_single_customer_item(item_id):
    try:
        if not ObjectId.is_valid(item_id):
            return jsonify({"message": "Invalid customer ID format"}), 400

        db = get_db()
        current_tenant = get_current_tenant_id()
        item = get_customer_by_id(db_conn=db, customer_id=item_id, tenant_id=current_tenant)

        if item:
            item['_id'] = str(item['_id'])
            if item.get('logoFilename'):
                 item['logoUrl'] = f"/uploads/logos/{item['logoFilename']}"
            return jsonify(item), 200
        else:
            return jsonify({"message": "Customer not found"}), 404
    except ValueError:
        return jsonify({"message": "Invalid customer ID format"}), 400
    except Exception as e:
        logging.error(f"Error in handle_get_single_customer_item for ID {item_id}: {e}")
        current_app.logger.error(f"Error details in handle_get_single_customer_item: {str(e)}")
        return jsonify({"message": "Failed to fetch customer", "error": str(e)}), 500

