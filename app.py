import os
from flask import Flask, jsonify, request
from flask_cors import CORS
from mongoengine import connect, disconnect # Import disconnect
from serverless_wsgi import handle_request
import json # For pretty printing event
import logging # Import logging

# SET PYMONGO LOGGER TO DEBUG - Place this early, after imports
logging.basicConfig() # Ensure basicConfig is called if not already by another module
pymongo_logger = logging.getLogger('pymongo')
pymongo_logger.setLevel(logging.DEBUG)
# You might want to also set the root logger to DEBUG if pymongo doesn't output enough
# logging.getLogger().setLevel(logging.DEBUG)

# Import Blueprints
from routes.posts_routes import posts_bp # Changed to direct import
from routes.user_routes import user_bp   # Changed to direct import
# We will add user_routes_bp later

# Initialize Flask app
app = Flask(__name__)
app.url_map.strict_slashes = False # Set strict_slashes globally for the app

# CORS Configuration
CORS(app, resources={r"/*": {"origins": "*"}}) # Allow all origins for now, can be restricted later

# MongoDB Connection
CONNECTION_URL = os.getenv("CONNECTION_URL")

# Connect to MongoDB when the app starts or on the first request if preferred.
# For Lambda, it's often better to connect within the handler or ensure the connection
# is managed correctly across invocations (e.g., check connection state).

# Placeholder for database connection logic
# We will refine this. For now, just defining it.
def connect_db():
    try:
        print("CONNECT_DB: Attempting connection with PyMongo DEBUG logging enabled...")
        if CONNECTION_URL:
            # MongoEngine's connect is idempotent for the default connection alias if params are the same.
            # Add serverSelectionTimeoutMS to help prevent indefinite hangs
            connect(host=CONNECTION_URL, alias='default', serverSelectionTimeoutMS=10000) # 10-second timeout
            print("CONNECT_DB: Successfully connected to MongoDB via MongoEngine!")
        else:
            print("CONNECT_DB: CONNECTION_URL not found.")
    except Exception as e:
        print(f"CONNECT_DB: Error connecting to MongoDB (see PyMongo DEBUG logs above for details): {e}")
        raise # Re-raise the exception to be caught by the handler or higher up

# Logging middleware - VERY IMPORTANT FOR DEBUGGING
@app.before_request
def log_request_info():
    # This will log before each request handled by Flask
    print(f"FLASK_REQUEST: Path={request.path}, Method={request.method}, Headers={request.headers}")
    if request.data:
        try:
            print(f"FLASK_REQUEST: Body={request.get_json()}")
        except Exception:
            print(f"FLASK_REQUEST: Body (non-JSON)={request.data}")

# Example Route
@app.route('/', methods=['GET'])
def welcome():
    print("FLASK_ROUTING: Hit GET / fallback handler")
    return jsonify(message="welcome to the Memories API (Python/Flask)")

# Register Blueprints
app.register_blueprint(posts_bp)
app.register_blueprint(user_bp) # Register the user blueprint
# app.register_blueprint(user_routes_bp) # Will be uncommented later

@app.errorhandler(Exception)
def handle_global_error(e):
    print(f"FLASK_GLOBAL_ERROR_HANDLER: An error occurred: {e}")
    # Add CORS headers to error responses
    response = jsonify(message="Internal Server Error", error=str(e))
    response.status_code = 500
    response.headers.add('Access-Control-Allow-Origin', '*')
    return response

# Lambda handler function
def lambda_handler(event, context):
    print("LAMBDA_HANDLER: Entered")
    # Pretty print the event if possible
    try:
        print(f"LAMBDA_HANDLER: Received event: {json.dumps(event, indent=2)}")
    except Exception:
        print(f"LAMBDA_HANDLER: Received event (raw): {event}")
    
    db_connected_successfully = False
    try:
        print("LAMBDA_HANDLER: Attempting to connect to DB...")
        connect_db() 
        print("LAMBDA_HANDLER: DB connection attempt finished (or was already connected).")
        db_connected_successfully = True
    except Exception as e:
        print(f"LAMBDA_HANDLER: Critical error during connect_db: {e}")
        # Return an immediate error response if DB connection fails critically
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', "Access-Control-Allow-Headers": "Content-Type,Authorization", "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,PATCH,OPTIONS"},
            'body': json.dumps({'message': 'Internal Server Error - DB Connection Failed', 'error': str(e)})
        }

    # Only proceed if DB was (presumably) okay
    if db_connected_successfully:
        print("LAMBDA_HANDLER: Calling serverless_wsgi.handle_request...")
        try:
            response = handle_request(app, event, context)
            print(f"LAMBDA_HANDLER: handle_request returned (raw): {response}") 
            # Ensure response structure is what API Gateway expects for proxy integration
            # serverless-wsgi should handle this, but good to log for debugging.
            return response
        except Exception as e:
            print(f"LAMBDA_HANDLER: Error during serverless_wsgi.handle_request: {e}")
            return {
                'statusCode': 500,
                'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', "Access-Control-Allow-Headers": "Content-Type,Authorization", "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,PATCH,OPTIONS"},
                'body': json.dumps({'message': 'Internal Server Error - WSGI Processing', 'error': str(e)})
            }
    else:
        # This case should ideally be caught by the exception block above
        print("LAMBDA_HANDLER: DB not connected, not calling handle_request.")
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json', 'Access-Control-Allow-Origin': '*', "Access-Control-Allow-Headers": "Content-Type,Authorization", "Access-Control-Allow-Methods": "GET,POST,PUT,DELETE,PATCH,OPTIONS"},
            'body': json.dumps({'message': 'Internal Server Error - DB Not Connected'})
        }

if __name__ == '__main__':
    print("Starting Flask app for local development...")
    connect_db()
    app.run(debug=True, port=os.getenv("PORT", 5001)) 