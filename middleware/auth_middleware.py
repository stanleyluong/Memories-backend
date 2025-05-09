import jwt # PyJWT library
from functools import wraps
from flask import request, jsonify
import os

# It's better to get the secret from environment variables
JWT_SECRET = os.getenv("JWT_SECRET", "test") # Default to "test" if not set

def auth_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        token = None
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return jsonify(message="Authorization header is missing"), 401

        try:
            token_parts = auth_header.split(" ")
            if len(token_parts) != 2 or token_parts[0].lower() != 'bearer':
                raise ValueError("Invalid token format. Expected 'Bearer <token>'")
            token = token_parts[1]
        except Exception as e:
             return jsonify(message=f"Token error: {str(e)}"), 401

        if not token:
            return jsonify(message="Token is missing"), 401

        try:
            # Distinguish between custom JWT and Google OAuth token
            is_custom_auth = len(token) < 500 # Same logic as in Node.js middleware
            decoded_data = None
            user_id = None

            if is_custom_auth:
                # This is our own JWT, verify it with the secret
                decoded_data = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
                user_id = decoded_data.get('id')
            else:
                # This is potentially a Google token. 
                # IMPORTANT: jwt.decode only decodes, it DOES NOT VERIFY the signature for Google tokens.
                # For Google tokens, proper validation involves fetching Google's public keys.
                # This is a security risk if not handled correctly.
                # Replicating the Node.js logic for now.
                decoded_data = jwt.decode(token, options={"verify_signature": False}) # Decode without verification
                user_id = decoded_data.get('sub')
            
            if not user_id:
                return jsonify(message="User ID not found in token"), 401
            
            # Add user_id to Flask's g object or pass as argument
            # For simplicity, we can pass it as an argument to the wrapped function
            # The route function will need to accept 'current_user_id' as a parameter
            kwargs['current_user_id'] = user_id

        except jwt.ExpiredSignatureError:
            return jsonify(message="Token has expired"), 401
        except jwt.InvalidTokenError as e:
            return jsonify(message=f"Invalid token: {str(e)}"), 401
        except Exception as e:
            print(f"Auth middleware error: {e}")
            return jsonify(message="Authentication failed due to an unexpected error"), 500

        return f(*args, **kwargs)
    return decorated_function 