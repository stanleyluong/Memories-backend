from flask import Blueprint, request, jsonify
from models.user_model import User # Changed to direct import
import bcrypt # For password hashing
import jwt # PyJWT for generating tokens
import datetime
import os

# Blueprint Configuration
user_bp = Blueprint(
    'user_bp',
    __name__,
    url_prefix='/user'
)

JWT_SECRET = os.getenv("JWT_SECRET", "test") # Same secret as in auth_middleware

@user_bp.route('/signin', methods=['POST'])
def signin():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')

    if not email or not password:
        return jsonify(message="Email and password are required"), 400

    try:
        existing_user = User.objects(email=email).first()
        if not existing_user:
            return jsonify(message="User doesn't exist."), 404

        # Check password (bcrypt.checkpw needs encoded versions)
        if not bcrypt.checkpw(password.encode('utf-8'), existing_user.password.encode('utf-8')):
            return jsonify(message="Invalid credentials."), 400
        
        # Password is correct, generate a token
        token_payload = {
            'email': existing_user.email,
            'id': str(existing_user.id), # Use str(ObjectId)
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }
        token = jwt.encode(token_payload, JWT_SECRET, algorithm="HS256")

        # Prepare user data for response (excluding password)
        user_data = {
            'id': str(existing_user.id),
            'email': existing_user.email,
            'name': existing_user.name
        }
        return jsonify(result=user_data, token=token), 200

    except Exception as e:
        print(f"Error in signin: {e}")
        return jsonify(message="Something went wrong during sign-in."), 500

@user_bp.route('/signup', methods=['POST'])
def signup():
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    confirm_password = data.get('confirmPassword')
    first_name = data.get('firstName')
    last_name = data.get('lastName')

    if not all([email, password, confirm_password, first_name, last_name]):
        return jsonify(message="All fields are required for signup"), 400

    if password != confirm_password:
        return jsonify(message="Passwords don't match"), 400

    try:
        existing_user = User.objects(email=email).first()
        if existing_user:
            return jsonify(message="User already exists."), 400

        # Hash password
        hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt(12))
        
        new_user = User(
            email=email,
            password=hashed_password.decode('utf-8'), # Store hashed password as string
            name=f"{first_name} {last_name}"
        )
        new_user.save()

        # Generate token for the new user
        token_payload = {
            'email': new_user.email,
            'id': str(new_user.id),
            'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
        }
        token = jwt.encode(token_payload, JWT_SECRET, algorithm="HS256")
        
        # Prepare user data for response
        user_data = {
            'id': str(new_user.id),
            'email': new_user.email,
            'name': new_user.name
        }
        return jsonify(result=user_data, token=token), 201 # 201 Created for signup

    except Exception as e:
        print(f"Error in signup: {e}")
        # Could be mongoengine.errors.NotUniqueError if email unique constraint is violated at DB level despite check
        if "NotUniqueError" in str(type(e)) or (hasattr(e, 'message') and "User already exists" in str(e.message)):
             return jsonify(message="User already exists."), 400
        return jsonify(message="Something went wrong during sign-up."), 500 