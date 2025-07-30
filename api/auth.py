# api/auth.py
from flask import Blueprint, request, jsonify, current_app
import logging
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity, get_jwt
from datetime import datetime, timedelta

from db.user_dal import create_user, get_user_by_username, get_user_by_id, verify_password
from db.database import mongo

auth_bp = Blueprint(
    'auth_bp',
    __name__,
    url_prefix='/api/auth'
)

logging.basicConfig(level=logging.INFO)

# --- (Registration and other functions remain the same) ---
@auth_bp.route('/register', methods=['POST'])
def register():
    """Endpoint to register a new user."""
    data = request.get_json()
    if not data:
        return jsonify({"message": "Invalid JSON provided"}), 400

    username = data.get('username')
    password = data.get('password')
    email = data.get('email')
    company_legal_name = data.get('companyLegalName')

    if not username or not password or not company_legal_name:
        return jsonify({"message": "Missing required fields. Username, password, and company name are required."}), 400

    try:
        if get_user_by_username(username):
            return jsonify({"message": "Username already exists. Please choose another."}), 409

        user_id = create_user(
            username=username,
            password=password,
            email=email,
            company_legal_name=company_legal_name
        )

        if user_id:
            logging.info(f"Successfully registered user '{username}' with ID {user_id}")
            return jsonify({"message": "User registered successfully", "userId": str(user_id)}), 201
        else:
            return jsonify({"message": "Registration failed."}), 500

    except ValueError as ve:
        logging.error(f"ValueError during registration for {username}: {ve}")
        return jsonify({"message": str(ve)}), 400
    except Exception as e:
        logging.error(f"Error during registration for {username}: {e}")
        return jsonify({"message": "An error occurred during registration."}), 500

@auth_bp.route('/login', methods=['POST'])
def login():
    """
    Login endpoint. On success, it returns a JWT with the tenant_id and role embedded.
    """
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

            # --- ADD TENANT ID AND ROLE TO JWT ---
            # This is where we define who gets the admin role.
            # In a real app, this might come from a 'roles' field in the user document.
            # For this example, we'll assign the 'admin' role to a specific user, e.g., 'sa'.
            user_role = "admin" if user.get('username') == 'sa' else "user"

            additional_claims = {
                "tenant_id": user.get("tenant_id"),
                "role": user_role
            }

            access_token = create_access_token(
                identity=str(user['_id']),
                additional_claims=additional_claims
            )

            logging.info(f"User '{username}' logged in successfully with role '{user_role}'.")
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
    """Fetches the profile information for the currently logged-in user."""
    current_user_id = get_jwt_identity()
    user = get_user_by_id(current_user_id)

    if not user:
        return jsonify({"message": "User not found"}), 404

    # Also return role in the profile
    claims = get_jwt()
    user_role = claims.get("role", "user")

    return jsonify({
        "id": str(user["_id"]),
        "username": user["username"],
        "email": user.get("email"),
        "tenant_id": user.get("tenant_id"),
        "role": user_role
    }), 200

