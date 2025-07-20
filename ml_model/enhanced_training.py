"""
Enhanced training module for SmartSOP application.
This module provides advanced training capabilities for fine-tuning language models.
"""

import torch
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
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
import json
import os
import time
from datetime import datetime
from typing import List, Dict, Tuple, Optional, Union, Any
import logging
from sklearn.metrics import accuracy_score, precision_recall_fscore_support

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ml_model/training.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("enhanced_training")

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

class EnhancedTrainer:
    """Enhanced training capabilities for SmartSOP models"""
    
    def __init__(
        self, 
        model_name: str = "microsoft/phi-2",
        save_dir: str = "ml_model/model_checkpoints",
        max_length: int = 512,
        use_gradient_checkpointing: bool = True,
        learning_rate: float = 2e-5,
        weight_decay: float = 0.01,
        warmup_ratio: float = 0.1,
        num_epochs: int = 5,
        early_stopping_patience: int = 3,
        batch_size: int = 2,
        gradient_accumulation_steps: int = 4,
        eval_steps: int = 50,
        save_steps: int = 100,
        fp16: bool = True
    ):
        """Initialize the enhanced trainer
        
        Args:
            model_name: Name or path of the pre-trained model
            save_dir: Directory to save model checkpoints
            max_length: Maximum sequence length for tokenization
            use_gradient_checkpointing: Whether to use gradient checkpointing to save memory
            learning_rate: Learning rate for training
            weight_decay: Weight decay for regularization
            warmup_ratio: Ratio of warmup steps
            num_epochs: Number of training epochs
            early_stopping_patience: Number of evaluations with no improvement before stopping
            batch_size: Batch size for training
            gradient_accumulation_steps: Number of steps to accumulate gradients
            eval_steps: Number of steps between evaluations
            save_steps: Number of steps between saving checkpoints
            fp16: Whether to use mixed precision training
        """
        self.model_name = model_name
        self.save_dir = save_dir
        self.max_length = max_length
        self.use_gradient_checkpointing = use_gradient_checkpointing
        self.learning_rate = learning_rate
        self.weight_decay = weight_decay
        self.warmup_ratio = warmup_ratio
        self.num_epochs = num_epochs
        self.early_stopping_patience = early_stopping_patience
        self.batch_size = batch_size
        self.gradient_accumulation_steps = gradient_accumulation_steps
        self.eval_steps = eval_steps
        self.save_steps = save_steps
        self.fp16 = fp16 and torch.cuda.is_available()
        
        # Create save directory if it doesn't exist
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
        
        # Load tokenizer and model
        logger.info(f"Loading model: {model_name}")
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name)
        
        # Configure the model for training
        self._configure_model()
        
        logger.info("Enhanced trainer initialized successfully")
    
    def _configure_model(self):
        """Configure the model for training"""
        # Enable gradient checkpointing if requested (saves memory)
        if self.use_gradient_checkpointing and hasattr(self.model, "gradient_checkpointing_enable"):
            self.model.gradient_checkpointing_enable()
            logger.info("Gradient checkpointing enabled")
        
        # Set padding token if not set
        if self.tokenizer.pad_token is None:
            self.tokenizer.pad_token = self.tokenizer.eos_token
            logger.info(f"Set padding token to {self.tokenizer.pad_token}")
    
    def _prepare_dataset(self, training_data: List[Dict]) -> Tuple[Dataset, Dataset]:
        """Convert training data to HuggingFace dataset format
        
        Args:
            training_data: List of training examples
            
        Returns:
            Tuple of training and validation datasets
        """
        logger.info(f"Preparing dataset with {len(training_data)} examples")
        formatted_data = []
        
        for example in training_data:
            # Format input as a more structured prompt
            input_prompt = self._format_prompt(example)
            
            # Add to formatted data
            formatted_data.append({
                'text': input_prompt,
                'quality_score': example['feedback_score']
            })
        
        # Create dataset
        dataset = Dataset.from_list(formatted_data)
        
        # Tokenize the dataset
        def tokenize_function(examples):
            return self.tokenizer(
                examples["text"],
                padding="max_length",
                truncation=True,
                max_length=self.max_length
            )
        
        tokenized_dataset = dataset.map(
            tokenize_function,
            batched=True,
            desc="Tokenizing dataset"
        )
        
        # Split dataset into training and validation sets (80/20 split)
        split_dataset = tokenized_dataset.train_test_split(test_size=0.2, seed=42)
        
        logger.info(f"Dataset prepared: {len(split_dataset['train'])} training examples, {len(split_dataset['test'])} validation examples")
        
        return split_dataset["train"], split_dataset["test"]
    
    def _format_prompt(self, example: Dict) -> str:
        """Format a training example as a prompt
        
        Args:
            example: Training example
            
        Returns:
            Formatted prompt
        """
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
    
    def fine_tune(self, training_data: List[Dict]) -> Dict[str, Any]:
        """Fine-tune the model on collected training data
        
        Args:
            training_data: List of training examples
        
        Returns:
            dict: Training metrics and results
        """
        start_time = time.time()
        logger.info(f"Starting fine-tuning with {len(training_data)} examples")
        
        if len(training_data) < 10:
            raise ValueError("Not enough training data. Need at least 10 examples.")
        
        # Prepare datasets
        train_dataset, eval_dataset = self._prepare_dataset(training_data)
        
        # Calculate training steps
        num_training_steps = (len(train_dataset) // (self.batch_size * self.gradient_accumulation_steps) + 1) * self.num_epochs
        warmup_steps = int(num_training_steps * self.warmup_ratio)
        
        # Configure training arguments
        training_args = TrainingArguments(
            output_dir=self.save_dir,
            num_train_epochs=self.num_epochs,
            per_device_train_batch_size=self.batch_size,
            per_device_eval_batch_size=self.batch_size,
            gradient_accumulation_steps=self.gradient_accumulation_steps,
            save_steps=self.save_steps,
            save_total_limit=3,
            evaluation_strategy="steps",
            eval_steps=self.eval_steps,
            load_best_model_at_end=True,
            metric_for_best_model="eval_loss",
            greater_is_better=False,
            learning_rate=self.learning_rate,
            weight_decay=self.weight_decay,
            warmup_steps=warmup_steps,
            logging_dir=os.path.join(self.save_dir, 'logs'),
            logging_steps=10,
            report_to="none",
            fp16=self.fp16,
            dataloader_num_workers=2,
            remove_unused_columns=False,  # Keep all columns
        )
        
        # Create data collator
        data_collator = DataCollatorForLanguageModeling(
            tokenizer=self.tokenizer,
            mlm=False  # We're doing causal language modeling, not masked
        )
        
        # Define callbacks
        callbacks = [
            EarlyStoppingCallback(
                early_stopping_patience=self.early_stopping_patience
            )
        ]
        
        # Define trainer
        trainer = Trainer(
            model=self.model,
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
        model_save_path = f"{self.save_dir}/{timestamp}"
        self.model.save_pretrained(model_save_path)
        self.tokenizer.save_pretrained(model_save_path)
        
        # Also save as latest
        logger.info(f"Saving model to {self.save_dir}/latest")
        self.model.save_pretrained(f"{self.save_dir}/latest")
        self.tokenizer.save_pretrained(f"{self.save_dir}/latest")
        
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
                "learning_rate": self.learning_rate,
                "batch_size": self.batch_size,
                "gradient_accumulation_steps": self.gradient_accumulation_steps,
                "num_epochs": self.num_epochs,
                "warmup_ratio": self.warmup_ratio,
                "weight_decay": self.weight_decay,
                "max_length": self.max_length,
                "use_gradient_checkpointing": self.use_gradient_checkpointing,
                "fp16": self.fp16
            }
        }
        
        # Save metrics to file
        metrics_path = f"{self.save_dir}/{timestamp}_metrics.json"
        with open(metrics_path, 'w') as f:
            json.dump(metrics, f, indent=2)
        
        logger.info(f"Model fine-tuning complete. Model saved to {model_save_path}")
        logger.info(f"Training metrics: loss={metrics['training_loss']:.4f}, eval_loss={metrics['eval_results'].get('eval_loss', 'N/A')}")
        
        return metrics
