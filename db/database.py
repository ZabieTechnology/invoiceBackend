    # db/database.py
from flask_pymongo import PyMongo

    # Create a PyMongo instance that will be initialized later with the Flask app
mongo = PyMongo()

def init_db(app):
        """
        Initializes the PyMongo extension with the Flask app instance.
        """
        mongo.init_app(app)

        # If using MongoDB for sessions, set the mongo client for Flask-Session
        if app.config.get('SESSION_TYPE') == 'mongodb':
            app.config['SESSION_MONGODB'] = mongo.cx # Pass the MongoClient instance
    