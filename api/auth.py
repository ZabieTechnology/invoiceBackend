# api/auth.py
from flask import Blueprint, request, jsonify, current_app
import logging
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from datetime import timedelta

from db.user_dal import create_user, get_user_by_username, verify_password

auth_bp = Blueprint(
    'auth_bp',
    __name__,
    url_prefix='/api/auth' # Changed from /login to /api/auth for grouping
)

logging.basicConfig(level=logging.INFO)

@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({"message": "Username and password are required"}), 400

    username = data['username']
    password = data['password']
    email = data.get('email') # Optional email

    try:
        existing_user = get_user_by_username(username)
        if existing_user:
            return jsonify({"message": "Username already exists"}), 409 # Conflict

        user_id = create_user(username, password, email)
        if user_id:
            return jsonify({"message": "User created successfully", "userId": str(user_id)}), 201
        else:
            # This case should ideally be caught by the existing_user check,
            # but as a fallback if create_user returns None for other reasons.
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
            if not user.get('is_active', True): # Check if user is active
                return jsonify({"message": "User account is inactive"}), 403

            # Create JWT token
            # expires_delta can be configured via app.config['JWT_ACCESS_TOKEN_EXPIRES']
            access_token = create_access_token(
                identity=str(user['_id']), # Store user's MongoDB ObjectId as string
                # additional_claims={"username": user['username'], "email": user.get('email')} # Optional additional claims
            )
            
            # Store user info in session (optional, if you still use Flask-Session for other things)
            # session['user_id'] = str(user['_id'])
            # session['username'] = user['username']

            logging.info(f"User '{username}' logged in successfully.")
            return jsonify(access_token=access_token, username=user['username']), 200
        else:
            logging.warning(f"Invalid login attempt for username: {username}")
            return jsonify({"message": "Invalid username or password"}), 401
            
    except Exception as e:
        logging.error(f"Error during login for {username}: {e}")
        return jsonify({"message": "An error occurred during login"}), 500

# Example protected route using JWT (can be in any blueprint)
@auth_bp.route('/profile', methods=['GET'])
@jwt_required() # This decorator ensures the request has a valid JWT
def profile():
    current_user_id = get_jwt_identity() # Retrieves the identity stored in the token
    # You can then fetch user details from DB using this ID if needed
    # For now, just return the ID
    return jsonify(logged_in_as_id=current_user_id), 200

