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

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
# Configure CORS to allow requests from Angular frontend
CORS(app, resources={
    r"/*": {
        "origins": ["http://localhost:4200", "http://localhost:4201", "http://127.0.0.1:4200", "http://127.0.0.1:4201"],
        "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization", "X-Requested-With"],
        "supports_credentials": True,
        "expose_headers": ["Content-Disposition"]
    }
})

# Create directory for generated documents
GENERATED_DOCS_DIR = os.path.join(os.path.dirname(__file__), 'generated_docs')
os.makedirs(GENERATED_DOCS_DIR, exist_ok=True)

# Initialize components
model = SOPModel()
data_collector = DataCollector()
security = SecurityManager()
data_protection = DataProtection()

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
        # Log training attempt
        data_protection.audit_log('train_model', 'user', 'manual trigger')
        
        # Get training data with minimum feedback score of 3.5 (out of 5)
        training_data = data_collector.get_training_data(min_feedback_score=3.5)
        
        if len(training_data) < 10:
            return jsonify({
                'success': False,
                'error': 'Not enough high-quality training data yet'
            }), 400
        
        # Fine-tune the model
        model.fine_tune(training_data)
        return jsonify({'success': True})
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/stats', methods=['GET'])
def get_stats():
    try:
        stats = data_collector.get_stats()
        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
        training_data = data_collector.get_training_data()
        
        if not training_data:
            return jsonify({
                'success': False,
                'error': 'No training data available'
            })
        
        # Train the model
        model.fine_tune(training_data)
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        })

if __name__ == '__main__':
    app.run(debug=True)