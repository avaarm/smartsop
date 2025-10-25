from flask import Blueprint, request, jsonify
from sqlalchemy.exc import SQLAlchemyError
from ..models import Project, Experiment, Task, ExperimentData, User
from ..db_session import db_session
from ..protocol_models import AuditLog, Protocol, ExperimentProtocol
import uuid
from datetime import datetime

# Create Blueprint for experiment routes
experiment_bp = Blueprint('experiment_routes', __name__)

@experiment_bp.route('/api/projects/<project_id>/experiments', methods=['GET'])
def get_experiments(project_id):
    """Get all experiments for a specific project."""
    try:
        # Check if project exists
        project = db_session.query(Project).filter_by(id=project_id).first()
        if not project:
            return jsonify({
                'success': False,
                'error': f'Project with ID {project_id} not found'
            }), 404
        
        # Get query parameters
        status = request.args.get('status')
        
        # Start with base query
        query = db_session.query(Experiment).filter_by(project_id=project_id)
        
        # Apply filters if provided
        if status:
            query = query.filter(Experiment.status == status)
        
        # Execute query and get results
        experiments = query.all()
        
        # Convert to dictionary
        result = []
        for experiment in experiments:
            result.append({
                'id': experiment.id,
                'project_id': experiment.project_id,
                'title': experiment.title,
                'hypothesis': experiment.hypothesis,
                'expected_outcome': experiment.expected_outcome,
                'status': experiment.status.value if hasattr(experiment.status, 'value') else experiment.status,
                'start_date': experiment.start_date.isoformat() if experiment.start_date else None,
                'end_date': experiment.end_date.isoformat() if experiment.end_date else None,
                'created_at': experiment.created_at.isoformat(),
                'updated_at': experiment.updated_at.isoformat(),
                'created_by': experiment.created_by,
                'metadata': experiment.metadata
            })
        
        return jsonify({
            'success': True,
            'experiments': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@experiment_bp.route('/api/projects/<project_id>/experiments', methods=['POST'])
def create_experiment(project_id):
    """Create a new experiment for a specific project."""
    try:
        data = request.json
        
        # Check if project exists
        project = db_session.query(Project).filter_by(id=project_id).first()
        if not project:
            return jsonify({
                'success': False,
                'error': f'Project with ID {project_id} not found'
            }), 404
        
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
        
        # Create new experiment
        new_experiment = Experiment(
            id=str(uuid.uuid4()),
            project_id=project_id,
            title=data['title'],
            hypothesis=data.get('hypothesis', ''),
            expected_outcome=data.get('expected_outcome', ''),
            status=data.get('status', 'planned'),
            start_date=datetime.fromisoformat(data['start_date']) if 'start_date' in data and data['start_date'] else None,
            end_date=datetime.fromisoformat(data['end_date']) if 'end_date' in data and data['end_date'] else None,
            created_by=data['created_by'],
            metadata=data.get('metadata', {})
        )
        
        db_session.add(new_experiment)
        
        # Create audit log entry
        audit = AuditLog(
            id=str(uuid.uuid4()),
            action='create_experiment',
            entity_type='experiment',
            entity_id=new_experiment.id,
            user_id=data['created_by'],
            details={
                'experiment_title': new_experiment.title,
                'project_id': project_id
            },
            ip_address=request.remote_addr
        )
        db_session.add(audit)
        
        db_session.commit()
        
        return jsonify({
            'success': True,
            'experiment': {
                'id': new_experiment.id,
                'project_id': new_experiment.project_id,
                'title': new_experiment.title,
                'hypothesis': new_experiment.hypothesis,
                'expected_outcome': new_experiment.expected_outcome,
                'status': new_experiment.status.value if hasattr(new_experiment.status, 'value') else new_experiment.status,
                'start_date': new_experiment.start_date.isoformat() if new_experiment.start_date else None,
                'end_date': new_experiment.end_date.isoformat() if new_experiment.end_date else None,
                'created_at': new_experiment.created_at.isoformat(),
                'updated_at': new_experiment.updated_at.isoformat(),
                'created_by': new_experiment.created_by,
                'metadata': new_experiment.metadata
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

@experiment_bp.route('/api/experiments/<experiment_id>', methods=['GET'])
def get_experiment(experiment_id):
    """Get a specific experiment by ID."""
    try:
        experiment = db_session.query(Experiment).filter_by(id=experiment_id).first()
        
        if not experiment:
            return jsonify({
                'success': False,
                'error': f'Experiment with ID {experiment_id} not found'
            }), 404
        
        # Get tasks for this experiment
        tasks = db_session.query(Task).filter_by(experiment_id=experiment_id).all()
        tasks_list = []
        for task in tasks:
            tasks_list.append({
                'id': task.id,
                'title': task.title,
                'description': task.description,
                'status': task.status.value if hasattr(task.status, 'value') else task.status,
                'assigned_to': task.assigned_to,
                'due_date': task.due_date.isoformat() if task.due_date else None,
                'created_at': task.created_at.isoformat(),
                'updated_at': task.updated_at.isoformat(),
                'priority': task.priority.value if hasattr(task.priority, 'value') else task.priority
            })
        
        # Get protocols for this experiment
        experiment_protocols = db_session.query(ExperimentProtocol).filter_by(experiment_id=experiment_id).all()
        protocols_list = []
        for exp_protocol in experiment_protocols:
            protocol = db_session.query(Protocol).filter_by(id=exp_protocol.protocol_id).first()
            if protocol:
                protocols_list.append({
                    'id': protocol.id,
                    'title': protocol.title,
                    'description': protocol.description,
                    'version': protocol.version,
                    'execution_date': exp_protocol.execution_date.isoformat() if exp_protocol.execution_date else None,
                    'status': exp_protocol.status,
                    'executed_by': exp_protocol.executed_by
                })
        
        # Get experiment data
        data_entries = db_session.query(ExperimentData).filter_by(experiment_id=experiment_id).all()
        data_list = []
        for entry in data_entries:
            data_list.append({
                'id': entry.id,
                'title': entry.title,
                'data_type': entry.data_type,
                'value': entry.value,
                'unit': entry.unit,
                'timestamp': entry.timestamp.isoformat(),
                'created_by': entry.created_by,
                'metadata': entry.metadata
            })
        
        return jsonify({
            'success': True,
            'experiment': {
                'id': experiment.id,
                'project_id': experiment.project_id,
                'title': experiment.title,
                'hypothesis': experiment.hypothesis,
                'expected_outcome': experiment.expected_outcome,
                'status': experiment.status.value if hasattr(experiment.status, 'value') else experiment.status,
                'start_date': experiment.start_date.isoformat() if experiment.start_date else None,
                'end_date': experiment.end_date.isoformat() if experiment.end_date else None,
                'created_at': experiment.created_at.isoformat(),
                'updated_at': experiment.updated_at.isoformat(),
                'created_by': experiment.created_by,
                'metadata': experiment.metadata,
                'tasks': tasks_list,
                'protocols': protocols_list,
                'data': data_list
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@experiment_bp.route('/api/experiments/<experiment_id>', methods=['PUT'])
def update_experiment(experiment_id):
    """Update a specific experiment."""
    try:
        data = request.json
        
        # Find experiment
        experiment = db_session.query(Experiment).filter_by(id=experiment_id).first()
        if not experiment:
            return jsonify({
                'success': False,
                'error': f'Experiment with ID {experiment_id} not found'
            }), 404
        
        # Update fields
        if 'title' in data:
            experiment.title = data['title']
        if 'hypothesis' in data:
            experiment.hypothesis = data['hypothesis']
        if 'expected_outcome' in data:
            experiment.expected_outcome = data['expected_outcome']
        if 'status' in data:
            experiment.status = data['status']
        if 'start_date' in data:
            experiment.start_date = datetime.fromisoformat(data['start_date']) if data['start_date'] else None
        if 'end_date' in data:
            experiment.end_date = datetime.fromisoformat(data['end_date']) if data['end_date'] else None
        if 'metadata' in data:
            experiment.metadata = data['metadata']
        
        experiment.updated_at = datetime.now()
        
        # Create audit log entry
        audit = AuditLog(
            id=str(uuid.uuid4()),
            action='update_experiment',
            entity_type='experiment',
            entity_id=experiment.id,
            user_id=data.get('user_id', 'system'),
            details={'updated_fields': list(data.keys())},
            ip_address=request.remote_addr
        )
        db_session.add(audit)
        
        db_session.commit()
        
        return jsonify({
            'success': True,
            'experiment': {
                'id': experiment.id,
                'project_id': experiment.project_id,
                'title': experiment.title,
                'hypothesis': experiment.hypothesis,
                'expected_outcome': experiment.expected_outcome,
                'status': experiment.status.value if hasattr(experiment.status, 'value') else experiment.status,
                'start_date': experiment.start_date.isoformat() if experiment.start_date else None,
                'end_date': experiment.end_date.isoformat() if experiment.end_date else None,
                'created_at': experiment.created_at.isoformat(),
                'updated_at': experiment.updated_at.isoformat(),
                'created_by': experiment.created_by,
                'metadata': experiment.metadata
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

@experiment_bp.route('/api/experiments/<experiment_id>', methods=['DELETE'])
def delete_experiment(experiment_id):
    """Delete an experiment."""
    try:
        # Get query parameters
        user_id = request.args.get('user_id', 'system')
        
        # Find experiment
        experiment = db_session.query(Experiment).filter_by(id=experiment_id).first()
        if not experiment:
            return jsonify({
                'success': False,
                'error': f'Experiment with ID {experiment_id} not found'
            }), 404
        
        # Create audit log entry before deletion
        audit = AuditLog(
            id=str(uuid.uuid4()),
            action='delete_experiment',
            entity_type='experiment',
            entity_id=experiment.id,
            user_id=user_id,
            details={
                'experiment_title': experiment.title,
                'project_id': experiment.project_id
            },
            ip_address=request.remote_addr
        )
        db_session.add(audit)
        
        # Delete the experiment
        db_session.delete(experiment)
        db_session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Experiment {experiment_id} has been deleted'
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

@experiment_bp.route('/api/experiments/<experiment_id>/data', methods=['GET'])
def get_experiment_data(experiment_id):
    """Get all data entries for a specific experiment."""
    try:
        # Check if experiment exists
        experiment = db_session.query(Experiment).filter_by(id=experiment_id).first()
        if not experiment:
            return jsonify({
                'success': False,
                'error': f'Experiment with ID {experiment_id} not found'
            }), 404
        
        # Get data entries
        data_entries = db_session.query(ExperimentData).filter_by(experiment_id=experiment_id).all()
        
        result = []
        for entry in data_entries:
            result.append({
                'id': entry.id,
                'experiment_id': entry.experiment_id,
                'title': entry.title,
                'data_type': entry.data_type,
                'value': entry.value,
                'unit': entry.unit,
                'timestamp': entry.timestamp.isoformat(),
                'created_by': entry.created_by,
                'metadata': entry.metadata
            })
        
        return jsonify({
            'success': True,
            'data': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@experiment_bp.route('/api/experiments/<experiment_id>/data', methods=['POST'])
def add_experiment_data(experiment_id):
    """Add a new data entry to an experiment."""
    try:
        data = request.json
        
        # Check if experiment exists
        experiment = db_session.query(Experiment).filter_by(id=experiment_id).first()
        if not experiment:
            return jsonify({
                'success': False,
                'error': f'Experiment with ID {experiment_id} not found'
            }), 404
        
        # Validate required fields
        required_fields = ['title', 'data_type', 'value', 'created_by']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Create new data entry
        new_data = ExperimentData(
            id=str(uuid.uuid4()),
            experiment_id=experiment_id,
            title=data['title'],
            data_type=data['data_type'],
            value=data['value'],
            unit=data.get('unit'),
            created_by=data['created_by'],
            metadata=data.get('metadata', {})
        )
        
        db_session.add(new_data)
        
        # Create audit log entry
        audit = AuditLog(
            id=str(uuid.uuid4()),
            action='add_experiment_data',
            entity_type='experiment_data',
            entity_id=new_data.id,
            user_id=data['created_by'],
            details={
                'data_title': new_data.title,
                'experiment_id': experiment_id,
                'data_type': new_data.data_type
            },
            ip_address=request.remote_addr
        )
        db_session.add(audit)
        
        db_session.commit()
        
        return jsonify({
            'success': True,
            'data': {
                'id': new_data.id,
                'experiment_id': new_data.experiment_id,
                'title': new_data.title,
                'data_type': new_data.data_type,
                'value': new_data.value,
                'unit': new_data.unit,
                'timestamp': new_data.timestamp.isoformat(),
                'created_by': new_data.created_by,
                'metadata': new_data.metadata
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
