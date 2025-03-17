from flask import Flask, request, jsonify
from flask_pymongo import PyMongo
from flask_cors import CORS
from bson.objectid import ObjectId
from datetime import datetime
import logging
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

app = Flask(__name__)
CORS(app)  # Enable CORS

# MongoDB configuration
app.config["MONGO_URI"] = os.getenv("DATABASE_URL")
mongo = PyMongo(app)

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
        dropdown_values = list(mongo.db.dropdown.find().skip(skip).limit(limit))
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
        logging.error(f"Error fetching dropdown values: {e}")
        return jsonify({"message": "Failed to fetch dropdown values"}), 500

# Route to add a new dropdown value
@app.route("/api/dropdown", methods=["POST"])
def add_dropdown_value():
    data = request.get_json()
    if not data or not data.get("type") or not data.get("value") or not data.get("label"):
        return jsonify({"message": "Type, value, and label are required"}), 400

    # Insert new value with created_date, updated_date, and updated_user
    result = mongo.db.dropdown.insert_one({
        "type": data["type"],
        "value": data["value"],
        "label": data["label"],
        "created_date": datetime.utcnow(),
        "updated_date": datetime.utcnow(),
        "updated_user": "Admin",  # Replace with actual user
    })
    return jsonify({"message": "Dropdown value added successfully", "id": str(result.inserted_id)}), 201

# Route to update a dropdown value
@app.route("/api/dropdown/<id>", methods=["PUT"])
def update_dropdown_value(id):
    data = request.get_json()
    if not data or not data.get("label"):
        return jsonify({"message": "Label is required"}), 400

    # Update value with updated_date and updated_user
    result = mongo.db.dropdown.update_one(
        {"_id": ObjectId(id)},
        {
            "$set": {
                "label": data["label"],
                "updated_date": datetime.utcnow(),
                "updated_user": "Admin",  # Replace with actual user
            }
        }
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
    app.run(debug=True)