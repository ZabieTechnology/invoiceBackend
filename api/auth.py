# api/auth.py
from flask import Blueprint, request, jsonify, current_app
import logging
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from datetime import timedelta

# Updated import to include get_test_users
from db.user_dal import create_user, get_user_by_username, verify_password, get_test_users

auth_bp = Blueprint(
    'auth_bp',
    __name__,
    url_prefix='/api/auth'
)

logging.basicConfig(level=logging.INFO)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"message": "Username and password are required"}), 400

    username = data['username']
    password = data['password']
    email = data.get('email')

    try:
        existing_user = get_user_by_username(username)
        if existing_user:
            return jsonify({"message": "Username already exists"}), 409

        user_id = create_user(username, password, email)
        if user_id:
            return jsonify({"message": "User created successfully", "userId": str(user_id)}), 201
        else:
            return jsonify({"message": "User registration failed"}), 500

    except Exception as e:
        logging.error(f"Error during registration for {username}: {e}")
        return jsonify({"message": "An error occurred during registration"}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"message": "Username and password are required"}), 400

    username = data['username']
    password = data['password']

    try:
        user = get_user_by_username(username)
        if user and verify_password(user['password_hash'], password):
            if not user.get('is_active', True):
                return jsonify({"message": "User account is inactive"}), 403

            access_token = create_access_token(identity=str(user['_id']))

            logging.info(f"User '{username}' logged in successfully.")
            return jsonify(access_token=access_token, username=user['username']), 200
        else:
            logging.warning(f"Invalid login attempt for username: {username}")
            return jsonify({"message": "Invalid username or password"}), 401

    except Exception as e:
        logging.error(f"Error during login for {username}: {e}")
        return jsonify({"message": "An error occurred during login"}), 500

@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def profile():
    current_user_id = get_jwt_identity()
    return jsonify(logged_in_as_id=current_user_id), 200

# --- New endpoint for fetching test users ---
@auth_bp.route('/test-users', methods=['GET'])
def test_users():
    """
    Endpoint to fetch a few users for testing DB connectivity.
    This should ideally be removed or secured in a production environment.
    """
    try:
        users = get_test_users(limit=5) # Get top 5 users
        return jsonify(users), 200
    except Exception as e:
        logging.error(f"Error fetching test users for API: {e}")
        return jsonify({"message": "Failed to fetch test users"}), 500
