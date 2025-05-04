from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os
from ml_model.model import SOPModel
from ml_model.data_collector import DataCollector

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Initialize our custom model and data collector
model = SOPModel()
data_collector = DataCollector()

@app.route('/api/generate_document', methods=['POST'])
def generate_document():
    try:
        data = request.json
        doc_type = data.get('type', 'sop')
        
        # Generate document using our custom model
        generated_content = model.generate_document(data)
        
        # Save the generated document and get its path
        doc_path = data_collector.save_document(
            input_data=data,
            generated_content=generated_content,
            doc_type=doc_type,
            metadata={'model_version': 'v1'}
        )
        
        return jsonify({
            'success': True,
            'content': generated_content,
            'type': doc_type,
            'doc_id': doc_path
        })
        
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
        # Get training data with minimum feedback score of 3.5 (out of 5)
        training_data = data_collector.get_training_data(min_feedback_score=3.5)
        
        if len(training_data) < 10:
            return jsonify({
                'success': False,
                'error': 'Not enough high-quality training data yet'
            }), 400
        
        # Fine-tune the model
        model.fine_tune()
        
        return jsonify({
            'success': True,
            'message': 'Model training completed successfully'
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

if __name__ == '__main__':
    app.run(debug=True)