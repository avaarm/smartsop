from flask import Flask, request, jsonify
import openai
from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()


# Initialize Flask app
app = Flask(__name__)

# Set up OpenAI API Key 
openai.api_key = os.getenv("OPENAI_API_KEY")

# Route to generate SOP content
@app.route('/api/generate_sop', methods=['POST'])
def generate_sop():
    data = request.json #Get data from POST request
    steps = data.get('steps')
    roles = data.get('roles')

    # Create the prompt for GPT 
    prompt = f"Create an SOP for the following steps: {steps}, roles involved: {roles}"

    # Call the OpenAi GPT API 
    response = openai.Compilation.create(
        model="text-davinci-003", # You can switch to GPT-4 if desired
        prompt=prompt,
        max_tokens=300
    )

    # Extract the generated content from GPT response
    sop_content = response.choice[0].text.strip()

    # Send the response back to the frontend
    return jsonify({'sop_content': sop_content})

    # Run the Flask app
    if __name__ == '__main__':
         app.run(debug=True)