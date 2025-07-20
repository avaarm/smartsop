"""
Test the trained SmartSOP model by generating a document with the latest trained model.
"""

import os
import json
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch
import argparse

def load_latest_model():
    """Load the latest trained model"""
    model_dir = os.path.join('ml_model', 'model_checkpoints', 'latest')
    
    if not os.path.exists(model_dir):
        print(f"No trained model found at {model_dir}")
        print("Using the base model instead (microsoft/phi-2)")
        model_name = "microsoft/phi-2"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForCausalLM.from_pretrained(model_name)
    else:
        print(f"Loading trained model from {model_dir}")
        tokenizer = AutoTokenizer.from_pretrained(model_dir)
        model = AutoModelForCausalLM.from_pretrained(model_dir)
    
    return tokenizer, model

def generate_document(doc_type, steps, roles, notes):
    """Generate a document using the trained model"""
    tokenizer, model = load_latest_model()
    
    # Create the prompt
    prompt = f"""### Instruction:
Generate a detailed {doc_type.upper()} document based on the following information.

### Input:
Type: {doc_type}
Steps: {steps}
Roles: {roles}
Notes: {notes}

### Response:
"""
    
    # Set generation parameters
    inputs = tokenizer(prompt, return_tensors="pt")
    
    # Generate text
    with torch.no_grad():
        outputs = model.generate(
            inputs.input_ids,
            max_new_tokens=1024,
            temperature=0.7,
            top_p=0.9,
            do_sample=True,
            pad_token_id=tokenizer.eos_token_id
        )
    
    # Decode the generated text
    generated_text = tokenizer.decode(outputs[0], skip_special_tokens=True)
    
    # Extract only the response part (after "### Response:")
    response_start = generated_text.find("### Response:")
    if response_start != -1:
        response_text = generated_text[response_start + len("### Response:"):].strip()
    else:
        response_text = generated_text
    
    return response_text

def main():
    """Main function to test the trained model"""
    parser = argparse.ArgumentParser(description="Test the trained SmartSOP model")
    parser.add_argument("--type", default="sop", help="Document type (sop or batch_record)")
    parser.add_argument("--steps", default="1. Prepare equipment 2. Clean workspace 3. Document process", 
                      help="Steps for the document")
    parser.add_argument("--roles", default="Operator, Supervisor, QA Specialist", 
                      help="Roles involved in the process")
    parser.add_argument("--notes", default="Follow all safety protocols. Document any deviations.", 
                      help="Additional notes")
    parser.add_argument("--output", default="generated_document.txt", 
                      help="Output file to save the generated document")
    
    args = parser.parse_args()
    
    print(f"Generating {args.type.upper()} document with the trained model...")
    generated_document = generate_document(
        args.type, 
        args.steps, 
        args.roles, 
        args.notes
    )
    
    # Save the generated document
    with open(args.output, "w") as f:
        f.write(generated_document)
    
    print(f"Document generated and saved to {args.output}")
    print("\nGenerated document preview:")
    print("=" * 50)
    preview_length = min(500, len(generated_document))
    print(generated_document[:preview_length] + "..." if len(generated_document) > preview_length else generated_document)
    print("=" * 50)

if __name__ == "__main__":
    main()
