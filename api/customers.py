# api/customers.py
from flask import Blueprint, request, jsonify, session, current_app
import logging
from bson import ObjectId # For validating ObjectId in GET by ID
import re # Import regular expression module for search

# Import DAL functions
from db.customer_dal import (
    create_customer,
    get_customer_by_id,
    get_all_customers,
    update_customer,
    delete_customer_by_id
)

# Define the blueprint
customers_bp = Blueprint(
    'customers_bp',
    __name__,
    url_prefix='/api/customers'
)

logging.basicConfig(level=logging.INFO)

def get_current_user():
    return session.get('username', 'System') # Placeholder

@customers_bp.route('', methods=['POST'])
def handle_create_customer():
    """Handles POST requests to create a new customer."""
    data = request.get_json()
    if not data:
        return jsonify({"message": "No input data provided"}), 400
    # Add more specific required field checks based on your CustomerForm
    if not data.get('displayName') or not data.get('financialDetails', {}).get('paymentTerms'):
        return jsonify({"message": "Missing required fields: displayName and paymentTerms"}), 400

    try:
        current_user = get_current_user()
        customer_id = create_customer(data, user=current_user)
        created_customer = get_customer_by_id(str(customer_id))
        if created_customer:
            created_customer['_id'] = str(created_customer['_id'])
            return jsonify({"message": "Customer created successfully", "data": created_customer}), 201
        else:
            return jsonify({"message": "Customer created, but failed to retrieve."}), 201
    except Exception as e:
        logging.error(f"Error in handle_create_customer: {e}")
        return jsonify({"message": "Failed to create customer"}), 500

@customers_bp.route('/<customer_id>', methods=['GET'])
def handle_get_customer(customer_id):
    """Handles GET requests to fetch a single customer by ID."""
    try:
        if not ObjectId.is_valid(customer_id):
            return jsonify({"message": "Invalid customer ID format"}), 400
        
        customer = get_customer_by_id(customer_id)
        if customer:
            customer['_id'] = str(customer['_id'])
            # Convert nested ObjectIds if any, e.g., in primaryContact or financialDetails if they have their own _ids
            if 'primaryContact' in customer and customer['primaryContact'] and '_id' in customer['primaryContact']:
                 customer['primaryContact']['_id'] = str(customer['primaryContact']['_id'])
            # Add more as needed
            return jsonify(customer), 200
        else:
            return jsonify({"message": "Customer not found"}), 404
    except Exception as e:
        logging.error(f"Error in handle_get_customer for ID {customer_id}: {e}")
        return jsonify({"message": "Failed to fetch customer"}), 500

@customers_bp.route('', methods=['GET'])
def handle_get_all_customers():
    """Handles GET requests to fetch all customers with pagination and search."""
    try:
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 25))
        search_term = request.args.get("search", None) # Get search term from query params

        filters = {}
        if search_term:
            # Create a case-insensitive regex search query
            # This will search for the term in displayName, companyName, and primaryContact's email or name
            # Adjust fields as necessary for your search requirements
            regex_query = {"$regex": re.escape(search_term), "$options": "i"}
            filters["$or"] = [
                {"displayName": regex_query},
                {"companyName": regex_query},
                {"primaryContact.email": regex_query},
                {"primaryContact.name": regex_query},
                {"primaryContact.contact": regex_query}, # Search by phone/contact number
                {"gstNo": regex_query},
                {"pan": regex_query}
            ]
        
        # You can add other filters here, e.g., by status or date range
        # date_range_filter = request.args.get("dateRange", None)
        # if date_range_filter == "this_month":
        #     # Add logic to filter by current month
        #     pass

        customer_list, total_items = get_all_customers(page, limit, filters)
        
        result = []
        for item in customer_list:
            item['_id'] = str(item['_id'])
            # Convert nested ObjectIds if any
            if 'primaryContact' in item and item['primaryContact'] and '_id' in item['primaryContact']:
                 item['primaryContact']['_id'] = str(item['primaryContact']['_id'])
            result.append(item)

        return jsonify({
            "data": result,
            "total": total_items,
            "page": page,
            "limit": limit,
            "totalPages": (total_items + limit - 1) // limit if limit > 0 else 0
        }), 200
    except ValueError:
         return jsonify({"message": "Invalid page or limit parameter. Must be integers."}), 400
    except Exception as e:
        logging.error(f"Error in handle_get_all_customers: {e}")
        return jsonify({"message": "Failed to fetch customers"}), 500

@customers_bp.route('/<customer_id>', methods=['PUT'])
def handle_update_customer(customer_id):
    """Handles PUT requests to update an existing customer."""
    data = request.get_json()
    if not data:
        return jsonify({"message": "No input data provided"}), 400
    if not ObjectId.is_valid(customer_id):
        return jsonify({"message": "Invalid customer ID format"}), 400

    try:
        current_user = get_current_user()
        matched_count = update_customer(customer_id, data, user=current_user)
        if matched_count == 0:
            return jsonify({"message": "Customer not found or no changes made"}), 404
        
        updated_customer = get_customer_by_id(customer_id)
        if updated_customer:
            updated_customer['_id'] = str(updated_customer['_id'])
            if 'primaryContact' in updated_customer and updated_customer['primaryContact'] and '_id' in updated_customer['primaryContact']:
                 updated_customer['primaryContact']['_id'] = str(updated_customer['primaryContact']['_id'])
            return jsonify({"message": "Customer updated successfully", "data": updated_customer}), 200
        else:
            return jsonify({"message": "Customer updated, but failed to retrieve updated data."}), 200
    except Exception as e:
        logging.error(f"Error in handle_update_customer for ID {customer_id}: {e}")
        return jsonify({"message": "Failed to update customer"}), 500

@customers_bp.route('/<customer_id>', methods=['DELETE'])
def handle_delete_customer(customer_id):
    """Handles DELETE requests to remove a customer."""
    try:
        if not ObjectId.is_valid(customer_id):
            return jsonify({"message": "Invalid customer ID format"}), 400

        deleted_count = delete_customer_by_id(customer_id)
        if deleted_count == 0:
            return jsonify({"message": "Customer not found"}), 404
        return jsonify({"message": "Customer deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error in handle_delete_customer for ID {customer_id}: {e}")
        return jsonify({"message": "Failed to delete customer"}), 500
