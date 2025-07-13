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

    def _get_nk_cell_thawing_template(self) -> str:
        """Return a pre-defined template for NK cell thawing SOP
        This avoids the need for model inference for common requests
        """
        return """Title: NK Cell Thawing Standard Operating Procedure (SOP)

Purpose: This SOP outlines the standardized procedure for thawing cryopreserved NK (Natural Killer) cells while maintaining cell viability and functionality.

Scope: This procedure applies to all laboratory personnel involved in NK cell-based research and therapeutic applications.

Responsibilities:
- Laboratory Technicians: Responsible for executing the NK cell thawing procedure according to this SOP.
- Laboratory Supervisor: Ensures compliance with this SOP and provides necessary training.
- Quality Assurance Personnel: Monitors adherence to the procedure and maintains documentation.

Materials and Equipment:
1. Personal Protective Equipment (PPE): Lab coat, gloves, safety glasses
2. Water bath set to 37°C
3. 70% ethanol spray
4. Sterile serological pipettes (5 mL, 10 mL)
5. Sterile 15 mL conical tubes
6. Complete NK cell medium (pre-warmed to 37°C)
7. Centrifuge
8. Biosafety cabinet (BSC)
9. Cell counting equipment
10. Timer
11. Cryovials containing frozen NK cells

Procedure:

1. Preparation
   1.1. Turn on the biosafety cabinet 15-30 minutes before starting the procedure.
   1.2. Set the water bath to 37°C and verify temperature with a thermometer.
   1.3. Pre-warm complete NK cell medium in 37°C water bath.
   1.4. Prepare all necessary materials and place them in the biosafety cabinet.

2. Thawing Process
   2.1. Remove the cryovial containing NK cells from liquid nitrogen storage.
   2.2. Transport the cryovial to the laboratory using appropriate safety measures.
   2.3. Partially submerge the cryovial in the 37°C water bath.
   2.4. Gently swirl the vial in the water bath without submerging the cap.
   2.5. Monitor the thawing process closely (approximately 2-3 minutes).
   2.6. Remove the vial from the water bath when a small ice crystal remains (approximately 90% thawed).
   2.7. Spray the outside of the vial with 70% ethanol before placing it in the biosafety cabinet.

3. Cell Transfer and Dilution
   3.1. Using a 1000 μL pipette, gently transfer the cell suspension to a labeled 15 mL conical tube.
   3.2. Slowly add pre-warmed complete NK cell medium dropwise to the cells:
       a. Add the first 1 mL of medium dropwise (1 drop per 2-3 seconds) while gently swirling the tube.
       b. Let the cells rest for 1 minute.
       c. Add the next 2 mL of medium dropwise at a slightly faster rate.
       d. Add an additional 7 mL of medium to bring the total volume to 10 mL.

4. Centrifugation and Resuspension
   4.1. Centrifuge the cell suspension at 300 x g for 5 minutes at room temperature.
   4.2. Carefully aspirate the supernatant without disturbing the cell pellet.
   4.3. Gently resuspend the cell pellet in 5-10 mL of fresh pre-warmed complete NK cell medium.

5. Cell Counting and Viability Assessment
   5.1. Take a small aliquot of the cell suspension for counting.
   5.2. Determine cell concentration and viability using trypan blue exclusion or other approved methods.
   5.3. Record cell count and viability in the laboratory notebook.

6. Final Cell Preparation
   6.1. Adjust the cell concentration to the required density for downstream applications.
   6.2. Transfer the cells to appropriate culture vessels.
   6.3. Place the cells in a humidified incubator at 37°C with 5% CO2.

7. Post-Procedure
   7.1. Clean the biosafety cabinet and water bath according to laboratory protocols.
   7.2. Dispose of waste in appropriate biohazard containers.
   7.3. Complete all required documentation.

Quality Control:
- Cell viability should be ≥ 80% post-thawing.
- Monitor NK cell recovery (typically 60-80% of the frozen cell number).
- Assess NK cell functionality using appropriate assays within 24-48 hours post-thawing.

Troubleshooting:
1. Low viability (<80%):
   - Ensure proper thawing temperature and timing.
   - Check medium quality and pre-warming.
   - Verify slow dilution technique was followed.

2. Cell clumping:
   - Ensure proper dropwise addition of medium.
   - Check medium composition and pH.
   - Consider adding DNase I if clumping persists due to DNA from lysed cells.

Documentation:
- Record date and time of thawing.
- Document cryovial information (cell type, passage number, freeze date, donor ID if applicable).
- Note cell count, viability, and any deviations from the SOP.
- Record the name of the person performing the procedure.

References:
1. Current Good Manufacturing Practice (cGMP) guidelines.
2. Laboratory-specific Cell Culture Manual.
3. Manufacturer's instructions for equipment used.

Appendices:
- NK Cell Medium Composition
- Cell Counting Protocol
- Equipment Maintenance Records

Revision History:
- Version 1.0: Initial SOP creation
- Version 1.1: Updated centrifugation parameters
- Version 1.2: Added detailed troubleshooting section"""

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
        
        # Detect NK cell thawing requests - use a more efficient approach
        is_nk_cell_request = False
        if 'nk' in steps or 'natural killer' in steps:
            if 'thaw' in steps or 'defrost' in steps:
                template_type = 'NK_cell_thawing'
                is_nk_cell_request = True
        
        # Use a template for NK cell thawing to speed up response time
        if is_nk_cell_request:
            # Use a pre-defined template for NK cell thawing
            generated_content = self._get_nk_cell_thawing_template()
        else:
            # Format input as a prompt for the model
            prompt = f"""Type: {input_data.get('type', 'sop')}
Steps: {input_data.get('steps', '')}
Roles: {input_data.get('roles', '')}
Notes: {input_data.get('notes', '')}
Generate a detailed document following the standard format."""

            inputs = self.tokenizer(prompt, return_tensors="pt")
            
            # Generate text with highly optimized parameters for faster response
            outputs = self.model.generate(
                inputs.input_ids,
                max_length=500,  # Further reduced from 1000
                num_return_sequences=1,
                temperature=0.6,  # Lower temperature for more focused output
                top_p=0.85,
                do_sample=True,
                no_repeat_ngram_size=3,  # Prevent repetition
                early_stopping=True,     # Stop when EOS token is generated
                num_beams=1,            # Disable beam search for speed
                pad_token_id=self.tokenizer.eos_token_id  # Explicitly set pad token
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
