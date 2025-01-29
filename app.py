from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from flask_cors import CORS
from flask_jwt_extended import JWTManager, create_access_token, jwt_required
import bcrypt
import certifi  # For SSL certificates
from datetime import timedelta
from dotenv import load_dotenv
import os



load_dotenv()

app = Flask(__name__)

# Enable CORS for the frontend
CORS(app)

# MongoDB URI and SSL setup
mongo_uri = os.getenv("DATABASE_URL")
app.config["MONGO_URI"] = mongo_uri

# Initialize PyMongo with the SSL certificates
mongo = PyMongo(app,tlsCAFile=certifi.where())

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

if __name__ == "__main__":
    app.run(debug=True)


""" 
from pymongo.mongo_client import MongoClient
import certifi

uri = "mongodb+srv://dbUser:test@cobook.14ec1.mongodb.net/?retryWrites=true&w=majority&appName=cobook"

# Create a new client and connect to the server
client = MongoClient(uri, tlsCAFile=certifi.where())

# Send a ping to confirm a successful connection
try:
    client.admin.command('ping')
    print("Pinged your deployment. You successfully connected to MongoDB!")
except Exception as e:
    print(e) """