"""
Run the training process for the SmartSOP model using the generated training data.
This script will load the training data and fine-tune the model.
"""

import json
import os
from ml_model.enhanced_training import EnhancedTrainer
from ml_model.model import SOPModel
from ml_model.data_collector import DataCollector

def load_training_data():
    """Load training data from the saved file"""
    try:
        # Try loading from the training_data.json file
        with open("ml_model/saved_models/training_data.json", "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # If that fails, try collecting from the collected_data directory
        print("Could not load training_data.json, collecting from individual files...")
        data_collector = DataCollector()
        return data_collector.get_training_data(min_feedback_score=3.5)

def main():
    """Main function to run the training process"""
    print("Loading training data...")
    training_data = load_training_data()
    
    if not training_data:
        print("No training data found. Please generate training data first.")
        return
    
    print(f"Loaded {len(training_data)} training examples.")
    
    # Initialize the enhanced trainer with default parameters
    print("Initializing trainer...")
    trainer = EnhancedTrainer(
        model_name="microsoft/phi-2",
        save_dir="ml_model/model_checkpoints",
        max_length=512,
        use_gradient_checkpointing=True,
        learning_rate=2e-5,
        weight_decay=0.01,
        warmup_ratio=0.1,
        num_epochs=3,  # Using fewer epochs for faster training
        early_stopping_patience=2,
        batch_size=2,
        gradient_accumulation_steps=4,
        eval_steps=50,
        save_steps=100,
        fp16=True
    )
    
    # Start the fine-tuning process
    print("Starting fine-tuning process...")
    try:
        metrics = trainer.fine_tune(training_data)
        
        print("\nTraining complete!")
        print(f"Final training loss: {metrics['training_loss']:.4f}")
        if 'eval_results' in metrics and 'eval_loss' in metrics['eval_results']:
            print(f"Final evaluation loss: {metrics['eval_results']['eval_loss']:.4f}")
        if 'eval_results' in metrics and 'perplexity' in metrics['eval_results']:
            print(f"Final perplexity: {metrics['eval_results']['perplexity']:.2f}")
        print(f"Model saved to: {metrics['model_save_path']}")
        print(f"Training time: {metrics['training_time_seconds'] / 60:.2f} minutes")
        
        # Update the model in the SOPModel class
        print("\nUpdating the model for document generation...")
        model = SOPModel()
        model.load_latest_model()
        print("Model updated successfully!")
        
    except Exception as e:
        print(f"Error during training: {str(e)}")
        raise

if __name__ == "__main__":
    main()
