from flask import Blueprint, request, jsonify
from sqlalchemy.exc import SQLAlchemyError
from ..protocol_models import Protocol, ProtocolStep, ExperimentProtocol, AuditLog
from ..models import User, Experiment
from ..db_session import db_session
import uuid
from datetime import datetime

# Create Blueprint for protocol routes
protocol_bp = Blueprint('protocol_routes', __name__)

@protocol_bp.route('/api/protocols', methods=['GET'])
def get_protocols():
    """Get all protocols or filter by parameters."""
    try:
        # Get query parameters
        created_by = request.args.get('created_by')
        is_template = request.args.get('is_template', '').lower() == 'true'
        
        # Start with base query
        query = db_session.query(Protocol)
        
        # Apply filters if provided
        if created_by:
            query = query.filter(Protocol.created_by == created_by)
        
        if is_template:
            query = query.filter(Protocol.is_template == True)
        
        # Execute query and get results
        protocols = query.all()
        
        # Convert to dictionary
        result = []
        for protocol in protocols:
            result.append({
                'id': protocol.id,
                'title': protocol.title,
                'description': protocol.description,
                'version': protocol.version,
                'is_template': protocol.is_template,
                'created_at': protocol.created_at.isoformat(),
                'updated_at': protocol.updated_at.isoformat(),
                'created_by': protocol.created_by,
                'metadata': protocol.metadata
            })
        
        return jsonify({
            'success': True,
            'protocols': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@protocol_bp.route('/api/protocols', methods=['POST'])
def create_protocol():
    """Create a new protocol."""
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
        
        # Create new protocol
        new_protocol = Protocol(
            id=str(uuid.uuid4()),
            title=data['title'],
            description=data.get('description', ''),
            version=data.get('version', '1.0'),
            is_template=data.get('is_template', False),
            created_by=data['created_by'],
            metadata=data.get('metadata', {})
        )
        
        db_session.add(new_protocol)
        
        # Process protocol steps if provided
        steps = data.get('steps', [])
        created_steps = []
        
        for i, step_data in enumerate(steps):
            step = ProtocolStep(
                id=str(uuid.uuid4()),
                protocol_id=new_protocol.id,
                title=step_data.get('title', f'Step {i+1}'),
                description=step_data.get('description', ''),
                order=i + 1,
                duration=step_data.get('duration'),
                temperature=step_data.get('temperature'),
                reagents=step_data.get('reagents', []),
                equipment=step_data.get('equipment', []),
                safety_notes=step_data.get('safety_notes', ''),
                metadata=step_data.get('metadata', {})
            )
            db_session.add(step)
            created_steps.append({
                'id': step.id,
                'title': step.title,
                'description': step.description,
                'order': step.order
            })
        
        # Create audit log entry
        audit = AuditLog(
            id=str(uuid.uuid4()),
            action='create_protocol',
            entity_type='protocol',
            entity_id=new_protocol.id,
            user_id=data['created_by'],
            details={
                'protocol_title': new_protocol.title,
                'is_template': new_protocol.is_template,
                'steps_count': len(steps)
            },
            ip_address=request.remote_addr
        )
        db_session.add(audit)
        
        db_session.commit()
        
        return jsonify({
            'success': True,
            'protocol': {
                'id': new_protocol.id,
                'title': new_protocol.title,
                'description': new_protocol.description,
                'version': new_protocol.version,
                'is_template': new_protocol.is_template,
                'created_at': new_protocol.created_at.isoformat(),
                'updated_at': new_protocol.updated_at.isoformat(),
                'created_by': new_protocol.created_by,
                'metadata': new_protocol.metadata,
                'steps': created_steps
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

@protocol_bp.route('/api/protocols/<protocol_id>', methods=['GET'])
def get_protocol(protocol_id):
    """Get a specific protocol by ID."""
    try:
        protocol = db_session.query(Protocol).filter_by(id=protocol_id).first()
        
        if not protocol:
            return jsonify({
                'success': False,
                'error': f'Protocol with ID {protocol_id} not found'
            }), 404
        
        # Get protocol steps
        steps = db_session.query(ProtocolStep).filter_by(protocol_id=protocol_id).order_by(ProtocolStep.order).all()
        steps_list = []
        
        for step in steps:
            steps_list.append({
                'id': step.id,
                'title': step.title,
                'description': step.description,
                'order': step.order,
                'duration': step.duration,
                'temperature': step.temperature,
                'reagents': step.reagents,
                'equipment': step.equipment,
                'safety_notes': step.safety_notes,
                'metadata': step.metadata
            })
        
        # Get experiments using this protocol
        experiment_protocols = db_session.query(ExperimentProtocol).filter_by(protocol_id=protocol_id).all()
        experiments_list = []
        
        for exp_protocol in experiment_protocols:
            experiment = db_session.query(Experiment).filter_by(id=exp_protocol.experiment_id).first()
            if experiment:
                experiments_list.append({
                    'id': experiment.id,
                    'title': experiment.title,
                    'status': experiment.status.value if hasattr(experiment.status, 'value') else experiment.status,
                    'execution_date': exp_protocol.execution_date.isoformat() if exp_protocol.execution_date else None,
                    'execution_status': exp_protocol.status
                })
        
        return jsonify({
            'success': True,
            'protocol': {
                'id': protocol.id,
                'title': protocol.title,
                'description': protocol.description,
                'version': protocol.version,
                'is_template': protocol.is_template,
                'created_at': protocol.created_at.isoformat(),
                'updated_at': protocol.updated_at.isoformat(),
                'created_by': protocol.created_by,
                'metadata': protocol.metadata,
                'steps': steps_list,
                'experiments': experiments_list
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@protocol_bp.route('/api/protocols/<protocol_id>', methods=['PUT'])
def update_protocol(protocol_id):
    """Update a specific protocol."""
    try:
        data = request.json
        
        # Find protocol
        protocol = db_session.query(Protocol).filter_by(id=protocol_id).first()
        if not protocol:
            return jsonify({
                'success': False,
                'error': f'Protocol with ID {protocol_id} not found'
            }), 404
        
        # Update fields
        if 'title' in data:
            protocol.title = data['title']
        if 'description' in data:
            protocol.description = data['description']
        if 'version' in data:
            protocol.version = data['version']
        if 'is_template' in data:
            protocol.is_template = data['is_template']
        if 'metadata' in data:
            protocol.metadata = data['metadata']
        
        protocol.updated_at = datetime.now()
        
        # Update steps if provided
        if 'steps' in data:
            # Get existing steps
            existing_steps = db_session.query(ProtocolStep).filter_by(protocol_id=protocol_id).all()
            existing_step_ids = {step.id for step in existing_steps}
            
            # Track which steps to keep
            updated_step_ids = set()
            
            for i, step_data in enumerate(data['steps']):
                if 'id' in step_data and step_data['id'] in existing_step_ids:
                    # Update existing step
                    step = db_session.query(ProtocolStep).filter_by(id=step_data['id']).first()
                    step.title = step_data.get('title', step.title)
                    step.description = step_data.get('description', step.description)
                    step.order = i + 1
                    step.duration = step_data.get('duration', step.duration)
                    step.temperature = step_data.get('temperature', step.temperature)
                    step.reagents = step_data.get('reagents', step.reagents)
                    step.equipment = step_data.get('equipment', step.equipment)
                    step.safety_notes = step_data.get('safety_notes', step.safety_notes)
                    step.metadata = step_data.get('metadata', step.metadata)
                    updated_step_ids.add(step.id)
                else:
                    # Create new step
                    step = ProtocolStep(
                        id=str(uuid.uuid4()),
                        protocol_id=protocol_id,
                        title=step_data.get('title', f'Step {i+1}'),
                        description=step_data.get('description', ''),
                        order=i + 1,
                        duration=step_data.get('duration'),
                        temperature=step_data.get('temperature'),
                        reagents=step_data.get('reagents', []),
                        equipment=step_data.get('equipment', []),
                        safety_notes=step_data.get('safety_notes', ''),
                        metadata=step_data.get('metadata', {})
                    )
                    db_session.add(step)
            
            # Delete steps that were not updated
            for step in existing_steps:
                if step.id not in updated_step_ids:
                    db_session.delete(step)
        
        # Create audit log entry
        audit = AuditLog(
            id=str(uuid.uuid4()),
            action='update_protocol',
            entity_type='protocol',
            entity_id=protocol.id,
            user_id=data.get('user_id', 'system'),
            details={'updated_fields': list(data.keys())},
            ip_address=request.remote_addr
        )
        db_session.add(audit)
        
        db_session.commit()
        
        # Get updated steps for response
        steps = db_session.query(ProtocolStep).filter_by(protocol_id=protocol_id).order_by(ProtocolStep.order).all()
        steps_list = []
        for step in steps:
            steps_list.append({
                'id': step.id,
                'title': step.title,
                'description': step.description,
                'order': step.order,
                'duration': step.duration,
                'temperature': step.temperature,
                'reagents': step.reagents,
                'equipment': step.equipment,
                'safety_notes': step.safety_notes,
                'metadata': step.metadata
            })
        
        return jsonify({
            'success': True,
            'protocol': {
                'id': protocol.id,
                'title': protocol.title,
                'description': protocol.description,
                'version': protocol.version,
                'is_template': protocol.is_template,
                'created_at': protocol.created_at.isoformat(),
                'updated_at': protocol.updated_at.isoformat(),
                'created_by': protocol.created_by,
                'metadata': protocol.metadata,
                'steps': steps_list
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

@protocol_bp.route('/api/protocols/<protocol_id>', methods=['DELETE'])
def delete_protocol(protocol_id):
    """Delete a protocol."""
    try:
        # Get query parameters
        user_id = request.args.get('user_id', 'system')
        
        # Find protocol
        protocol = db_session.query(Protocol).filter_by(id=protocol_id).first()
        if not protocol:
            return jsonify({
                'success': False,
                'error': f'Protocol with ID {protocol_id} not found'
            }), 404
        
        # Check if protocol is used in any experiments
        experiment_protocols = db_session.query(ExperimentProtocol).filter_by(protocol_id=protocol_id).first()
        if experiment_protocols:
            return jsonify({
                'success': False,
                'error': 'Cannot delete protocol that is used in experiments'
            }), 400
        
        # Create audit log entry before deletion
        audit = AuditLog(
            id=str(uuid.uuid4()),
            action='delete_protocol',
            entity_type='protocol',
            entity_id=protocol.id,
            user_id=user_id,
            details={
                'protocol_title': protocol.title,
                'protocol_version': protocol.version
            },
            ip_address=request.remote_addr
        )
        db_session.add(audit)
        
        # Delete protocol steps first
        db_session.query(ProtocolStep).filter_by(protocol_id=protocol_id).delete()
        
        # Delete the protocol
        db_session.delete(protocol)
        db_session.commit()
        
        return jsonify({
            'success': True,
            'message': f'Protocol {protocol_id} has been deleted'
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

@protocol_bp.route('/api/experiments/<experiment_id>/protocols', methods=['POST'])
def assign_protocol_to_experiment(experiment_id):
    """Assign a protocol to an experiment."""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['protocol_id', 'assigned_by']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Check if experiment exists
        experiment = db_session.query(Experiment).filter_by(id=experiment_id).first()
        if not experiment:
            return jsonify({
                'success': False,
                'error': f'Experiment with ID {experiment_id} not found'
            }), 404
        
        # Check if protocol exists
        protocol = db_session.query(Protocol).filter_by(id=data['protocol_id']).first()
        if not protocol:
            return jsonify({
                'success': False,
                'error': f'Protocol with ID {data["protocol_id"]} not found'
            }), 404
        
        # Check if protocol is already assigned to this experiment
        existing = db_session.query(ExperimentProtocol).filter_by(
            experiment_id=experiment_id,
            protocol_id=data['protocol_id']
        ).first()
        
        if existing:
            return jsonify({
                'success': False,
                'error': 'Protocol is already assigned to this experiment'
            }), 400
        
        # Create new experiment protocol assignment
        exp_protocol = ExperimentProtocol(
            id=str(uuid.uuid4()),
            experiment_id=experiment_id,
            protocol_id=data['protocol_id'],
            status='pending',
            assigned_by=data['assigned_by'],
            execution_date=datetime.fromisoformat(data['execution_date']) if 'execution_date' in data and data['execution_date'] else None,
            notes=data.get('notes', '')
        )
        
        db_session.add(exp_protocol)
        
        # Create audit log entry
        audit = AuditLog(
            id=str(uuid.uuid4()),
            action='assign_protocol',
            entity_type='experiment_protocol',
            entity_id=exp_protocol.id,
            user_id=data['assigned_by'],
            details={
                'experiment_id': experiment_id,
                'protocol_id': data['protocol_id'],
                'protocol_title': protocol.title
            },
            ip_address=request.remote_addr
        )
        db_session.add(audit)
        
        db_session.commit()
        
        return jsonify({
            'success': True,
            'experiment_protocol': {
                'id': exp_protocol.id,
                'experiment_id': exp_protocol.experiment_id,
                'protocol_id': exp_protocol.protocol_id,
                'status': exp_protocol.status,
                'assigned_by': exp_protocol.assigned_by,
                'assigned_at': exp_protocol.assigned_at.isoformat(),
                'execution_date': exp_protocol.execution_date.isoformat() if exp_protocol.execution_date else None,
                'executed_by': exp_protocol.executed_by,
                'execution_completed_at': exp_protocol.execution_completed_at.isoformat() if exp_protocol.execution_completed_at else None,
                'notes': exp_protocol.notes
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

@protocol_bp.route('/api/experiments/<experiment_id>/protocols/<protocol_id>', methods=['PUT'])
def update_experiment_protocol(experiment_id, protocol_id):
    """Update the status of a protocol assigned to an experiment."""
    try:
        data = request.json
        
        # Find experiment protocol
        exp_protocol = db_session.query(ExperimentProtocol).filter_by(
            experiment_id=experiment_id,
            protocol_id=protocol_id
        ).first()
        
        if not exp_protocol:
            return jsonify({
                'success': False,
                'error': f'Protocol {protocol_id} not assigned to experiment {experiment_id}'
            }), 404
        
        # Update fields
        if 'status' in data:
            exp_protocol.status = data['status']
            
            # If status is completed, set execution_completed_at
            if data['status'] == 'completed':
                exp_protocol.execution_completed_at = datetime.now()
        
        if 'executed_by' in data:
            exp_protocol.executed_by = data['executed_by']
        
        if 'execution_date' in data:
            exp_protocol.execution_date = datetime.fromisoformat(data['execution_date']) if data['execution_date'] else None
        
        if 'notes' in data:
            exp_protocol.notes = data['notes']
        
        # Create audit log entry
        audit = AuditLog(
            id=str(uuid.uuid4()),
            action='update_experiment_protocol',
            entity_type='experiment_protocol',
            entity_id=exp_protocol.id,
            user_id=data.get('user_id', 'system'),
            details={
                'experiment_id': experiment_id,
                'protocol_id': protocol_id,
                'updated_fields': list(data.keys()),
                'new_status': data.get('status')
            },
            ip_address=request.remote_addr
        )
        db_session.add(audit)
        
        db_session.commit()
        
        return jsonify({
            'success': True,
            'experiment_protocol': {
                'id': exp_protocol.id,
                'experiment_id': exp_protocol.experiment_id,
                'protocol_id': exp_protocol.protocol_id,
                'status': exp_protocol.status,
                'assigned_by': exp_protocol.assigned_by,
                'assigned_at': exp_protocol.assigned_at.isoformat(),
                'execution_date': exp_protocol.execution_date.isoformat() if exp_protocol.execution_date else None,
                'executed_by': exp_protocol.executed_by,
                'execution_completed_at': exp_protocol.execution_completed_at.isoformat() if exp_protocol.execution_completed_at else None,
                'notes': exp_protocol.notes
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
