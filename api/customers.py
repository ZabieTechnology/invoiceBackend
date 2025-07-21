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
    Handles POST requests to create a new customer.
    Intelligently handles both minimal JSON requests (from invoice page)
    and full multipart/form-data requests (from customer form).
    """
    current_user = get_current_user()
    current_tenant = get_current_tenant_id()
    db = get_db()

    try:
        # Case 1: Minimal customer creation from invoice page (expects JSON)
        if request.is_json:
            data = request.json
            display_name = data.get('displayName')
            payment_terms = data.get('paymentTerms', 'Due on Receipt')

            if not display_name:
                return jsonify({"message": "Missing required field: displayName"}), 400

            created_customer = create_customer_minimal(
                db_conn=db,
                display_name=display_name,
                payment_terms=payment_terms,
                user=current_user,
                tenant_id=current_tenant
            )
            return jsonify({"message": "Customer created successfully", "data": created_customer}), 201

        # Case 2: Full customer creation from dedicated form (expects form-data)
        elif request.form:
            data = parse_form_data(request.form.to_dict())

            payment_terms_from_form = data.get('financialDetails', {}).get('paymentTerms')

            if not data.get('displayName') or not payment_terms_from_form:
                 return jsonify({"message": "Missing required fields: displayName and paymentTerms"}), 400

            data['paymentTerms'] = payment_terms_from_form

            base_upload_folder = current_app.config.get('UPLOAD_FOLDER')
            if not base_upload_folder:
                logging.error("UPLOAD_FOLDER is not configured in the Flask app.")
                return jsonify({"message": "File upload configuration error on server."}), 500

            logos_upload_path = os.path.join(base_upload_folder, 'logos')
            if not os.path.exists(logos_upload_path):
                os.makedirs(logos_upload_path, exist_ok=True)

            if 'logo' in request.files:
                file = request.files['logo']
                if file and file.filename and allowed_file(file.filename):
                    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
                    secure_base_filename = secure_filename(file.filename)
                    filename = f"{current_tenant}_{timestamp}_{secure_base_filename}"
                    file.save(os.path.join(logos_upload_path, filename))
                    data['logoFilename'] = filename
                elif file and file.filename:
                    allowed_types_str = ', '.join(current_app.config.get('ALLOWED_EXTENSIONS', []))
                    return jsonify({"message": f"File type not allowed. Allowed types: {allowed_types_str}"}), 400

            # UPDATED: The create_customer function returns the full document.
            # No need to fetch it again.
            created_customer = create_customer(db, data, user=current_user, tenant_id=current_tenant)

            if created_customer:
                if created_customer.get('logoFilename'):
                    created_customer['logoUrl'] = f"/uploads/logos/{created_customer['logoFilename']}"
                return jsonify({"message": "Customer created successfully", "data": created_customer}), 201
            else:
                return jsonify({"message": "Customer created, but failed to retrieve."}), 500

        # If neither JSON nor form data is present
        else:
            return jsonify({"message": "Unsupported request format. Expecting JSON or form-data."}), 415

    except ValueError as ve:
        logging.warning(f"ValueError in handle_create_customer: {ve}")
        return jsonify({"message": str(ve)}), 409
    except Exception as e:
        logging.error(f"Error in handle_create_customer: {e}")
        return jsonify({"message": "Failed to create customer", "error": str(e)}), 500


@customers_bp.route('/<customer_id>', methods=['PUT'])
def handle_update_customer(customer_id):
    """Handles PUT requests to update an existing customer. Expects multipart/form-data."""
    if not ObjectId.is_valid(customer_id):
        return jsonify({"message": "Invalid customer ID format"}), 400
    if not request.form:
        return jsonify({"message": "No form data provided for update"}), 400

    data = parse_form_data(request.form.to_dict())

    try:
        current_user = get_current_user()
        current_tenant = get_current_tenant_id()
        db = get_db()

        payment_terms_from_form = data.get('financialDetails', {}).get('paymentTerms')
        if payment_terms_from_form:
            data['paymentTerms'] = payment_terms_from_form

        base_upload_folder = current_app.config.get('UPLOAD_FOLDER')
        if not base_upload_folder:
            return jsonify({"message": "File upload configuration error on server."}), 500
        logos_upload_path = os.path.join(base_upload_folder, 'logos')
        os.makedirs(logos_upload_path, exist_ok=True)

        if 'logo' in request.files:
            file = request.files['logo']
            if file and file.filename and allowed_file(file.filename):
                timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
                filename = f"{current_tenant}_{timestamp}_{secure_filename(file.filename)}"
                file.save(os.path.join(logos_upload_path, filename))
                data['logoFilename'] = filename
            elif file and file.filename:
                 allowed_types_str = ', '.join(current_app.config.get('ALLOWED_EXTENSIONS', []))
                 return jsonify({"message": f"File type not allowed. Allowed types: {allowed_types_str}"}), 400

        matched_count = update_customer(db, customer_id, data, user=current_user, tenant_id=current_tenant)
        if matched_count == 0:
            return jsonify({"message": "Customer not found or no changes made"}), 404

        updated_customer = get_customer_by_id(db, customer_id, tenant_id=current_tenant)
        if updated_customer:
            if updated_customer.get('logoFilename'):
                updated_customer['logoUrl'] = f"/uploads/logos/{updated_customer['logoFilename']}"
            return jsonify({"message": "Customer updated successfully", "data": updated_customer}), 200
        else:
            return jsonify({"message": "Customer updated, but failed to retrieve updated data."}), 500
    except ValueError as ve:
        return jsonify({"message": str(ve)}), 409
    except Exception as e:
        return jsonify({"message": "Failed to update customer", "error": str(e)}), 500

@customers_bp.route('/<customer_id>', methods=['GET'])
def handle_get_customer(customer_id):
    try:
        if not ObjectId.is_valid(customer_id):
            return jsonify({"message": "Invalid customer ID format"}), 400

        db = get_db()
        customer = get_customer_by_id(db, customer_id, tenant_id=get_current_tenant_id())
        if customer:
            if customer.get('logoFilename'):
                 customer['logoUrl'] = f"/uploads/logos/{customer['logoFilename']}"
            return jsonify(customer), 200
        else:
            return jsonify({"message": "Customer not found"}), 404
    except Exception as e:
        return jsonify({"message": "Failed to fetch customer", "error": str(e)}), 500

@customers_bp.route('', methods=['GET'])
def handle_get_all_customers():
    try:
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 25))
        search_term = request.args.get("search", None)

        db = get_db()
        filters = {}
        if search_term:
            regex_query = {"$regex": re.escape(search_term), "$options": "i"}
            filters["$or"] = [
                {"displayName": regex_query}, {"companyName": regex_query},
                {"primaryContact.email": regex_query}, {"primaryContact.mobile": regex_query}
            ]

        customer_list, total_items = get_all_customers(db, page, limit, filters, tenant_id=get_current_tenant_id())

        for item in customer_list:
            if item.get('logoFilename'):
                 item['logoUrl'] = f"/uploads/logos/{item['logoFilename']}"

        return jsonify({
            "data": customer_list, "total": total_items, "page": page,
            "limit": limit if limit > 0 else total_items,
            "totalPages": (total_items + limit - 1) // limit if limit > 0 else 1
        }), 200
    except ValueError:
         return jsonify({"message": "Invalid page or limit parameter."}), 400
    except Exception as e:
        return jsonify({"message": "Failed to fetch customers", "error": str(e)}), 500

@customers_bp.route('/<customer_id>', methods=['DELETE'])
def handle_delete_customer(customer_id):
    try:
        if not ObjectId.is_valid(customer_id):
            return jsonify({"message": "Invalid customer ID format"}), 400

        db = get_db()
        deleted_count = delete_customer_by_id(db, customer_id, user=get_current_user(), tenant_id=get_current_tenant_id())
        if deleted_count == 0:
            return jsonify({"message": "Customer not found"}), 404
        return jsonify({"message": "Customer deleted successfully"}), 200
    except Exception as e:
        return jsonify({"message": "Failed to delete customer", "error": str(e)}), 500
