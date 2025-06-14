# invoiceBackend/db/database.py
from flask_pymongo import PyMongo
from flask import current_app, g

mongo = PyMongo()

def init_db(app):
    mongo.init_app(app)
    if app.config.get('SESSION_TYPE') == 'mongodb':
        try:
            app.config['SESSION_MONGODB'] = mongo.cx
        except AttributeError:
            app.config['SESSION_MONGODB'] = mongo.client
        app.config['SESSION_MONGODB_DB'] = app.config.get('SESSION_MONGODB_DB', mongo.db.name)
        app.config['SESSION_MONGODB_COLLECT'] = app.config.get('SESSION_MONGODB_COLLECT', 'sessions')

def get_db():
    if current_app:
        if 'db' not in g:
            g.db = mongo.db
        return g.db
    raise RuntimeError("Application context not found.")

# --- END OF database.py ---