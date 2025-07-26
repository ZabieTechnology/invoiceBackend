# api/account_classification.py
from flask import Blueprint, request, jsonify, session
import logging

from db.account_classification_dal import (
    get_classifications,
    add_nature, add_main_head, add_category, add_option,
    delete_nature, delete_main_head, delete_category, delete_option,
    edit_nature, edit_main_head, edit_category, edit_option,
    update_lock_status
)
from db.database import get_db

classification_bp = Blueprint(
    'classification_bp',
    __name__,
    url_prefix='/api/account-classifications'
)

logging.basicConfig(level=logging.INFO)

# Helper functions to get user and tenant from session
def get_current_user():
    return session.get('username', 'System')

def get_current_tenant_id():
    return session.get('tenant_id', 'default_tenant')

@classification_bp.route('', methods=['GET'])
def handle_get_classifications():
    """Fetches all account classification structures."""
    try:
        classifications = get_classifications(get_db(), tenant_id=get_current_tenant_id())
        return jsonify(classifications), 200
    except Exception as e:
        logging.error(f"Error in handle_get_classifications: {e}")
        return jsonify({"message": "Failed to fetch classifications", "error": str(e)}), 500

# --- POST (ADD) Routes ---
@classification_bp.route('/nature', methods=['POST'])
def handle_add_nature():
    data = request.get_json()
    if not data or not data.get('name'):
        return jsonify({"message": "Nature name is required"}), 400
    try:
        new_id = add_nature(get_db(), data['name'], user=get_current_user(), tenant_id=get_current_tenant_id())
        return jsonify({"message": "Nature added successfully", "id": str(new_id)}), 201
    except ValueError as ve:
        return jsonify({"message": str(ve)}), 409 # Conflict
    except Exception as e:
        logging.error(f"Error in handle_add_nature: {e}")
        return jsonify({"message": "Failed to add nature", "error": str(e)}), 500

@classification_bp.route('/main-head', methods=['POST'])
def handle_add_main_head():
    data = request.get_json()
    if not data or not data.get('nature') or not data.get('name'):
        return jsonify({"message": "Nature and main head name are required"}), 400
    try:
        success = add_main_head(get_db(), data['nature'], data['name'], user=get_current_user(), tenant_id=get_current_tenant_id())
        return jsonify({"message": "Main head added successfully" if success else "No changes were made."}), 200
    except ValueError as ve:
        return jsonify({"message": str(ve)}), 404
    except Exception as e:
        logging.error(f"Error in handle_add_main_head: {e}")
        return jsonify({"message": "Failed to add main head", "error": str(e)}), 500

@classification_bp.route('/category', methods=['POST'])
def handle_add_category():
    data = request.get_json()
    if not data or not data.get('nature') or not data.get('mainHead') or not data.get('name'):
        return jsonify({"message": "Nature, main head, and category name are required"}), 400
    try:
        success = add_category(get_db(), data['nature'], data['mainHead'], data['name'], user=get_current_user(), tenant_id=get_current_tenant_id())
        return jsonify({"message": "Category added successfully" if success else "No changes were made."}), 200
    except ValueError as ve:
        return jsonify({"message": str(ve)}), 404
    except Exception as e:
        logging.error(f"Error in handle_add_category: {e}")
        return jsonify({"message": "Failed to add category", "error": str(e)}), 500

@classification_bp.route('/option', methods=['POST'])
def handle_add_option():
    data = request.get_json()
    if not data or not data.get('nature') or not data.get('mainHead') or not data.get('category') or not data.get('name'):
        return jsonify({"message": "All path fields and option name are required"}), 400
    try:
        success = add_option(get_db(), data['nature'], data['mainHead'], data['category'], data['name'], user=get_current_user(), tenant_id=get_current_tenant_id())
        return jsonify({"message": "Option added successfully" if success else "No changes were made."}), 200
    except ValueError as ve:
        return jsonify({"message": str(ve)}), 404
    except Exception as e:
        logging.error(f"Error in handle_add_option: {e}")
        return jsonify({"message": "Failed to add option", "error": str(e)}), 500

# --- DELETE Routes ---
@classification_bp.route('/nature/<name>', methods=['DELETE'])
def handle_delete_nature(name):
    try:
        success = delete_nature(get_db(), name, user=get_current_user(), tenant_id=get_current_tenant_id())
        if not success: return jsonify({"message": "Nature not found"}), 404
        return jsonify({"message": "Nature deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error in handle_delete_nature: {e}")
        return jsonify({"message": "Failed to delete nature", "error": str(e)}), 500

@classification_bp.route('/main-head', methods=['DELETE'])
def handle_delete_main_head():
    data = request.get_json()
    if not data or not data.get('nature') or not data.get('name'):
        return jsonify({"message": "Nature and main head name are required"}), 400
    try:
        success = delete_main_head(get_db(), data['nature'], data['name'], user=get_current_user(), tenant_id=get_current_tenant_id())
        if not success: return jsonify({"message": "Main head not found"}), 404
        return jsonify({"message": "Main head deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error in handle_delete_main_head: {e}")
        return jsonify({"message": "Failed to delete main head", "error": str(e)}), 500

@classification_bp.route('/category', methods=['DELETE'])
def handle_delete_category():
    data = request.get_json()
    if not data or not data.get('nature') or not data.get('mainHead') or not data.get('name'):
        return jsonify({"message": "Nature, main head, and category name are required"}), 400
    try:
        success = delete_category(get_db(), data['nature'], data['mainHead'], data['name'], user=get_current_user(), tenant_id=get_current_tenant_id())
        if not success: return jsonify({"message": "Category not found"}), 404
        return jsonify({"message": "Category deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error in handle_delete_category: {e}")
        return jsonify({"message": "Failed to delete category", "error": str(e)}), 500

@classification_bp.route('/option', methods=['DELETE'])
def handle_delete_option():
    data = request.get_json()
    if not data or not data.get('nature') or not data.get('mainHead') or not data.get('category') or not data.get('name'):
        return jsonify({"message": "All path fields and option name are required"}), 400
    try:
        success = delete_option(get_db(), data['nature'], data['mainHead'], data['category'], data['name'], user=get_current_user(), tenant_id=get_current_tenant_id())
        if not success: return jsonify({"message": "Option not found"}), 404
        return jsonify({"message": "Option deleted successfully"}), 200
    except Exception as e:
        logging.error(f"Error in handle_delete_option: {e}")
        return jsonify({"message": "Failed to delete option", "error": str(e)}), 500

# --- PUT (EDIT) Routes ---
@classification_bp.route('/nature', methods=['PUT'])
def handle_edit_nature():
    data = request.get_json()
    if not data or not data.get('oldName') or not data.get('newName'):
        return jsonify({"message": "Old and new nature names are required"}), 400
    try:
        success = edit_nature(get_db(), data['oldName'], data['newName'], user=get_current_user(), tenant_id=get_current_tenant_id())
        if not success: return jsonify({"message": "Nature not found"}), 404
        return jsonify({"message": "Nature updated successfully"}), 200
    except Exception as e:
        logging.error(f"Error in handle_edit_nature: {e}")
        return jsonify({"message": "Failed to update nature", "error": str(e)}), 500

@classification_bp.route('/main-head', methods=['PUT'])
def handle_edit_main_head():
    data = request.get_json()
    if not all(k in data for k in ['nature', 'oldName', 'newName']):
        return jsonify({"message": "Nature, old name, and new name are required"}), 400
    try:
        success = edit_main_head(get_db(), data['nature'], data['oldName'], data['newName'], user=get_current_user(), tenant_id=get_current_tenant_id())
        if not success: return jsonify({"message": "Main head not found"}), 404
        return jsonify({"message": "Main head updated successfully"}), 200
    except Exception as e:
        logging.error(f"Error in handle_edit_main_head: {e}")
        return jsonify({"message": "Failed to update main head", "error": str(e)}), 500

@classification_bp.route('/category', methods=['PUT'])
def handle_edit_category():
    data = request.get_json()
    if not all(k in data for k in ['nature', 'mainHead', 'oldName', 'newName']):
        return jsonify({"message": "Nature, main head, old name, and new name are required"}), 400
    try:
        success = edit_category(get_db(), data['nature'], data['mainHead'], data['oldName'], data['newName'], user=get_current_user(), tenant_id=get_current_tenant_id())
        if not success: return jsonify({"message": "Category not found"}), 404
        return jsonify({"message": "Category updated successfully"}), 200
    except Exception as e:
        logging.error(f"Error in handle_edit_category: {e}")
        return jsonify({"message": "Failed to update category", "error": str(e)}), 500

@classification_bp.route('/option', methods=['PUT'])
def handle_edit_option():
    data = request.get_json()
    if not all(k in data for k in ['nature', 'mainHead', 'category', 'oldName', 'newName']):
        return jsonify({"message": "All path fields, old name, and new name are required"}), 400
    try:
        success = edit_option(get_db(), data['nature'], data['mainHead'], data['category'], data['oldName'], data['newName'], user=get_current_user(), tenant_id=get_current_tenant_id())
        if not success: return jsonify({"message": "Option not found or no change made"}), 404
        return jsonify({"message": "Option updated successfully"}), 200
    except Exception as e:
        logging.error(f"Error in handle_edit_option: {e}")
        return jsonify({"message": "Failed to update option", "error": str(e)}), 500

# --- PATCH (LOCK) Route ---
@classification_bp.route('/lock', methods=['PATCH'])
def handle_lock_status():
    data = request.get_json()
    if not all(k in data for k in ['level', 'context', 'isLocked']):
        return jsonify({"message": "Level, context, and lock status are required"}), 400
    try:
        success = update_lock_status(get_db(), data['level'], data['context'], data['isLocked'], user=get_current_user(), tenant_id=get_current_tenant_id())
        if not success: return jsonify({"message": "Item to update lock status not found"}), 404
        return jsonify({"message": "Lock status updated successfully"}), 200
    except Exception as e:
        logging.error(f"Error in handle_lock_status: {e}")
        return jsonify({"message": "Failed to update lock status", "error": str(e)}), 500
