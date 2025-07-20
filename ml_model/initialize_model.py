"""
Initialize the model and download necessary files for the SmartSOP application.
This script downloads the pre-trained model and sets up the necessary directories.
"""

import os
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
import json

# Create necessary directories
os.makedirs("ml_model/saved_models/latest", exist_ok=True)

# Download and save the model
model_name = "microsoft/phi-2"
print(f"Downloading model: {model_name}")

# Initialize tokenizer and model
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name)

# Save the model and tokenizer
print("Saving model and tokenizer...")
model.save_pretrained("ml_model/saved_models/latest")
tokenizer.save_pretrained("ml_model/saved_models/latest")

# Create empty training data file
training_data = []
with open("ml_model/saved_models/training_data.json", "w") as f:
    json.dump(training_data, f)

print("Model initialization complete!")
print("You can now use the SmartSOP application with document generation.")
