# api/staff.py
from flask import Blueprint, request, jsonify, session, current_app
import logging
from bson import ObjectId
import re

from db.staff_dal import (
    create_staff_member,
    get_staff_member_by_id,
    get_all_staff_members,
    update_staff_member,
    delete_staff_member_by_id
)

staff_bp = Blueprint(
    'staff_bp',
    __name__,
    url_prefix='/api/staff'
)

logging.basicConfig(level=logging.INFO)

def get_current_user():
    return session.get('username', 'System')

@staff_bp.route('', methods=['POST'])
def handle_create_staff_member():
    data = request.get_json()
    if not data:
        return jsonify({"message": "No input data provided"}), 400
    if not data.get('firstName') or not data.get('lastName'): # Based on form design
        return jsonify({"message": "Missing required fields: firstName and lastName"}), 400

    try:
        current_user = get_current_user()
        staff_id = create_staff_member(data, user=current_user)
        created_staff = get_staff_member_by_id(str(staff_id))
        if created_staff:
            created_staff['_id'] = str(created_staff['_id'])
            return jsonify({"message": "Staff member created successfully", "data": created_staff}), 201
        else:
            return jsonify({"message": "Staff member created, but failed to retrieve."}), 201
    except Exception as e:
        logging.error(f"Error in handle_create_staff_member: {e}")
        return jsonify({"message": "Failed to create staff member"}), 500

@staff_bp.route('/<staff_id>', methods=['GET'])
def handle_get_staff_member(staff_id):
    try:
        if not ObjectId.is_valid(staff_id):
            return jsonify({"message": "Invalid staff ID format"}), 400
        
        staff_member = get_staff_member_by_id(staff_id)
        if staff_member:
            staff_member['_id'] = str(staff_member['_id'])
            return jsonify(staff_member), 200
        else:
            return jsonify({"message": "Staff member not found"}), 404
    except Exception as e:
        logging.error(f"Error fetching staff member {staff_id}: {e}")
        return jsonify({"message": "Failed to fetch staff member"}), 500

@staff_bp.route('', methods=['GET'])
def handle_get_all_staff():
    try:
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 25))
        search_term = request.args.get("search", None)

        filters = {}
        if search_term:
            regex_query = {"$regex": re.escape(search_term), "$options": "i"}
            filters["$or"] = [
                {"firstName": regex_query},
                {"lastName": regex_query},
                {"email": regex_query},
                {"employeeId": regex_query},
                {"mobile": regex_query}
            ]
        
        staff_list, total_items = get_all_staff_members(page, limit, filters)
        
        result = []
        for item in staff_list:
            item['_id'] = str(item['_id'])
            result.append(item)

        return jsonify({
            "data": result,
            "total": total_items,
            "page": page,
            "limit": limit,
            "totalPages": (total_items + limit - 1) // limit if limit > 0 else 0
        }), 200
    except ValueError:
         return jsonify({"message": "Invalid page or limit parameter."}), 400
    except Exception as e:
        logging.error(f"Error fetching all staff: {e}")
        return jsonify({"message": "Failed to fetch staff members"}), 500

@staff_bp.route('/<staff_id>', methods=['PUT'])
def handle_update_staff_member(staff_id):
    data = request.get_json()
    if not data:
        return jsonify({"message": "No input data provided"}), 400
    if not ObjectId.is_valid(staff_id):
        return jsonify({"message": "Invalid staff ID format"}), 400

    try:
        current_user = get_current_user()
        matched_count = update_staff_member(staff_id, data, user=current_user)
        if matched_count == 0:
            return jsonify({"message": "Staff member not found or no changes made"}), 404
        
        updated_staff = get_staff_member_by_id(staff_id)
        if updated_staff:
            updated_staff['_id'] = str(updated_staff['_id'])
            return jsonify({"message": "Staff member updated successfully", "data": updated_staff}), 200
        else:
            return jsonify({"message": "Staff member updated, but failed to retrieve."}), 200
    except Exception as e:
        logging.error(f"Error updating staff member {staff_id}: {e}")
        return jsonify({"message": "Failed to update staff member"}), 500

@staff_bp.route('/<staff_id>', methods=['DELETE'])
def handle_delete_staff_member(staff_id):
    try:
        if not ObjectId.is_valid(staff_id):
            return jsonify({"message": "Invalid staff ID format"}), 400

        deleted_count = delete_staff_member_by_id(staff_id)
        if deleted_count == 0:
            return jsonify({"message": "Staff member not found"}), 404
        return jsonify({"message": "Staff member deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error deleting staff member {staff_id}: {e}")
        return jsonify({"message": "Failed to delete staff member"}), 500

