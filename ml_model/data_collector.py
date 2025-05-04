from typing import Dict
import json
import os
from datetime import datetime

class DataCollector:
    def __init__(self, data_dir="collected_data"):
        self.data_dir = data_dir
        if not os.path.exists(data_dir):
            os.makedirs(data_dir)
            
        # Create separate directories for different document types
        self.sop_dir = os.path.join(data_dir, "sops")
        self.batch_record_dir = os.path.join(data_dir, "batch_records")
        
        for directory in [self.sop_dir, self.batch_record_dir]:
            if not os.path.exists(directory):
                os.makedirs(directory)

    def save_document(self, 
                     input_data: Dict, 
                     generated_content: str, 
                     doc_type: str,
                     metadata: Dict = None):
        """Save a generated document with its input data and metadata"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Prepare the data to save
        data = {
            "timestamp": timestamp,
            "input": input_data,
            "generated_content": generated_content,
            "metadata": metadata or {},
            "feedback": None,  # To be filled later
            "feedback_timestamp": None
        }
        
        # Choose directory based on document type
        save_dir = self.sop_dir if doc_type.lower() == "sop" else self.batch_record_dir
        
        # Save the document
        filename = f"{timestamp}_{doc_type.lower()}.json"
        filepath = os.path.join(save_dir, filename)
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
            
        return filepath

    def add_feedback(self, 
                    doc_path: str, 
                    feedback_score: float, 
                    feedback_text: str = None):
        """Add feedback to a previously generated document"""
        if not os.path.exists(doc_path):
            raise FileNotFoundError(f"Document not found: {doc_path}")
            
        # Load the existing document
        with open(doc_path, 'r') as f:
            data = json.load(f)
            
        # Add feedback
        data["feedback"] = {
            "score": feedback_score,
            "text": feedback_text,
            "timestamp": datetime.now().strftime("%Y%m%d_%H%M%S")
        }
        
        # Save the updated document
        with open(doc_path, 'w') as f:
            json.dump(data, f, indent=2)

    def get_training_data(self, min_feedback_score: float = None) -> list:
        """Get all documents with feedback for training"""
        training_data = []
        
        # Function to process files in a directory
        def process_directory(directory):
            for filename in os.listdir(directory):
                if filename.endswith('.json'):
                    filepath = os.path.join(directory, filename)
                    with open(filepath, 'r') as f:
                        data = json.load(f)
                        
                    # Only include documents with feedback
                    if data.get('feedback'):
                        feedback_score = data['feedback']['score']
                        
                        # Filter by minimum feedback score if specified
                        if min_feedback_score is None or feedback_score >= min_feedback_score:
                            training_data.append({
                                'input': data['input'],
                                'output': data['generated_content'],
                                'feedback_score': feedback_score,
                                'feedback_text': data['feedback'].get('text'),
                                'type': 'sop' if directory == self.sop_dir else 'batch_record'
                            })
        
        # Process both SOP and batch record directories
        process_directory(self.sop_dir)
        process_directory(self.batch_record_dir)
        
        return training_data

    def get_statistics(self) -> Dict:
        """Get statistics about collected data"""
        stats = {
            'total_documents': 0,
            'documents_with_feedback': 0,
            'average_feedback_score': 0,
            'sops': {'total': 0, 'with_feedback': 0},
            'batch_records': {'total': 0, 'with_feedback': 0}
        }
        
        feedback_scores = []
        
        # Function to process files in a directory
        def process_directory(directory, doc_type):
            for filename in os.listdir(directory):
                if filename.endswith('.json'):
                    with open(os.path.join(directory, filename), 'r') as f:
                        data = json.load(f)
                    
                    stats[doc_type]['total'] += 1
                    stats['total_documents'] += 1
                    
                    if data.get('feedback'):
                        stats[doc_type]['with_feedback'] += 1
                        stats['documents_with_feedback'] += 1
                        feedback_scores.append(data['feedback']['score'])
        
        # Process both directories
        process_directory(self.sop_dir, 'sops')
        process_directory(self.batch_record_dir, 'batch_records')
        
        # Calculate average feedback score
        if feedback_scores:
            stats['average_feedback_score'] = sum(feedback_scores) / len(feedback_scores)
            
        return stats
