from venv import logger
from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
import bcrypt
import certifi  # For SSL certificates
from datetime import timedelta
from dotenv import load_dotenv
import os
from bson.objectid import ObjectId  # For handling MongoDB ObjectIDs


load_dotenv()

app = Flask(__name__)

# Enable CORS for the frontend
CORS(app)

# MongoDB URI and SSL setup
mongo_uri = os.getenv("DATABASE_URL")
app.config["MONGO_URI"] = mongo_uri


# Check MongoDB connection
def check_mongo_connection():
    try:
        # Attempt to connect to MongoDB and list collections
        collections = mongo.db.list_collection_names()
        logger.debug(f"Connected to MongoDB. Collections: {collections}")
        return True
    except Exception as e:
        logger.error(f"Failed to connect to MongoDB: {e}")
        return False
    
# Initialize PyMongo with the SSL certificates
mongo = PyMongo(app, tlsCAFile=certifi.where())

# JWT Configuration
app.config["JWT_SECRET_KEY"] = "your_jwt_secret_key"  # Replace with your own secret key
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=1)
jwt = JWTManager(app)


@app.route("/", methods=["GET"])
def home():
    return jsonify(status="success"), 200


# Route for user registration
@app.route("/register", methods=["POST"])
def register_user():
    data = request.get_json()
    print(data)
    username = data.get("username")
    password = data.get("password")
    email = data.get("email")

    # Check if the user already exists
    existing_user = mongo.db.users.find_one({"username": username})  # Referring to the 'users' collection
    if existing_user:
        return jsonify({"message": "Username already exists"}), 400

    existing_email = mongo.db.users.find_one({"email": email})  # Referring to the 'users' collection
    if existing_email:
        return jsonify({"message": "Email already exists"}), 400

    # Hash the password using bcrypt
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    # Create a new user in the 'users' collection
    mongo.db.users.insert_one({
        "username": username,
        "password": hashed_password,
        "email": email
    })

    return jsonify({"message": "User registered successfully"}), 201


# Route for user login
@app.route("/login", methods=["POST"])
def login_user():
    data = request.get_json()
    print(data)
    username = data.get("username")
    password = data.get("password")

    # Find the user by username in the 'users' collection
    user = mongo.db.users.find_one({"username": username})
    if not user:
        return jsonify({"message": "User not found"}), 404

    # Verify the password
    if not bcrypt.checkpw(password.encode('utf-8'), user["password"]):
        return jsonify({"message": "Invalid password"}), 400

    # Create JWT token
    access_token = create_access_token(identity=username)
    return jsonify(access_token=access_token), 200


# Protected route example
@app.route("/protected", methods=["GET"])
@jwt_required()
def protected():
    return jsonify(message="This is a protected route.")


# Route to fetch dropdown values with pagination
@app.route("/api/dropdown", methods=["GET"])
def get_dropdown_values():
    try:
        # Pagination parameters
        page = int(request.args.get("page", 1))
        limit = int(request.args.get("limit", 25))

        # Calculate skip value for pagination
        skip = (page - 1) * limit

        # Fetch dropdown values with pagination
        dropdown_values = mongo.db.dropdown.find().skip(skip).limit(limit)
        total_items = mongo.db.dropdown.count_documents({})

        # Convert MongoDB cursor to a list of dictionaries
        result = [
            {
                "_id": str(item["_id"]),  # Convert ObjectId to string
                "type": item["type"],
                "value": item["value"],
                "label": item["label"]
            }
            for item in dropdown_values
        ]

        return jsonify({
            "data": result,
            "total": total_items,
            "page": page,
            "limit": limit
        }), 200
    except Exception as e:
        logger.error(f"Error fetching dropdown values: {e}")
        return jsonify({"message": "Failed to fetch dropdown values"}), 500




# Route to fetch dropdown values
@app.route("/api/dropdown", methods=["GET"])
def get_dropdown_values():
    try:
        # Fetch all dropdown values from MongoDB
        dropdown_values = mongo.db.dropdown.find({})
        
        # Convert MongoDB cursor to a list of dictionaries
        result = [
            {
                "_id": str(item["_id"]),  # Convert ObjectId to string
                "type": item["type"],
                "value": item["value"],
                "label": item["label"]
            }
            for item in dropdown_values
        ]

       

        return jsonify(result), 200
    except Exception as e:
        logger.error(f"Error fetching dropdown values: {e}")
        return jsonify({"message": "Failed to fetch dropdown values"}), 500


# Route to add a new dropdown value
@app.route("/api/dropdown", methods=["POST"])
def add_dropdown_value():
    data = request.get_json()
    logger.debug(f"Received data: {data}")  # Log the incoming data

    if not data or not data.get("type") or not data.get("value") or not data.get("label"):
        logger.error("Missing required fields: type, value, or label")
        return jsonify({"message": "Type, value, and label are required"}), 400

    # Insert the new dropdown value
    result = mongo.db.dropdown.insert_one({
        "type": data["type"],
        "value": data["value"],
        "label": data["label"]
    })

    logger.debug(f"Inserted document ID: {result.inserted_id}")
    return jsonify({"message": "Dropdown value added successfully", "id": str(result.inserted_id)}), 201


# Route to update a dropdown value
@app.route("/api/dropdown/<id>", methods=["PUT"])
def update_dropdown_value(id):
    data = request.get_json()
    if not data or not data.get("label"):
        return jsonify({"message": "Label is required"}), 400

    # Update the dropdown value
    result = mongo.db.dropdown.update_one(
        {"_id": ObjectId(id)},
        {"$set": {"label": data["label"]}}
    )

    if result.matched_count == 0:
        return jsonify({"message": "Dropdown value not found"}), 404

    return jsonify({"message": "Dropdown value updated successfully"}), 200


# Route to delete a dropdown value
@app.route("/api/dropdown/<id>", methods=["DELETE"])
def delete_dropdown_value(id):
    result = mongo.db.dropdown.delete_one({"_id": ObjectId(id)})

    if result.deleted_count == 0:
        return jsonify({"message": "Dropdown value not found"}), 404

    return jsonify({"message": "Dropdown value deleted successfully"}), 200


if __name__ == "__main__":
    # Check MongoDB connection when the app starts
    if check_mongo_connection():
        logger.info("MongoDB connection successful. Starting Flask app...")
        app.run(debug=True)
    else:
        logger.error("MongoDB connection failed. Exiting...")