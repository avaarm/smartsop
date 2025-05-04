from flask import Flask, request, jsonify
from flask_cors import CORS
import openai
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Initialize Flask app
app = Flask(__name__)
CORS(app)  # Enable CORS for all routes

# Set up OpenAI API Key
openai.api_key = os.getenv("OPENAI_API_KEY")

def create_sop_prompt(data):
    return f"""Create a detailed Standard Operating Procedure (SOP) with the following information:
Process Steps: {data.get('steps')}
Roles Involved: {data.get('roles')}
Additional Notes: {data.get('notes', 'None')}

Format the SOP with:
1. Purpose
2. Scope
3. Responsibilities
4. Safety Precautions
5. Required Materials
6. Detailed Procedure Steps
7. Quality Control
8. Documentation Requirements"""

def create_batch_record_prompt(data):
    return f"""Create a detailed Batch Record template with the following information:
Process: {data.get('steps')}
Roles: {data.get('roles')}
Additional Requirements: {data.get('notes', 'None')}

Include sections for:
1. Batch Identification
2. Material Information
3. Equipment Setup Verification
4. Process Steps with Sign-offs
5. In-Process Controls
6. Quality Checks
7. Deviation Recording
8. Final Product Details"""

@app.route('/api/generate_document', methods=['POST'])
def generate_document():
    try:
        data = request.json
        doc_type = data.get('type', 'sop')
        
        # Select appropriate prompt based on document type
        prompt = create_sop_prompt(data) if doc_type == 'sop' else create_batch_record_prompt(data)
        
        # Call the OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-4",  # Using GPT-4 for better quality
            messages=[
                {"role": "system", "content": "You are an expert in creating detailed SOPs and batch records for manufacturing and laboratory processes."},
                {"role": "user", "content": prompt}
            ],
            max_tokens=2000,
            temperature=0.7
        )
        
        # Extract the generated content
        generated_content = response.choices[0].message.content.strip()
        
        return jsonify({
            'success': True,
            'content': generated_content,
            'type': doc_type
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

if __name__ == '__main__':
    app.run(debug=True)