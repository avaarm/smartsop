from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from dotenv import load_dotenv
import os
import json
import uuid
from ml_model.model import SOPModel
from ml_model.data_collector import DataCollector
from ml_model.security import SecurityManager, DataProtection
from ml_model.word_generator import WordDocumentGenerator
from ml_model.document_exporter import DocumentExporter
from ml_model.web_data_collector import generate_training_examples as generate_web_training_examples
from ml_model.web_data_collector import save_training_data as save_web_training_data

# Import database and API routes
from ml_model.database import engine, Base
from ml_model.db_session import init_db_session
from ml_model.api import register_api_routes

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
# Configure CORS to allow requests from Angular frontend
# Using a simpler configuration for development purposes
CORS(app, origins=["http://localhost:4200", "http://localhost:4201", "http://127.0.0.1:4200", "http://127.0.0.1:4201"], 
     supports_credentials=True, 
     allow_headers=["Content-Type", "Authorization", "X-Requested-With"],
     expose_headers=["Content-Disposition"])

# Create directory for generated documents
GENERATED_DOCS_DIR = os.path.join(os.path.dirname(__file__), 'generated_docs')
os.makedirs(GENERATED_DOCS_DIR, exist_ok=True)

# Initialize database session
db_session = init_db_session(app)

# Register API routes
register_api_routes(app)

# Initialize components
model = SOPModel()
data_collector = DataCollector()
security = SecurityManager()
data_protection = DataProtection()
document_exporter = DocumentExporter(output_dir=GENERATED_DOCS_DIR)

@app.route('/api/generate_document', methods=['POST'])
def generate_document():
    try:
        data = request.json
        doc_type = data.get('type', 'sop')
        
        # Generate document using our custom model
        generated_content, word_doc_path, template_type = model.generate_document(data)
        
        # Sanitize any sensitive information
        data = data_protection.sanitize_training_data(data)
        
        # Save the generated document and get its path
        doc_path = data_collector.save_document(
            input_data=data,
            generated_content=generated_content,
            doc_type=doc_type,
            metadata={
                'model_version': 'v1',
                'template_type': template_type,
                'word_doc_path': word_doc_path
            }
        )
        
        # Log the generation
        data_protection.audit_log('generate_document', 'user', f'type: {doc_type}')
        
        # Prepare response
        response_data = {
            'success': True,
            'content': generated_content,
            'type': doc_type,
            'doc_id': doc_path
        }
        
        # Add Word document download link if available
        if word_doc_path:
            # Get just the filename from the path
            word_doc_filename = os.path.basename(word_doc_path)
            response_data['word_document'] = {
                'available': True,
                'filename': word_doc_filename,
                'download_url': f'/api/download/{word_doc_filename}'
            }
        
        return jsonify(response_data)
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/download/<filename>', methods=['GET'])
def download_document(filename):
    """Endpoint to download generated Word documents"""
    try:
        # Security check to prevent directory traversal attacks
        if '..' in filename or filename.startswith('/'):
            return jsonify({
                'success': False,
                'error': 'Invalid filename'
            }), 400
            
        # Path to the document
        file_path = os.path.join(GENERATED_DOCS_DIR, filename)
        
        # Check if file exists
        if not os.path.exists(file_path):
            return jsonify({
                'success': False,
                'error': 'File not found'
            }), 404
            
        # Log the download
        data_protection.audit_log('download_document', 'user', f'filename: {filename}')
        
        # Send the file with proper MIME type for Word documents
        return send_file(
            file_path, 
            mimetype='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
            as_attachment=True, 
            download_name=filename
        )
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/feedback', methods=['POST'])
def submit_feedback():
    try:
        data = request.json
        doc_path = data.get('doc_id')
        feedback_score = data.get('score')
        feedback_text = data.get('text')
        
        if not doc_path or feedback_score is None:
            return jsonify({
                'success': False,
                'error': 'Missing required fields'
            }), 400
        
        # Log feedback submission
        data_protection.audit_log('submit_feedback', 'user', f'doc_id: {doc_path}')
        
        # Add feedback to the document
        data_collector.add_feedback(
            doc_path=doc_path,
            feedback_score=feedback_score,
            feedback_text=feedback_text
        )
        
        # Add to model's training data
        with open(doc_path, 'r') as f:
            doc_data = json.load(f)
            model.add_training_example(
                input_data=doc_data['input'],
                generated_sop=doc_data['generated_content'],
                feedback_score=feedback_score
            )
        
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/train', methods=['POST'])
def train_model():
    try:
        # Get request parameters
        data = request.json or {}
        min_feedback_score = data.get('min_feedback_score', 3.5)  # Default to 3.5 out of 5
        min_examples = data.get('min_examples', 10)  # Default to requiring at least 10 examples
        
        # Log training attempt
        data_protection.audit_log('train_model', 'user', f'manual trigger with min_score={min_feedback_score}')
        
        # Get training data with minimum feedback score
        training_data = data_collector.get_training_data(min_feedback_score=min_feedback_score)
        
        # Check if we have enough data
        if len(training_data) < min_examples:
            return jsonify({
                'success': False,
                'error': f'Not enough high-quality training data yet. Found {len(training_data)} examples, need at least {min_examples}.',
                'available_examples': len(training_data)
            }), 400
        
        # Start training in a background thread to avoid blocking the API
        def train_in_background():
            try:
                print(f"Starting model training with {len(training_data)} examples...")
                # Fine-tune the model with the collected training data
                metrics = model.fine_tune(training_data)
                print(f"Training complete. Final loss: {metrics['training_loss']}")
                # Log successful training
                data_protection.audit_log('train_model_complete', 'system', 
                                         f'Training completed with {len(training_data)} examples')
            except Exception as e:
                print(f"Error during training: {str(e)}")
                # Log training error
                data_protection.audit_log('train_model_error', 'system', f'Error: {str(e)}')
        
        # Start training in background thread
        import threading
        training_thread = threading.Thread(target=train_in_background)
        training_thread.daemon = True
        training_thread.start()
        
        # Return success immediately
        return jsonify({
            'success': True,
            'message': f'Training started with {len(training_data)} examples. This process will continue in the background.',
            'num_examples': len(training_data)
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        stats = data_collector.get_statistics()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/training/status', methods=['GET'])
def get_training_status():
    try:
        # Get training metrics from saved files
        metrics_files = []
        save_dir = os.path.join(os.path.dirname(__file__), 'ml_model', 'model_checkpoints')
        
        # Check if directory exists
        if not os.path.exists(save_dir):
            return jsonify({
                'success': True,
                'training_history': [],
                'is_training_in_progress': False
            })
        
        # Look for metrics files
        for filename in os.listdir(save_dir):
            if filename.endswith('_metrics.json'):
                with open(os.path.join(save_dir, filename), 'r') as f:
                    metrics = json.load(f)
                    metrics_files.append(metrics)
        
        # Sort by timestamp (newest first)
        metrics_files.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        # Check if training is in progress
        import threading
        is_training = any(t.name == 'train_in_background' and t.is_alive() for t in threading.enumerate())
        
        return jsonify({
            'success': True,
            'training_history': metrics_files,
            'is_training_in_progress': is_training,
            'latest_model': metrics_files[0]['model_save_path'] if metrics_files else None
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/collect_web_data', methods=['POST'])
def collect_web_data():
    try:
        # Log the request
        data_protection.audit_log('collect_web_data', 'user', 'manual trigger')
        
        # Generate training examples from web data
        training_data = generate_web_training_examples()
        
        # Save the training data
        save_web_training_data(training_data)
        
        return jsonify({
            'success': True,
            'message': f'Successfully collected {len(training_data)} new training examples from web sources.'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/export/<format_type>', methods=['POST'])
def export_document(format_type):
    """
    Export a document to specified format (pdf, excel, csv)
    Expects JSON payload with: content, title, doc_id
    """
    try:
        data = request.json
        content = data.get('content')
        title = data.get('title', 'SOP Document')
        doc_id = data.get('doc_id')
        
        if not content:
            return jsonify({
                'success': False,
                'error': 'Content is required'
            }), 400
        
        # Validate format type
        if format_type.lower() not in document_exporter.get_available_formats():
            return jsonify({
                'success': False,
                'error': f'Unsupported format: {format_type}'
            }), 400
        
        # Log the export
        data_protection.audit_log('export_document', 'user', f'format: {format_type}, doc_id: {doc_id}')
        
        # Export document
        filepath, filename = document_exporter.export_document(
            content=content,
            format_type=format_type,
            title=title,
            doc_id=doc_id
        )
        
        return jsonify({
            'success': True,
            'filename': filename,
            'download_url': f'/api/download/{filename}'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/export/formats', methods=['GET'])
def get_export_formats():
    """Get list of available export formats"""
    try:
        return jsonify({
            'success': True,
            'formats': document_exporter.get_available_formats()
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='SmartSOP Flask Backend')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the server on')
    args = parser.parse_args()
    
    app.run(debug=True, port=args.port)
