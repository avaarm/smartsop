"""
Train the SmartSOP model using the generated training data.
This script handles the entire training process from data loading to model fine-tuning.
"""

import os
import json
import sys
import torch
from transformers import (
    AutoTokenizer, 
    AutoModelForCausalLM, 
    TrainingArguments, 
    Trainer,
    EarlyStoppingCallback,
    DataCollatorForLanguageModeling
)
from datasets import Dataset
import numpy as np
from datetime import datetime
import time
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ml_model/training.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("train_model")

class ModelEvaluator:
    """Class for evaluating model performance with custom metrics"""
    
    @staticmethod
    def compute_metrics(eval_pred):
        """Compute metrics for model evaluation"""
        predictions, labels = eval_pred
        
        # For text generation tasks, we can track perplexity
        # Lower perplexity means better model performance
        perplexity = torch.exp(torch.tensor(predictions.mean())).item()
        
        metrics = {
            "perplexity": perplexity,
        }
        
        return metrics

def load_training_data():
    """Load training data from the saved file"""
    try:
        # Try loading from the training_data.json file
        with open("ml_model/saved_models/training_data.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        # If that fails, try collecting from the collected_data directory
        logger.error(f"Error loading training data: {str(e)}")
        logger.info("Attempting to collect data from individual files...")
        
        # Collect data from individual files in collected_data directory
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
                        
                    # Check if the document has feedback
                    if "feedback" in doc_data and "score" in doc_data["feedback"]:
                        feedback_score = doc_data["feedback"]["score"]
                        
                        # Only include documents with feedback score >= 3.5
                        if feedback_score >= 3.5:
                            training_example = {
                                "input": doc_data["input"],
                                "output": doc_data["generated_content"],
                                "feedback_score": feedback_score
                            }
                            training_data.append(training_example)
                except Exception as e:
                    logger.error(f"Error processing {filename}: {str(e)}")
                    continue
                    
        return training_data

def prepare_dataset(training_data):
    """Convert training data to HuggingFace dataset format"""
    logger.info(f"Preparing dataset with {len(training_data)} examples")
    formatted_data = []
    
    for example in training_data:
        # Format input as a more structured prompt
        input_prompt = format_prompt(example)
        
        # Add to formatted data
        formatted_data.append({
            'text': input_prompt,
            'quality_score': example['feedback_score']
        })
    
    # Create dataset
    dataset = Dataset.from_list(formatted_data)
    
    # Split dataset into training and validation sets (80/20 split)
    split_dataset = dataset.train_test_split(test_size=0.2, seed=42)
    
    logger.info(f"Dataset prepared: {len(split_dataset['train'])} training examples, {len(split_dataset['test'])} validation examples")
    
    return split_dataset["train"], split_dataset["test"]

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

### Feedback Score: {example['feedback_score']}
"""
    
    return prompt

def train_model(training_data, model_name="microsoft/phi-2"):
    """Fine-tune the model on collected training data"""
    start_time = time.time()
    logger.info(f"Starting fine-tuning with {len(training_data)} examples")
    
    if len(training_data) < 5:
        logger.error("Not enough training data. Need at least 5 examples.")
        return None
    
    # Create save directory if it doesn't exist
    save_dir = os.path.join(os.path.dirname(__file__), 'ml_model', 'model_checkpoints')
    os.makedirs(save_dir, exist_ok=True)
    
    # Load tokenizer and model
    logger.info(f"Loading model: {model_name}")
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    
    # Configure the model for training
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token
        logger.info(f"Set padding token to {tokenizer.pad_token}")
    
    # Enable gradient checkpointing if available (saves memory)
    if hasattr(model, "gradient_checkpointing_enable"):
        model.gradient_checkpointing_enable()
        logger.info("Gradient checkpointing enabled")
    
    # Prepare datasets
    train_dataset, eval_dataset = prepare_dataset(training_data)
    
    # Tokenize the dataset
    def tokenize_function(examples):
        return tokenizer(
            examples["text"],
            padding="max_length",
            truncation=True,
            max_length=512
        )
    
    train_dataset = train_dataset.map(
        tokenize_function,
        batched=True,
        desc="Tokenizing dataset"
    )
    
    eval_dataset = eval_dataset.map(
        tokenize_function,
        batched=True,
        desc="Tokenizing dataset"
    )
    
    # Training parameters
    batch_size = 2
    gradient_accumulation_steps = 4
    learning_rate = 2e-5
    weight_decay = 0.01
    num_epochs = 3
    warmup_ratio = 0.1
    
    # Calculate training steps
    num_training_steps = (len(train_dataset) // (batch_size * gradient_accumulation_steps) + 1) * num_epochs
    warmup_steps = int(num_training_steps * warmup_ratio)
    
    # Configure training arguments
    training_args = TrainingArguments(
        output_dir=save_dir,
        num_train_epochs=num_epochs,
        per_device_train_batch_size=batch_size,
        per_device_eval_batch_size=batch_size,
        gradient_accumulation_steps=gradient_accumulation_steps,
        evaluation_strategy="steps",  # Match with save_strategy
        save_strategy="steps",       # Explicitly set save strategy
        save_steps=100,
        save_total_limit=3,
        eval_steps=50,
        load_best_model_at_end=True,
        learning_rate=learning_rate,
        weight_decay=weight_decay,
        warmup_steps=warmup_steps,
        logging_dir=os.path.join(save_dir, 'logs'),
        logging_steps=10,
        fp16=torch.cuda.is_available(),
        dataloader_num_workers=2,
        remove_unused_columns=False  # Keep all columns
    )
    
    # Create data collator
    data_collator = DataCollatorForLanguageModeling(
        tokenizer=tokenizer,
        mlm=False  # We're doing causal language modeling, not masked
    )
    
    # Define callbacks
    callbacks = [
        EarlyStoppingCallback(
            early_stopping_patience=2
        )
    ]
    
    # Define trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        data_collator=data_collator,
        callbacks=callbacks,
        compute_metrics=ModelEvaluator.compute_metrics
    )
    
    # Start training
    logger.info(f"Starting training with {len(train_dataset)} examples")
    training_results = trainer.train()
    
    # Evaluate the model
    logger.info("Evaluating model")
    eval_results = trainer.evaluate()
    
    # Save the fine-tuned model with timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    model_save_path = f"{save_dir}/{timestamp}"
    model.save_pretrained(model_save_path)
    tokenizer.save_pretrained(model_save_path)
    
    # Also save as latest
    logger.info(f"Saving model to {save_dir}/latest")
    model.save_pretrained(f"{save_dir}/latest")
    tokenizer.save_pretrained(f"{save_dir}/latest")
    
    # Calculate training time
    training_time = time.time() - start_time
    
    # Save training metrics
    metrics = {
        "training_loss": float(training_results.training_loss),
        "eval_results": {k: float(v) for k, v in eval_results.items()},
        "num_examples": len(training_data),
        "timestamp": timestamp,
        "model_save_path": model_save_path,
        "training_time_seconds": training_time,
        "training_hyperparameters": {
            "learning_rate": learning_rate,
            "batch_size": batch_size,
            "gradient_accumulation_steps": gradient_accumulation_steps,
            "num_epochs": num_epochs,
            "warmup_ratio": warmup_ratio,
            "weight_decay": weight_decay,
            "max_length": 512,
            "use_gradient_checkpointing": True,
            "fp16": torch.cuda.is_available()
        }
    }
    
    # Save metrics to file
    metrics_path = f"{save_dir}/{timestamp}_metrics.json"
    with open(metrics_path, 'w') as f:
        json.dump(metrics, f, indent=2)
    
    logger.info(f"Model fine-tuning complete. Model saved to {model_save_path}")
    logger.info(f"Training metrics: loss={metrics['training_loss']:.4f}, eval_loss={metrics['eval_results'].get('eval_loss', 'N/A')}")
    
    return metrics

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
    
    # Train the model
    try:
        metrics = train_model(training_data)
        
        if metrics:
            logger.info("\nTraining complete!")
            logger.info(f"Final training loss: {metrics['training_loss']:.4f}")
            if 'eval_results' in metrics and 'eval_loss' in metrics['eval_results']:
                logger.info(f"Final evaluation loss: {metrics['eval_results']['eval_loss']:.4f}")
            if 'eval_results' in metrics and 'perplexity' in metrics['eval_results']:
                logger.info(f"Final perplexity: {metrics['eval_results']['perplexity']:.2f}")
            logger.info(f"Model saved to: {metrics['model_save_path']}")
            logger.info(f"Training time: {metrics['training_time_seconds'] / 60:.2f} minutes")
            
            print("\n=== Training Summary ===")
            print(f"Training examples: {metrics['num_examples']}")
            print(f"Training loss: {metrics['training_loss']:.4f}")
            print(f"Training time: {metrics['training_time_seconds'] / 60:.2f} minutes")
            print(f"Model saved to: {metrics['model_save_path']}")
            print("========================")
            
    except Exception as e:
        logger.error(f"Error during training: {str(e)}")
        raise

if __name__ == "__main__":
    main()
