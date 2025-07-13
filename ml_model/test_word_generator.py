"""
Test script for the WordDocumentGenerator class
"""
import os
from word_generator import WordDocumentGenerator

def test_word_generator():
    """Test the WordDocumentGenerator class"""
    print("Testing WordDocumentGenerator...")
    
    # Create an instance of the WordDocumentGenerator
    generator = WordDocumentGenerator()
    
    # Test content for NK cell thawing SOP
    content = """
    # NK Cell Thawing SOP
    
    This is a test SOP for NK cell thawing procedure.
    
    ## Materials
    - Cryovials containing frozen NK cells
    - Water bath set to 37°C
    - 70% ethanol
    - Sterile PBS
    
    ## Procedure
    1. Pre-warm water bath to 37°C
    2. Remove cryovial from liquid nitrogen storage
    3. Thaw cells rapidly in 37°C water bath
    4. Transfer cells to a sterile tube
    5. Add pre-warmed media dropwise
    """
    
    # Generate a test document
    output_path = generator.generate_sop_document(
        content=content,
        title="NK Cell Thawing SOP",
        doc_id="TEST-001",
        template_type="NK_cell_thawing"
    )
    
    print(f"Generated document at: {output_path}")
    
    # Verify the file exists
    if os.path.exists(output_path):
        print("✅ Document generated successfully!")
        file_size = os.path.getsize(output_path)
        print(f"File size: {file_size} bytes")
    else:
        print("❌ Failed to generate document!")

if __name__ == "__main__":
    test_word_generator()
