import torch
from torch import nn
from transformers import AutoTokenizer, AutoModelForCausalLM, TrainingArguments, Trainer
from datasets import Dataset
import json
import os
import re
from typing import List, Dict, Tuple, Optional
from .word_generator import WordDocumentGenerator

class SOPModel:
    def __init__(self, model_name="microsoft/phi-2", save_dir="model_checkpoints"):
        self.save_dir = save_dir
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)
        self.model = AutoModelForCausalLM.from_pretrained(model_name)
        self.training_data = []
        
        # Create save directory if it doesn't exist
        if not os.path.exists(save_dir):
            os.makedirs(save_dir)
            
        # Load existing training data if available
        self.load_training_data()

    def load_training_data(self):
        """Load existing training data from disk"""
        try:
            with open(f"{self.save_dir}/training_data.json", 'r') as f:
                self.training_data = json.load(f)
        except FileNotFoundError:
            self.training_data = []

    def save_training_data(self):
        """Save training data to disk"""
        with open(f"{self.save_dir}/training_data.json", 'w') as f:
            json.dump(self.training_data, f)

    def add_training_example(self, input_data: Dict, generated_sop: str, feedback_score: float):
        """Add a new training example with user feedback"""
        example = {
            'input': input_data,
            'output': generated_sop,
            'feedback_score': feedback_score,
            'type': input_data.get('type', 'sop')
        }
        self.training_data.append(example)
        self.save_training_data()

    def prepare_dataset(self):
        """Convert training data to HuggingFace dataset format"""
        formatted_data = []
        
        for example in self.training_data:
            # Format input as a prompt
            input_prompt = f"""Type: {example['type']}
Steps: {example['input']['steps']}
Roles: {example['input']['roles']}
Notes: {example['input'].get('notes', '')}
Generated Content: {example['output']}
Quality Score: {example['feedback_score']}"""
            
            formatted_data.append({
                'text': input_prompt,
                'quality_score': example['feedback_score']
            })
        
        return Dataset.from_list(formatted_data)

    def fine_tune(self):
        """Fine-tune the model on collected training data"""
        if len(self.training_data) < 10:
            raise ValueError("Not enough training data. Need at least 10 examples.")

        dataset = self.prepare_dataset()
        
        training_args = TrainingArguments(
            output_dir=self.save_dir,
            num_train_epochs=3,
            per_device_train_batch_size=4,
            save_steps=100,
            save_total_limit=2,
            learning_rate=2e-5,
            weight_decay=0.01,
            logging_dir='./logs',
        )

        trainer = Trainer(
            model=self.model,
            args=training_args,
            train_dataset=dataset,
        )

        trainer.train()
        
        # Save the fine-tuned model
        self.model.save_pretrained(f"{self.save_dir}/latest")
        self.tokenizer.save_pretrained(f"{self.save_dir}/latest")

    def generate_document(self, input_data: Dict) -> Tuple[str, Optional[str], Optional[str]]:
        """Generate a document using the fine-tuned model
        
        Returns:
            Tuple containing:
                - The generated document content (str)
                - Path to Word document if generated (str or None)
                - Template type used (str or None)
        """
        # Check if this is an NK cell thawing request
        template_type = None
        steps = input_data.get('steps', '').lower()
        
        # Detect NK cell thawing requests
        if any(term in steps for term in ['nk cell', 'natural killer cell']) and \
           any(term in steps for term in ['thaw', 'thawing', 'defrost']):
            template_type = 'NK_cell_thawing'
        
        # Format input as a prompt
        prompt = f"""Type: {input_data.get('type', 'sop')}
Steps: {input_data.get('steps', '')}
Roles: {input_data.get('roles', '')}
Notes: {input_data.get('notes', '')}
Generate a detailed document following the standard format."""

        inputs = self.tokenizer(prompt, return_tensors="pt")
        
        # Generate text
        outputs = self.model.generate(
            inputs.input_ids,
            max_length=2000,
            num_return_sequences=1,
            temperature=0.7,
            top_p=0.9,
            do_sample=True
        )
        
        generated_content = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
        
        # Generate Word document if requested
        word_doc_path = None
        if template_type or 'word' in steps or 'word format' in steps or 'docx' in steps:
            try:
                # Extract title from content
                title_match = re.search(r"Title:\s*([^\n]+)", generated_content)
                title = title_match.group(1) if title_match else "NK Cell Thawing SOP"
                
                # Generate Word document
                word_generator = WordDocumentGenerator()
                word_doc_path = word_generator.generate_sop_document(
                    content=generated_content,
                    title=title,
                    doc_id=f"SOP-{input_data.get('type', 'sop').upper()}-{len(self.training_data) + 1:03d}",
                    template_type=template_type
                )
            except Exception as e:
                print(f"Error generating Word document: {e}")
        
        return generated_content, word_doc_path, template_type
