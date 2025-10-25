from flask import Blueprint, request, jsonify
from sqlalchemy.exc import SQLAlchemyError
from ..models import Project, User, TeamMember
from ..db_session import db_session
from ..protocol_models import AuditLog
import uuid
from datetime import datetime

# Create Blueprint for project routes
project_bp = Blueprint('project_routes', __name__)

@project_bp.route('/api/projects', methods=['GET'])
def get_projects():
    """Get all projects or filter by user."""
    try:
        # Get query parameters
        user_id = request.args.get('user_id')
        status = request.args.get('status')
        
        # Start with base query
        query = db_session.query(Project)
        
        # Apply filters if provided
        if user_id:
            # Get projects where user is a team member
            team_projects = db_session.query(TeamMember.project_id).filter_by(user_id=user_id).all()
            project_ids = [p[0] for p in team_projects]
            # Also include projects created by the user
            query = query.filter((Project.id.in_(project_ids)) | (Project.created_by == user_id))
        
        if status:
            query = query.filter(Project.status == status)
        
        # Execute query and get results
        projects = query.all()
        
        # Convert to dictionary
        result = []
        for project in projects:
            result.append({
                'id': project.id,
                'title': project.title,
                'description': project.description,
                'objectives': project.objectives,
                'created_at': project.created_at.isoformat(),
                'updated_at': project.updated_at.isoformat(),
                'created_by': project.created_by,
                'status': project.status.value if hasattr(project.status, 'value') else project.status,
                'metadata': project.metadata
            })
        
        return jsonify({
            'success': True,
            'projects': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@project_bp.route('/api/projects', methods=['POST'])
def create_project():
    """Create a new project."""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['title', 'created_by']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Check if user exists
        user = db_session.query(User).filter_by(id=data['created_by']).first()
        if not user:
            return jsonify({
                'success': False,
                'error': f'User with ID {data["created_by"]} not found'
            }), 404
        
        # Create new project
        new_project = Project(
            id=str(uuid.uuid4()),
            title=data['title'],
            description=data.get('description', ''),
            objectives=data.get('objectives', ''),
            created_by=data['created_by'],
            status=data.get('status', 'planned'),
            metadata=data.get('metadata', {})
        )
        
        db_session.add(new_project)
        
        # Add creator as team member with owner role
        team_member = TeamMember(
            id=str(uuid.uuid4()),
            user_id=data['created_by'],
            project_id=new_project.id,
            role='owner',
            invited_by=data['created_by']
        )
        db_session.add(team_member)
        
        # Create audit log entry
        audit = AuditLog(
            id=str(uuid.uuid4()),
            action='create_project',
            entity_type='project',
            entity_id=new_project.id,
            user_id=data['created_by'],
            details={'project_title': new_project.title},
            ip_address=request.remote_addr
        )
        db_session.add(audit)
        
        db_session.commit()
        
        return jsonify({
            'success': True,
            'project': {
                'id': new_project.id,
                'title': new_project.title,
                'description': new_project.description,
                'objectives': new_project.objectives,
                'created_at': new_project.created_at.isoformat(),
                'updated_at': new_project.updated_at.isoformat(),
                'created_by': new_project.created_by,
                'status': new_project.status.value if hasattr(new_project.status, 'value') else new_project.status,
                'metadata': new_project.metadata
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

@project_bp.route('/api/projects/<project_id>', methods=['GET'])
def get_project(project_id):
    """Get a specific project by ID."""
    try:
        project = db_session.query(Project).filter_by(id=project_id).first()
        
        if not project:
            return jsonify({
                'success': False,
                'error': f'Project with ID {project_id} not found'
            }), 404
        
        # Get team members
        team_members = db_session.query(TeamMember).filter_by(project_id=project_id).all()
        team = []
        for member in team_members:
            user = db_session.query(User).filter_by(id=member.user_id).first()
            if user:
                team.append({
                    'user_id': user.id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'role': member.role,
                    'joined_at': member.joined_at.isoformat()
                })
        
        return jsonify({
            'success': True,
            'project': {
                'id': project.id,
                'title': project.title,
                'description': project.description,
                'objectives': project.objectives,
                'created_at': project.created_at.isoformat(),
                'updated_at': project.updated_at.isoformat(),
                'created_by': project.created_by,
                'status': project.status.value if hasattr(project.status, 'value') else project.status,
                'metadata': project.metadata,
                'team': team
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@project_bp.route('/api/projects/<project_id>', methods=['PUT'])
def update_project(project_id):
    """Update a specific project."""
    try:
        data = request.json
        
        # Find project
        project = db_session.query(Project).filter_by(id=project_id).first()
        if not project:
            return jsonify({
                'success': False,
                'error': f'Project with ID {project_id} not found'
            }), 404
        
        # Update fields
        if 'title' in data:
            project.title = data['title']
        if 'description' in data:
            project.description = data['description']
        if 'objectives' in data:
            project.objectives = data['objectives']
        if 'status' in data:
            project.status = data['status']
        if 'metadata' in data:
            project.metadata = data['metadata']
        
        project.updated_at = datetime.now()
        
        # Create audit log entry
        audit = AuditLog(
            id=str(uuid.uuid4()),
            action='update_project',
            entity_type='project',
            entity_id=project.id,
            user_id=data.get('user_id', 'system'),
            details={'updated_fields': list(data.keys())},
            ip_address=request.remote_addr
        )
        db_session.add(audit)
        
        db_session.commit()
        
        return jsonify({
            'success': True,
            'project': {
                'id': project.id,
                'title': project.title,
                'description': project.description,
                'objectives': project.objectives,
                'created_at': project.created_at.isoformat(),
                'updated_at': project.updated_at.isoformat(),
                'created_by': project.created_by,
                'status': project.status.value if hasattr(project.status, 'value') else project.status,
                'metadata': project.metadata
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

@project_bp.route('/api/projects/<project_id>', methods=['DELETE'])
def delete_project(project_id):
    """Delete or archive a project."""
    try:
        # Get query parameters
        archive_only = request.args.get('archive', 'true').lower() == 'true'
        user_id = request.args.get('user_id', 'system')
        
        # Find project
        project = db_session.query(Project).filter_by(id=project_id).first()
        if not project:
            return jsonify({
                'success': False,
                'error': f'Project with ID {project_id} not found'
            }), 404
        
        if archive_only:
            # Archive the project instead of deleting
            project.status = 'archived'
            project.updated_at = datetime.now()
            
            # Create audit log entry
            audit = AuditLog(
                id=str(uuid.uuid4()),
                action='archive_project',
                entity_type='project',
                entity_id=project.id,
                user_id=user_id,
                details={'project_title': project.title},
                ip_address=request.remote_addr
            )
            db_session.add(audit)
            
            db_session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Project {project_id} has been archived'
            })
        else:
            # Create audit log entry before deletion
            audit = AuditLog(
                id=str(uuid.uuid4()),
                action='delete_project',
                entity_type='project',
                entity_id=project.id,
                user_id=user_id,
                details={'project_title': project.title},
                ip_address=request.remote_addr
            )
            db_session.add(audit)
            
            # Delete the project
            db_session.delete(project)
            db_session.commit()
            
            return jsonify({
                'success': True,
                'message': f'Project {project_id} has been deleted'
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

@project_bp.route('/api/projects/<project_id>/team', methods=['GET'])
def get_project_team(project_id):
    """Get team members for a specific project."""
    try:
        # Check if project exists
        project = db_session.query(Project).filter_by(id=project_id).first()
        if not project:
            return jsonify({
                'success': False,
                'error': f'Project with ID {project_id} not found'
            }), 404
        
        # Get team members
        team_members = db_session.query(TeamMember).filter_by(project_id=project_id).all()
        
        result = []
        for member in team_members:
            user = db_session.query(User).filter_by(id=member.user_id).first()
            if user:
                result.append({
                    'id': member.id,
                    'user_id': user.id,
                    'username': user.username,
                    'first_name': user.first_name,
                    'last_name': user.last_name,
                    'email': user.email,
                    'role': member.role,
                    'joined_at': member.joined_at.isoformat(),
                    'invited_by': member.invited_by
                })
        
        return jsonify({
            'success': True,
            'team': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@project_bp.route('/api/projects/<project_id>/team', methods=['POST'])
def add_team_member(project_id):
    """Add a team member to a project."""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['user_id', 'role', 'invited_by']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Check if project exists
        project = db_session.query(Project).filter_by(id=project_id).first()
        if not project:
            return jsonify({
                'success': False,
                'error': f'Project with ID {project_id} not found'
            }), 404
        
        # Check if user exists
        user = db_session.query(User).filter_by(id=data['user_id']).first()
        if not user:
            return jsonify({
                'success': False,
                'error': f'User with ID {data["user_id"]} not found'
            }), 404
        
        # Check if user is already a team member
        existing_member = db_session.query(TeamMember).filter_by(
            project_id=project_id, 
            user_id=data['user_id']
        ).first()
        
        if existing_member:
            return jsonify({
                'success': False,
                'error': f'User {data["user_id"]} is already a team member of this project'
            }), 400
        
        # Add team member
        team_member = TeamMember(
            id=str(uuid.uuid4()),
            user_id=data['user_id'],
            project_id=project_id,
            role=data['role'],
            invited_by=data['invited_by']
        )
        db_session.add(team_member)
        
        # Create audit log entry
        audit = AuditLog(
            id=str(uuid.uuid4()),
            action='add_team_member',
            entity_type='project',
            entity_id=project_id,
            user_id=data['invited_by'],
            details={
                'added_user_id': data['user_id'],
                'role': data['role']
            },
            ip_address=request.remote_addr
        )
        db_session.add(audit)
        
        db_session.commit()
        
        return jsonify({
            'success': True,
            'team_member': {
                'id': team_member.id,
                'user_id': team_member.user_id,
                'project_id': team_member.project_id,
                'role': team_member.role,
                'joined_at': team_member.joined_at.isoformat(),
                'invited_by': team_member.invited_by
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

@project_bp.route('/api/projects/<project_id>/team/<user_id>', methods=['DELETE'])
def remove_team_member(project_id, user_id):
    """Remove a team member from a project."""
    try:
        # Get the current user making the request
        current_user_id = request.args.get('current_user_id', 'system')
        
        # Check if project exists
        project = db_session.query(Project).filter_by(id=project_id).first()
        if not project:
            return jsonify({
                'success': False,
                'error': f'Project with ID {project_id} not found'
            }), 404
        
        # Find the team member
        team_member = db_session.query(TeamMember).filter_by(
            project_id=project_id, 
            user_id=user_id
        ).first()
        
        if not team_member:
            return jsonify({
                'success': False,
                'error': f'User {user_id} is not a team member of this project'
            }), 404
        
        # Check if the user is the owner and prevent removal if they are
        if team_member.role == 'owner':
            return jsonify({
                'success': False,
                'error': 'Cannot remove the project owner'
            }), 400
        
        # Create audit log entry before deletion
        audit = AuditLog(
            id=str(uuid.uuid4()),
            action='remove_team_member',
            entity_type='project',
            entity_id=project_id,
            user_id=current_user_id,
            details={
                'removed_user_id': user_id,
                'role': team_member.role
            },
            ip_address=request.remote_addr
        )
        db_session.add(audit)
        
        # Remove the team member
        db_session.delete(team_member)
        db_session.commit()
        
        return jsonify({
            'success': True,
            'message': f'User {user_id} has been removed from the project'
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
