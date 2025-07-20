"""
Simple training script for SmartSOP model using the generated training data.
This script uses a more basic approach that should work with most versions of the transformers library.
"""

import os
import json
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, Trainer, TrainingArguments
from datasets import Dataset
import logging
from datetime import datetime
import time

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("simple_train")

def load_training_data():
    """Load training data from the saved file"""
    try:
        # Try loading from the training_data.json file
        with open("ml_model/saved_models/training_data.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.error("Could not load training_data.json")
        
        # Try collecting from individual files
        training_data = []
        collected_data_dir = "collected_data"
        
        if not os.path.exists(collected_data_dir):
            logger.error(f"Directory {collected_data_dir} does not exist")
            return []
            
        for filename in os.listdir(collected_data_dir):
            if filename.endswith(".json"):
                try:
                    with open(os.path.join(collected_data_dir, filename), "r") as f:
                        doc_data = json.load(f)
                        
                    if "feedback" in doc_data and "score" in doc_data["feedback"]:
                        feedback_score = doc_data["feedback"]["score"]
                        if feedback_score >= 3.5:
                            training_example = {
                                "input": doc_data["input"],
                                "output": doc_data["generated_content"],
                                "feedback_score": feedback_score
                            }
                            training_data.append(training_example)
                except Exception as e:
                    logger.error(f"Error processing {filename}: {str(e)}")
                    
        return training_data

def format_prompt(example):
    """Format a training example as a prompt"""
    # Get input data
    input_data = example['input']
    doc_type = input_data.get('type', example.get('type', 'sop'))
    steps = input_data.get('steps', '')
    roles = input_data.get('roles', '')
    notes = input_data.get('notes', '')
    
    # Format prompt with clear instruction
    prompt = f"""### Instruction:
Generate a detailed {doc_type.upper()} document based on the following information.

### Input:
Type: {doc_type}
Steps: {steps}
Roles: {roles}
Notes: {notes}

### Response:
{example['output']}
"""
    
    return prompt

def main():
    """Main function to run the training process"""
    logger.info("Starting SmartSOP model training")
    
    # Load training data
    logger.info("Loading training data...")
    training_data = load_training_data()
    
    if not training_data:
        logger.error("No training data found. Please generate training data first.")
        return
    
    logger.info(f"Loaded {len(training_data)} training examples.")
    
    # Create save directory
    save_dir = os.path.join('ml_model', 'model_checkpoints')
    os.makedirs(save_dir, exist_ok=True)
    
    # Load model and tokenizer
    model_name = "microsoft/phi-2"
    logger.info(f"Loading model: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    
    # Set padding token if needed
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
    
    # Prepare dataset
    formatted_data = []
    for example in training_data:
        formatted_data.append({"text": format_prompt(example)})
    
    dataset = Dataset.from_list(formatted_data)
    
    # Split dataset
    split_dataset = dataset.train_test_split(test_size=0.2, seed=42)
    train_dataset = split_dataset["train"]
    eval_dataset = split_dataset["test"]
    
    logger.info(f"Dataset prepared: {len(train_dataset)} training examples, {len(eval_dataset)} validation examples")
    
    # Tokenize dataset
    def tokenize_function(examples):
        return tokenizer(
            examples["text"],
            padding="max_length",
            truncation=True,
            max_length=512
        )
    
    train_dataset = train_dataset.map(tokenize_function, batched=True)
    eval_dataset = eval_dataset.map(tokenize_function, batched=True)
    
    # Set up training arguments
    training_args = TrainingArguments(
        output_dir=save_dir,
        num_train_epochs=3,
        per_device_train_batch_size=2,
        per_device_eval_batch_size=2,
        learning_rate=2e-5,
        weight_decay=0.01,
        logging_dir=os.path.join(save_dir, 'logs'),
        logging_steps=10,
    )
    
    # Create trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
    )
    
    # Start training
    logger.info("Starting training...")
    start_time = time.time()
    
    try:
        trainer.train()
        
        # Save the model
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        model_save_path = f"{save_dir}/{timestamp}"
        model.save_pretrained(model_save_path)
        tokenizer.save_pretrained(model_save_path)
        
        # Also save as latest
        model.save_pretrained(f"{save_dir}/latest")
        tokenizer.save_pretrained(f"{save_dir}/latest")
        
        # Calculate training time
        training_time = time.time() - start_time
        
        # Log results
        logger.info(f"Training complete! Model saved to {model_save_path}")
        logger.info(f"Training time: {training_time / 60:.2f} minutes")
        
        print("\n=== Training Summary ===")
        print(f"Training examples: {len(training_data)}")
        print(f"Training time: {training_time / 60:.2f} minutes")
        print(f"Model saved to: {model_save_path}")
        print("========================")
        
    except Exception as e:
        logger.error(f"Error during training: {str(e)}")
        raise

if __name__ == "__main__":
    main()
