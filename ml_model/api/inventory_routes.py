from flask import Blueprint, request, jsonify
from sqlalchemy.exc import SQLAlchemyError
from ..inventory_models import InventoryItem, InventoryTransaction, InventoryUsage, InventoryAlert
from ..models import User, Experiment
from ..protocol_models import AuditLog
from ..db_session import db_session
import uuid
from datetime import datetime

# Create Blueprint for inventory routes
inventory_bp = Blueprint('inventory_routes', __name__)

@inventory_bp.route('/api/inventory', methods=['GET'])
def get_inventory_items():
    """Get all inventory items or filter by parameters."""
    try:
        # Get query parameters
        category = request.args.get('category')
        low_stock = request.args.get('low_stock', '').lower() == 'true'
        expired = request.args.get('expired', '').lower() == 'true'
        search = request.args.get('search', '')
        
        # Start with base query
        query = db_session.query(InventoryItem)
        
        # Apply filters if provided
        if category:
            query = query.filter(InventoryItem.category == category)
        
        if low_stock:
            query = query.filter(InventoryItem.current_quantity <= InventoryItem.min_quantity)
        
        if expired:
            now = datetime.now()
            query = query.filter(InventoryItem.expiry_date <= now)
        
        if search:
            query = query.filter(
                (InventoryItem.name.ilike(f'%{search}%')) | 
                (InventoryItem.catalog_number.ilike(f'%{search}%')) |
                (InventoryItem.supplier.ilike(f'%{search}%'))
            )
        
        # Execute query and get results
        items = query.all()
        
        # Convert to dictionary
        result = []
        for item in items:
            result.append({
                'id': item.id,
                'name': item.name,
                'category': item.category,
                'catalog_number': item.catalog_number,
                'supplier': item.supplier,
                'location': item.location,
                'current_quantity': item.current_quantity,
                'min_quantity': item.min_quantity,
                'unit': item.unit,
                'cost': item.cost,
                'currency': item.currency,
                'expiry_date': item.expiry_date.isoformat() if item.expiry_date else None,
                'date_received': item.date_received.isoformat() if item.date_received else None,
                'created_at': item.created_at.isoformat(),
                'updated_at': item.updated_at.isoformat(),
                'created_by': item.created_by,
                'metadata': item.metadata
            })
        
        return jsonify({
            'success': True,
            'inventory_items': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@inventory_bp.route('/api/inventory', methods=['POST'])
def create_inventory_item():
    """Create a new inventory item."""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['name', 'category', 'current_quantity', 'unit', 'created_by']
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
        
        # Create new inventory item
        new_item = InventoryItem(
            id=str(uuid.uuid4()),
            name=data['name'],
            category=data['category'],
            catalog_number=data.get('catalog_number', ''),
            supplier=data.get('supplier', ''),
            location=data.get('location', ''),
            current_quantity=data['current_quantity'],
            min_quantity=data.get('min_quantity', 0),
            unit=data['unit'],
            cost=data.get('cost'),
            currency=data.get('currency', 'USD'),
            expiry_date=datetime.fromisoformat(data['expiry_date']) if 'expiry_date' in data and data['expiry_date'] else None,
            date_received=datetime.fromisoformat(data['date_received']) if 'date_received' in data and data['date_received'] else datetime.now(),
            created_by=data['created_by'],
            metadata=data.get('metadata', {})
        )
        
        db_session.add(new_item)
        
        # Create initial inventory transaction
        transaction = InventoryTransaction(
            id=str(uuid.uuid4()),
            inventory_item_id=new_item.id,
            transaction_type='initial',
            quantity=new_item.current_quantity,
            previous_quantity=0,
            new_quantity=new_item.current_quantity,
            transaction_by=data['created_by'],
            notes='Initial inventory entry'
        )
        db_session.add(transaction)
        
        # Create low stock alert if needed
        if new_item.current_quantity <= new_item.min_quantity:
            alert = InventoryAlert(
                id=str(uuid.uuid4()),
                inventory_item_id=new_item.id,
                alert_type='low_stock',
                message=f'Low stock alert: {new_item.name} is below minimum quantity',
                is_resolved=False,
                created_by='system'
            )
            db_session.add(alert)
        
        # Create expiry alert if needed
        if new_item.expiry_date:
            now = datetime.now()
            days_to_expiry = (new_item.expiry_date - now).days
            if days_to_expiry <= 30:  # Alert for items expiring within 30 days
                alert = InventoryAlert(
                    id=str(uuid.uuid4()),
                    inventory_item_id=new_item.id,
                    alert_type='expiry',
                    message=f'Expiry alert: {new_item.name} will expire in {days_to_expiry} days',
                    is_resolved=False,
                    created_by='system'
                )
                db_session.add(alert)
        
        # Create audit log entry
        audit = AuditLog(
            id=str(uuid.uuid4()),
            action='create_inventory_item',
            entity_type='inventory_item',
            entity_id=new_item.id,
            user_id=data['created_by'],
            details={
                'item_name': new_item.name,
                'category': new_item.category,
                'quantity': new_item.current_quantity,
                'unit': new_item.unit
            },
            ip_address=request.remote_addr
        )
        db_session.add(audit)
        
        db_session.commit()
        
        return jsonify({
            'success': True,
            'inventory_item': {
                'id': new_item.id,
                'name': new_item.name,
                'category': new_item.category,
                'catalog_number': new_item.catalog_number,
                'supplier': new_item.supplier,
                'location': new_item.location,
                'current_quantity': new_item.current_quantity,
                'min_quantity': new_item.min_quantity,
                'unit': new_item.unit,
                'cost': new_item.cost,
                'currency': new_item.currency,
                'expiry_date': new_item.expiry_date.isoformat() if new_item.expiry_date else None,
                'date_received': new_item.date_received.isoformat() if new_item.date_received else None,
                'created_at': new_item.created_at.isoformat(),
                'updated_at': new_item.updated_at.isoformat(),
                'created_by': new_item.created_by,
                'metadata': new_item.metadata
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

@inventory_bp.route('/api/inventory/<item_id>', methods=['GET'])
def get_inventory_item(item_id):
    """Get a specific inventory item by ID."""
    try:
        item = db_session.query(InventoryItem).filter_by(id=item_id).first()
        
        if not item:
            return jsonify({
                'success': False,
                'error': f'Inventory item with ID {item_id} not found'
            }), 404
        
        # Get recent transactions
        transactions = db_session.query(InventoryTransaction).filter_by(inventory_item_id=item_id).order_by(InventoryTransaction.transaction_date.desc()).limit(10).all()
        transactions_list = []
        
        for transaction in transactions:
            transactions_list.append({
                'id': transaction.id,
                'transaction_type': transaction.transaction_type,
                'quantity': transaction.quantity,
                'previous_quantity': transaction.previous_quantity,
                'new_quantity': transaction.new_quantity,
                'transaction_date': transaction.transaction_date.isoformat(),
                'transaction_by': transaction.transaction_by,
                'notes': transaction.notes
            })
        
        # Get active alerts
        alerts = db_session.query(InventoryAlert).filter_by(inventory_item_id=item_id, is_resolved=False).all()
        alerts_list = []
        
        for alert in alerts:
            alerts_list.append({
                'id': alert.id,
                'alert_type': alert.alert_type,
                'message': alert.message,
                'created_at': alert.created_at.isoformat()
            })
        
        # Get usage history
        usages = db_session.query(InventoryUsage).filter_by(inventory_item_id=item_id).order_by(InventoryUsage.usage_date.desc()).limit(10).all()
        usages_list = []
        
        for usage in usages:
            experiment = None
            if usage.experiment_id:
                experiment = db_session.query(Experiment).filter_by(id=usage.experiment_id).first()
            
            usages_list.append({
                'id': usage.id,
                'quantity': usage.quantity,
                'usage_date': usage.usage_date.isoformat(),
                'used_by': usage.used_by,
                'experiment_id': usage.experiment_id,
                'experiment_title': experiment.title if experiment else None,
                'notes': usage.notes
            })
        
        return jsonify({
            'success': True,
            'inventory_item': {
                'id': item.id,
                'name': item.name,
                'category': item.category,
                'catalog_number': item.catalog_number,
                'supplier': item.supplier,
                'location': item.location,
                'current_quantity': item.current_quantity,
                'min_quantity': item.min_quantity,
                'unit': item.unit,
                'cost': item.cost,
                'currency': item.currency,
                'expiry_date': item.expiry_date.isoformat() if item.expiry_date else None,
                'date_received': item.date_received.isoformat() if item.date_received else None,
                'created_at': item.created_at.isoformat(),
                'updated_at': item.updated_at.isoformat(),
                'created_by': item.created_by,
                'metadata': item.metadata,
                'transactions': transactions_list,
                'alerts': alerts_list,
                'usages': usages_list
            }
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@inventory_bp.route('/api/inventory/<item_id>', methods=['PUT'])
def update_inventory_item(item_id):
    """Update a specific inventory item."""
    try:
        data = request.json
        
        # Find inventory item
        item = db_session.query(InventoryItem).filter_by(id=item_id).first()
        if not item:
            return jsonify({
                'success': False,
                'error': f'Inventory item with ID {item_id} not found'
            }), 404
        
        # Track if quantity is being updated
        old_quantity = item.current_quantity
        quantity_updated = False
        
        # Update fields
        if 'name' in data:
            item.name = data['name']
        if 'category' in data:
            item.category = data['category']
        if 'catalog_number' in data:
            item.catalog_number = data['catalog_number']
        if 'supplier' in data:
            item.supplier = data['supplier']
        if 'location' in data:
            item.location = data['location']
        if 'current_quantity' in data:
            item.current_quantity = data['current_quantity']
            quantity_updated = True
        if 'min_quantity' in data:
            item.min_quantity = data['min_quantity']
        if 'unit' in data:
            item.unit = data['unit']
        if 'cost' in data:
            item.cost = data['cost']
        if 'currency' in data:
            item.currency = data['currency']
        if 'expiry_date' in data:
            item.expiry_date = datetime.fromisoformat(data['expiry_date']) if data['expiry_date'] else None
        if 'date_received' in data:
            item.date_received = datetime.fromisoformat(data['date_received']) if data['date_received'] else None
        if 'metadata' in data:
            item.metadata = data['metadata']
        
        item.updated_at = datetime.now()
        
        # Create transaction if quantity was updated
        if quantity_updated:
            transaction_type = 'adjustment'
            if item.current_quantity > old_quantity:
                transaction_type = 'restock'
            elif item.current_quantity < old_quantity:
                transaction_type = 'withdrawal'
                
            transaction = InventoryTransaction(
                id=str(uuid.uuid4()),
                inventory_item_id=item.id,
                transaction_type=transaction_type,
                quantity=abs(item.current_quantity - old_quantity),
                previous_quantity=old_quantity,
                new_quantity=item.current_quantity,
                transaction_by=data.get('user_id', 'system'),
                notes=data.get('transaction_notes', f'Quantity updated from {old_quantity} to {item.current_quantity}')
            )
            db_session.add(transaction)
            
            # Check for low stock alert
            if item.current_quantity <= item.min_quantity:
                # Check if alert already exists
                existing_alert = db_session.query(InventoryAlert).filter_by(
                    inventory_item_id=item.id,
                    alert_type='low_stock',
                    is_resolved=False
                ).first()
                
                if not existing_alert:
                    alert = InventoryAlert(
                        id=str(uuid.uuid4()),
                        inventory_item_id=item.id,
                        alert_type='low_stock',
                        message=f'Low stock alert: {item.name} is below minimum quantity',
                        is_resolved=False,
                        created_by='system'
                    )
                    db_session.add(alert)
            else:
                # Resolve any existing low stock alerts
                db_session.query(InventoryAlert).filter_by(
                    inventory_item_id=item.id,
                    alert_type='low_stock',
                    is_resolved=False
                ).update({'is_resolved': True})
        
        # Create audit log entry
        audit = AuditLog(
            id=str(uuid.uuid4()),
            action='update_inventory_item',
            entity_type='inventory_item',
            entity_id=item.id,
            user_id=data.get('user_id', 'system'),
            details={
                'updated_fields': list(data.keys()),
                'quantity_updated': quantity_updated
            },
            ip_address=request.remote_addr
        )
        db_session.add(audit)
        
        db_session.commit()
        
        return jsonify({
            'success': True,
            'inventory_item': {
                'id': item.id,
                'name': item.name,
                'category': item.category,
                'catalog_number': item.catalog_number,
                'supplier': item.supplier,
                'location': item.location,
                'current_quantity': item.current_quantity,
                'min_quantity': item.min_quantity,
                'unit': item.unit,
                'cost': item.cost,
                'currency': item.currency,
                'expiry_date': item.expiry_date.isoformat() if item.expiry_date else None,
                'date_received': item.date_received.isoformat() if item.date_received else None,
                'created_at': item.created_at.isoformat(),
                'updated_at': item.updated_at.isoformat(),
                'created_by': item.created_by,
                'metadata': item.metadata
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

@inventory_bp.route('/api/inventory/<item_id>/transactions', methods=['POST'])
def add_inventory_transaction(item_id):
    """Add a transaction for an inventory item (restock, withdrawal, etc.)."""
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['transaction_type', 'quantity', 'transaction_by']
        for field in required_fields:
            if field not in data:
                return jsonify({
                    'success': False,
                    'error': f'Missing required field: {field}'
                }), 400
        
        # Find inventory item
        item = db_session.query(InventoryItem).filter_by(id=item_id).first()
        if not item:
            return jsonify({
                'success': False,
                'error': f'Inventory item with ID {item_id} not found'
            }), 404
        
        # Check if user exists
        user = db_session.query(User).filter_by(id=data['transaction_by']).first()
        if not user:
            return jsonify({
                'success': False,
                'error': f'User with ID {data["transaction_by"]} not found'
            }), 404
        
        # Calculate new quantity
        previous_quantity = item.current_quantity
        quantity = float(data['quantity'])
        
        if data['transaction_type'] == 'restock':
            new_quantity = previous_quantity + quantity
        elif data['transaction_type'] in ['withdrawal', 'used']:
            if quantity > previous_quantity:
                return jsonify({
                    'success': False,
                    'error': f'Insufficient quantity. Available: {previous_quantity}, Requested: {quantity}'
                }), 400
            new_quantity = previous_quantity - quantity
        else:
            # For adjustments, the quantity is the absolute value
            new_quantity = quantity
        
        # Create transaction
        transaction = InventoryTransaction(
            id=str(uuid.uuid4()),
            inventory_item_id=item_id,
            transaction_type=data['transaction_type'],
            quantity=quantity,
            previous_quantity=previous_quantity,
            new_quantity=new_quantity,
            transaction_by=data['transaction_by'],
            notes=data.get('notes', '')
        )
        db_session.add(transaction)
        
        # Update item quantity
        item.current_quantity = new_quantity
        item.updated_at = datetime.now()
        
        # Create usage record if this is for an experiment
        if data['transaction_type'] == 'used' and 'experiment_id' in data:
            # Check if experiment exists
            experiment = db_session.query(Experiment).filter_by(id=data['experiment_id']).first()
            if not experiment:
                return jsonify({
                    'success': False,
                    'error': f'Experiment with ID {data["experiment_id"]} not found'
                }), 404
            
            usage = InventoryUsage(
                id=str(uuid.uuid4()),
                inventory_item_id=item_id,
                experiment_id=data['experiment_id'],
                quantity=quantity,
                used_by=data['transaction_by'],
                notes=data.get('notes', '')
            )
            db_session.add(usage)
        
        # Check for low stock alert
        if new_quantity <= item.min_quantity:
            # Check if alert already exists
            existing_alert = db_session.query(InventoryAlert).filter_by(
                inventory_item_id=item.id,
                alert_type='low_stock',
                is_resolved=False
            ).first()
            
            if not existing_alert:
                alert = InventoryAlert(
                    id=str(uuid.uuid4()),
                    inventory_item_id=item.id,
                    alert_type='low_stock',
                    message=f'Low stock alert: {item.name} is below minimum quantity',
                    is_resolved=False,
                    created_by='system'
                )
                db_session.add(alert)
        else:
            # Resolve any existing low stock alerts
            db_session.query(InventoryAlert).filter_by(
                inventory_item_id=item.id,
                alert_type='low_stock',
                is_resolved=False
            ).update({'is_resolved': True})
        
        # Create audit log entry
        audit = AuditLog(
            id=str(uuid.uuid4()),
            action=f'inventory_{data["transaction_type"]}',
            entity_type='inventory_item',
            entity_id=item.id,
            user_id=data['transaction_by'],
            details={
                'item_name': item.name,
                'transaction_type': data['transaction_type'],
                'quantity': quantity,
                'previous_quantity': previous_quantity,
                'new_quantity': new_quantity,
                'experiment_id': data.get('experiment_id')
            },
            ip_address=request.remote_addr
        )
        db_session.add(audit)
        
        db_session.commit()
        
        return jsonify({
            'success': True,
            'transaction': {
                'id': transaction.id,
                'inventory_item_id': transaction.inventory_item_id,
                'transaction_type': transaction.transaction_type,
                'quantity': transaction.quantity,
                'previous_quantity': transaction.previous_quantity,
                'new_quantity': transaction.new_quantity,
                'transaction_date': transaction.transaction_date.isoformat(),
                'transaction_by': transaction.transaction_by,
                'notes': transaction.notes
            },
            'current_quantity': new_quantity
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

@inventory_bp.route('/api/inventory/alerts', methods=['GET'])
def get_inventory_alerts():
    """Get all active inventory alerts."""
    try:
        # Get query parameters
        alert_type = request.args.get('type')
        resolved = request.args.get('resolved', '').lower() == 'true'
        
        # Start with base query
        query = db_session.query(InventoryAlert)
        
        # Apply filters if provided
        if alert_type:
            query = query.filter(InventoryAlert.alert_type == alert_type)
        
        query = query.filter(InventoryAlert.is_resolved == resolved)
        
        # Execute query and get results
        alerts = query.all()
        
        # Convert to dictionary
        result = []
        for alert in alerts:
            # Get item details
            item = db_session.query(InventoryItem).filter_by(id=alert.inventory_item_id).first()
            
            result.append({
                'id': alert.id,
                'inventory_item_id': alert.inventory_item_id,
                'item_name': item.name if item else 'Unknown Item',
                'alert_type': alert.alert_type,
                'message': alert.message,
                'is_resolved': alert.is_resolved,
                'created_at': alert.created_at.isoformat(),
                'resolved_at': alert.resolved_at.isoformat() if alert.resolved_at else None,
                'resolved_by': alert.resolved_by
            })
        
        return jsonify({
            'success': True,
            'alerts': result
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@inventory_bp.route('/api/inventory/alerts/<alert_id>/resolve', methods=['POST'])
def resolve_inventory_alert(alert_id):
    """Resolve an inventory alert."""
    try:
        data = request.json
        
        # Validate required fields
        if 'resolved_by' not in data:
            return jsonify({
                'success': False,
                'error': 'Missing required field: resolved_by'
            }), 400
        
        # Find alert
        alert = db_session.query(InventoryAlert).filter_by(id=alert_id).first()
        if not alert:
            return jsonify({
                'success': False,
                'error': f'Alert with ID {alert_id} not found'
            }), 404
        
        # Check if already resolved
        if alert.is_resolved:
            return jsonify({
                'success': False,
                'error': 'Alert is already resolved'
            }), 400
        
        # Resolve alert
        alert.is_resolved = True
        alert.resolved_at = datetime.now()
        alert.resolved_by = data['resolved_by']
        
        # Create audit log entry
        audit = AuditLog(
            id=str(uuid.uuid4()),
            action='resolve_inventory_alert',
            entity_type='inventory_alert',
            entity_id=alert.id,
            user_id=data['resolved_by'],
            details={
                'alert_type': alert.alert_type,
                'inventory_item_id': alert.inventory_item_id
            },
            ip_address=request.remote_addr
        )
        db_session.add(audit)
        
        db_session.commit()
        
        return jsonify({
            'success': True,
            'alert': {
                'id': alert.id,
                'inventory_item_id': alert.inventory_item_id,
                'alert_type': alert.alert_type,
                'message': alert.message,
                'is_resolved': alert.is_resolved,
                'created_at': alert.created_at.isoformat(),
                'resolved_at': alert.resolved_at.isoformat(),
                'resolved_by': alert.resolved_by
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
