from flask import Blueprint, request, jsonify
from sqlalchemy.exc import SQLAlchemyError
from ..models import User
from ..protocol_models import AuditLog
from ..db_session import db_session
import uuid
from datetime import datetime
import hashlib
import secrets

# Create Blueprint for user routes
user_bp = Blueprint('user_routes', __name__)

def hash_password(password, salt=None):
    """Hash a password with a salt."""
    if salt is None:
        salt = secrets.token_hex(16)
    
    # Combine password and salt
    password_salt = password + salt
    
    # Hash the combined string
    hashed = hashlib.sha256(password_salt.encode()).hexdigest()
    
    return hashed, salt

def verify_password(password, hashed_password, salt):
    """Verify a password against a hash."""
    # Hash the password with the same salt
    new_hash, _ = hash_password(password, salt)
    
    # Compare the hashes
    return new_hash == hashed_password

@user_bp.route('/api/users', methods=['GET'])
def get_users():
    """Get all users or filter by parameters."""
    try:
        # Get query parameters
        role = request.args.get('role')
        
        # Start with base query
        query = db_session.query(User)
        
        # Apply filters if provided
        if role:
            query = query.filter(User.role == role)
        
        # Execute query and get results
        users = query.all()
        
        # Convert to dictionary (exclude password hash and salt)
        result = []
        for user in users:
            result.append({
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role,
                'created_at': user.created_at.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'is_active': user.is_active
            })
        
        return jsonify({
            'success': True,
            'users': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@user_bp.route('/api/users', methods=['POST'])
def create_user():
    """Create a new user."""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['username', 'email', 'password', 'first_name', 'last_name']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Check if username already exists
        existing_user = db_session.query(User).filter_by(username=data['username']).first()
        if existing_user:
            return jsonify({
                'success': False,
                'error': 'Username already exists'
            }), 400
        
        # Check if email already exists
        existing_email = db_session.query(User).filter_by(email=data['email']).first()
        if existing_email:
            return jsonify({
                'success': False,
                'error': 'Email already exists'
            }), 400
        
        # Hash password
        hashed_password, salt = hash_password(data['password'])
        
        # Create new user
        new_user = User(
            id=str(uuid.uuid4()),
            username=data['username'],
            email=data['email'],
            password_hash=hashed_password,
            password_salt=salt,
            first_name=data['first_name'],
            last_name=data['last_name'],
            role=data.get('role', 'user'),
            is_active=True
        )
        
        db_session.add(new_user)
        
        # Create audit log entry
        audit = AuditLog(
            id=str(uuid.uuid4()),
            action='create_user',
            entity_type='user',
            entity_id=new_user.id,
            user_id=data.get('created_by', 'system'),
            details={
                'username': new_user.username,
                'email': new_user.email,
                'role': new_user.role
            },
            ip_address=request.remote_addr
        )
        db_session.add(audit)
        
        db_session.commit()
        
        return jsonify({
            'success': True,
            'user': {
                'id': new_user.id,
                'username': new_user.username,
                'email': new_user.email,
                'first_name': new_user.first_name,
                'last_name': new_user.last_name,
                'role': new_user.role,
                'created_at': new_user.created_at.isoformat(),
                'is_active': new_user.is_active
            }
        }), 201
        
    except SQLAlchemyError as e:
        db_session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@user_bp.route('/api/users/<user_id>', methods=['GET'])
def get_user(user_id):
    """Get a specific user by ID."""
    try:
        user = db_session.query(User).filter_by(id=user_id).first()
        
        if not user:
            return jsonify({
                'success': False,
                'error': f'User with ID {user_id} not found'
            }), 404
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role,
                'created_at': user.created_at.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'is_active': user.is_active
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@user_bp.route('/api/users/<user_id>', methods=['PUT'])
def update_user(user_id):
    """Update a specific user."""
    try:
        data = request.json
        
        # Find user
        user = db_session.query(User).filter_by(id=user_id).first()
        if not user:
            return jsonify({
                'success': False,
                'error': f'User with ID {user_id} not found'
            }), 404
        
        # Check if updating username and it already exists
        if 'username' in data and data['username'] != user.username:
            existing_user = db_session.query(User).filter_by(username=data['username']).first()
            if existing_user:
                return jsonify({
                    'success': False,
                    'error': 'Username already exists'
                }), 400
        
        # Check if updating email and it already exists
        if 'email' in data and data['email'] != user.email:
            existing_email = db_session.query(User).filter_by(email=data['email']).first()
            if existing_email:
                return jsonify({
                    'success': False,
                    'error': 'Email already exists'
                }), 400
        
        # Update fields
        if 'username' in data:
            user.username = data['username']
        if 'email' in data:
            user.email = data['email']
        if 'first_name' in data:
            user.first_name = data['first_name']
        if 'last_name' in data:
            user.last_name = data['last_name']
        if 'role' in data:
            user.role = data['role']
        if 'is_active' in data:
            user.is_active = data['is_active']
        
        # Update password if provided
        if 'password' in data:
            hashed_password, salt = hash_password(data['password'])
            user.password_hash = hashed_password
            user.password_salt = salt
        
        # Create audit log entry
        audit = AuditLog(
            id=str(uuid.uuid4()),
            action='update_user',
            entity_type='user',
            entity_id=user.id,
            user_id=data.get('updated_by', 'system'),
            details={
                'updated_fields': list(data.keys())
            },
            ip_address=request.remote_addr
        )
        db_session.add(audit)
        
        db_session.commit()
        
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role,
                'created_at': user.created_at.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'is_active': user.is_active
            }
        })
        
    except SQLAlchemyError as e:
        db_session.rollback()
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@user_bp.route('/api/auth/login', methods=['POST'])
def login():
    """Authenticate a user."""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['username', 'password']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Find user by username
        user = db_session.query(User).filter_by(username=data['username']).first()
        if not user:
            return jsonify({
                'success': False,
                'error': 'Invalid username or password'
            }), 401
        
        # Check if user is active
        if not user.is_active:
            return jsonify({
                'success': False,
                'error': 'User account is inactive'
            }), 401
        
        # Verify password
        if not verify_password(data['password'], user.password_hash, user.password_salt):
            return jsonify({
                'success': False,
                'error': 'Invalid username or password'
            }), 401
        
        # Update last login time
        user.last_login = datetime.now()
        
        # Create audit log entry
        audit = AuditLog(
            id=str(uuid.uuid4()),
            action='user_login',
            entity_type='user',
            entity_id=user.id,
            user_id=user.id,
            details={
                'username': user.username
            },
            ip_address=request.remote_addr
        )
        db_session.add(audit)
        
        db_session.commit()
        
        # In a real application, you would generate a JWT token here
        # For now, just return user info
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'role': user.role
            },
            'message': 'Login successful'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@user_bp.route('/api/auth/logout', methods=['POST'])
def logout():
    """Log out a user."""
    try:
        data = request.json
        
        # Validate required fields
        if 'user_id' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: user_id'
            }), 400
        
        # Find user
        user = db_session.query(User).filter_by(id=data['user_id']).first()
        if not user:
            return jsonify({
                'success': False,
                'error': f'User with ID {data["user_id"]} not found'
            }), 404
        
        # Create audit log entry
        audit = AuditLog(
            id=str(uuid.uuid4()),
            action='user_logout',
            entity_type='user',
            entity_id=user.id,
            user_id=user.id,
            details={
                'username': user.username
            },
            ip_address=request.remote_addr
        )
        db_session.add(audit)
        
        db_session.commit()
        
        # In a real application, you would invalidate the JWT token here
        return jsonify({
            'success': True,
            'message': 'Logout successful'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
