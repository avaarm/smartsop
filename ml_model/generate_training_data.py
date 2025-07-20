"""
Generate training data for SmartSOP model based on standard SOP and batch record guidelines.
This script creates synthetic training examples based on industry standards.
"""

import json
import os
import random
from typing import List, Dict, Any

# Ensure directories exist
os.makedirs("ml_model/saved_models", exist_ok=True)
os.makedirs("collected_data", exist_ok=True)

# SOP Templates and Components
SOP_STEPS_TEMPLATES = [
    # Quality Control SOPs
    "1. Prepare testing equipment\n2. Calibrate instruments\n3. Collect samples\n4. Perform analysis\n5. Record results\n6. Review data\n7. Document findings",
    "1. Receive raw materials\n2. Inspect packaging integrity\n3. Check documentation\n4. Sample according to plan\n5. Test samples\n6. Record results\n7. Make disposition decision",
    "1. Set up testing environment\n2. Calibrate equipment\n3. Prepare reagents\n4. Process control samples\n5. Analyze test samples\n6. Calculate results\n7. Document findings\n8. Review and approve data",
    
    # Manufacturing SOPs
    "1. Prepare equipment\n2. Sanitize work area\n3. Gather materials\n4. Perform assembly\n5. Inspect product\n6. Package product\n7. Complete documentation",
    "1. Set up production line\n2. Verify material specifications\n3. Process materials according to formula\n4. Monitor critical parameters\n5. Collect in-process samples\n6. Perform final inspection\n7. Release to packaging",
    "1. Clean equipment\n2. Prepare sanitizing solution\n3. Apply solution to surfaces\n4. Allow contact time\n5. Rinse thoroughly\n6. Verify cleanliness\n7. Document procedure",
    
    # Laboratory SOPs
    "1. Prepare laboratory area\n2. Calibrate analytical instruments\n3. Prepare reagents\n4. Process samples\n5. Run analysis\n6. Calculate results\n7. Document findings\n8. Review data",
    "1. Receive test samples\n2. Log sample information\n3. Prepare samples for testing\n4. Perform required tests\n5. Record raw data\n6. Calculate final results\n7. Complete test report\n8. Review and approve results",
    
    # Equipment SOPs
    "1. Power down equipment\n2. Disconnect from power source\n3. Disassemble components\n4. Clean each component\n5. Inspect for damage\n6. Reassemble equipment\n7. Perform functional test\n8. Document maintenance",
    "1. Review equipment manual\n2. Perform pre-operation checks\n3. Start equipment according to procedure\n4. Monitor operation parameters\n5. Perform required adjustments\n6. Shut down properly\n7. Document operation details"
]

SOP_ROLES_TEMPLATES = [
    "Quality Control Specialist, Laboratory Manager, Quality Assurance Reviewer",
    "Production Operator, Quality Control Analyst, Production Supervisor, Quality Assurance Manager",
    "Laboratory Technician, Laboratory Manager, Quality Assurance Specialist",
    "Equipment Operator, Maintenance Technician, Production Supervisor",
    "Manufacturing Technician, Quality Control Analyst, Production Manager",
    "Validation Specialist, Quality Assurance Reviewer, Department Manager",
    "Warehouse Personnel, Quality Control Analyst, Materials Manager",
    "Clean Room Operator, Quality Control Specialist, Production Supervisor",
    "Calibration Technician, Laboratory Manager, Quality Assurance Specialist",
    "Document Control Specialist, Department Manager, Quality Assurance Reviewer"
]

SOP_NOTES_TEMPLATES = [
    "Ensure all equipment is calibrated according to SOP-QC-001. Document all deviations.",
    "Follow safety protocols outlined in SAF-001. Wear appropriate PPE at all times.",
    "Critical process parameters must be monitored and recorded every 30 minutes.",
    "Reference master formula document MF-2023-01 for specific processing parameters.",
    "All documentation must be completed in blue or black ink. No correction fluid allowed.",
    "Samples must be tested within 4 hours of collection to ensure validity.",
    "Maintain controlled environment conditions as specified in ENV-SOP-002.",
    "All deviations must be documented and reported to the supervisor immediately.",
    "Electronic records must be backed up according to IT-SOP-005.",
    "Refer to equipment manual EM-2022-XYZ for troubleshooting procedures."
]

# Batch Record Templates and Components
BATCH_STEPS_TEMPLATES = [
    # Pharmaceutical Batch Records
    "1. Verify raw materials\n2. Weigh ingredients\n3. Mix components\n4. Process mixture\n5. Fill containers\n6. Inspect finished product\n7. Sample for testing\n8. Complete documentation",
    "1. Prepare clean room\n2. Sanitize equipment\n3. Prepare solution\n4. Filter solution\n5. Fill vials\n6. Apply stoppers\n7. Crimp seals\n8. Inspect vials\n9. Label product",
    "1. Verify material identity\n2. Dispense raw materials\n3. Granulate powder\n4. Dry granulation\n5. Blend with excipients\n6. Compress tablets\n7. Coat tablets\n8. Package product",
    
    # Food Production Batch Records
    "1. Receive ingredients\n2. Weigh components\n3. Mix according to formula\n4. Process mixture\n5. Package product\n6. Label packages\n7. Sample for QC\n8. Release for distribution",
    "1. Sanitize processing area\n2. Prepare ingredients\n3. Mix according to recipe\n4. Cook product\n5. Cool to specified temperature\n6. Package product\n7. Apply batch coding\n8. Move to quarantine",
    
    # Chemical Production Batch Records
    "1. Verify reactor status\n2. Add initial reagents\n3. Heat to reaction temperature\n4. Add catalysts\n5. Monitor reaction parameters\n6. Cool mixture\n7. Filter product\n8. Package final product",
    "1. Prepare reaction vessel\n2. Add solvent\n3. Dissolve reactants\n4. Control temperature\n5. Monitor pH\n6. Precipitate product\n7. Filter and dry\n8. Package and label"
]

BATCH_ROLES_TEMPLATES = [
    "Production Operator, Quality Control Analyst, Production Supervisor, Quality Assurance Reviewer",
    "Manufacturing Technician, QC Analyst, Production Manager, QA Specialist",
    "Compounding Technician, Fill Technician, QC Analyst, Production Supervisor",
    "Weighing Operator, Production Technician, In-Process Control, QA Reviewer",
    "Reactor Operator, Process Engineer, QC Analyst, Production Manager",
    "Clean Room Operator, Fill/Finish Technician, QC Microbiologist, QA Specialist",
    "Formulation Scientist, Production Technician, QC Chemist, QA Reviewer"
]

BATCH_NOTES_TEMPLATES = [
    "Critical process parameters: Temperature 60-65°C, Pressure 2.0-2.5 bar, pH 6.8-7.2",
    "In-process testing required at steps 3, 5, and 7. Document results before proceeding.",
    "Environmental monitoring required during steps 4-6. Follow EM-SOP-003.",
    "Verify all calculations by second person before proceeding with material additions.",
    "Reference master batch record MBR-2023-05 for specific acceptance criteria.",
    "Line clearance must be performed and documented before batch processing begins.",
    "All deviations must be documented and approved before proceeding to next step.",
    "Hold times: Maximum 4 hours between steps 3 and 4, 24 hours between steps 6 and 7.",
    "Maintain controlled room temperature (20-25°C) and relative humidity (30-50%)."
]

# SOP and Batch Record Output Templates
SOP_OUTPUT_TEMPLATES = [
    """
# STANDARD OPERATING PROCEDURE
## {title}

**Document ID:** SOP-{doc_id}  
**Version:** 1.0  
**Effective Date:** {date}  
**Review Date:** {review_date}  

### 1. PURPOSE
This Standard Operating Procedure (SOP) defines the process for {purpose_statement}.

### 2. SCOPE
This procedure applies to all {scope_statement}.

### 3. RESPONSIBILITIES
{roles_section}

### 4. MATERIALS AND EQUIPMENT
- {equipment_list}

### 5. PROCEDURE
{procedure_steps}

### 6. DOCUMENTATION
The following records must be maintained:
- {documentation_list}

### 7. REFERENCES
- {references_list}

### 8. REVISION HISTORY
| Version | Date | Description of Changes | Author | Approved By |
|---------|------|------------------------|--------|-------------|
| 1.0 | {date} | Initial release | | |

### 9. APPROVALS
| Role | Name | Signature | Date |
|------|------|-----------|------|
| Author | | | |
| Reviewer | | | |
| Approver | | | |
    """,
    
    """
# STANDARD OPERATING PROCEDURE
## {title}

**SOP Number:** SOP-{doc_id}  
**Revision:** 1.0  
**Implementation Date:** {date}  
**Next Review:** {review_date}  

### 1. INTRODUCTION
#### 1.1 Purpose
This procedure establishes guidelines for {purpose_statement}.

#### 1.2 Scope
This SOP applies to {scope_statement}.

### 2. DEFINITIONS
- **{term1}:** {definition1}
- **{term2}:** {definition2}

### 3. RESPONSIBILITIES
{roles_section}

### 4. SAFETY CONSIDERATIONS
{safety_considerations}

### 5. MATERIALS AND EQUIPMENT
{equipment_list}

### 6. PROCEDURE
{procedure_steps}

### 7. QUALITY CONTROL
{quality_control_section}

### 8. DOCUMENTATION
{documentation_section}

### 9. REFERENCES
{references_list}

### 10. ATTACHMENTS
- {attachment1}
- {attachment2}

### 11. REVISION HISTORY
| Version | Effective Date | Description | Prepared By | Approved By |
|---------|---------------|-------------|-------------|-------------|
| 1.0 | {date} | Initial version | | |
    """
]

BATCH_OUTPUT_TEMPLATES = [
    """
# BATCH PRODUCTION RECORD
## {product_name}

**Batch Number:** {batch_number}  
**Product Code:** {product_code}  
**Batch Size:** {batch_size}  
**Manufacturing Date:** {date}  

### 1. PRODUCT INFORMATION
- **Product Name:** {product_name}
- **Strength/Concentration:** {strength}
- **Dosage Form:** {dosage_form}

### 2. RAW MATERIALS
| Material | Item Code | Quantity Required | Quantity Dispensed | Dispensed By | Verified By |
|----------|-----------|-------------------|-------------------|--------------|-------------|
{raw_materials_table}

### 3. EQUIPMENT
| Equipment | ID Number | Cleaned By | Verified By |
|-----------|-----------|------------|-------------|
{equipment_table}

### 4. MANUFACTURING PROCEDURE
{manufacturing_steps}

### 5. IN-PROCESS CONTROLS
| Test | Specification | Result | Tested By | Date/Time |
|------|--------------|--------|-----------|-----------|
{in_process_table}

### 6. BATCH RECONCILIATION
- **Theoretical Yield:** {theoretical_yield}
- **Actual Yield:** ____________
- **Yield Percentage:** ____________
- **Reconciliation By:** ____________
- **Date:** ____________

### 7. BATCH RELEASE
| Role | Name | Signature | Date |
|------|------|-----------|------|
| Manufacturing | | | |
| Quality Control | | | |
| Quality Assurance | | | |
    """,
    
    """
# BATCH MANUFACTURING RECORD
## {product_name}

**BMR Number:** BMR-{batch_number}  
**Product ID:** {product_code}  
**Lot Size:** {batch_size}  
**Start Date:** {date}  

### 1. PRODUCT DETAILS
- **Product Description:** {product_description}
- **Physical Form:** {physical_form}
- **Storage Requirements:** {storage_requirements}

### 2. MATERIAL INFORMATION
| Item | Material Code | Standard Quantity | Actual Quantity | Lot Number | Expiry Date | Verified By |
|------|--------------|-------------------|----------------|------------|-------------|-------------|
{materials_table}

### 3. EQUIPMENT LIST
| Equipment | ID | Calibration Due Date | Setup By | Verified By |
|-----------|----|--------------------|----------|-------------|
{equipment_list_table}

### 4. PRE-PRODUCTION CHECKLIST
- Area cleaned and sanitized: □ Yes □ No
- Line clearance completed: □ Yes □ No
- Materials verified: □ Yes □ No
- Equipment verified: □ Yes □ No

### 5. PRODUCTION PROCESS
{production_steps}

### 6. IN-PROCESS TESTING
{in_process_testing}

### 7. DEVIATIONS AND INVESTIGATIONS
{deviations_section}

### 8. FINAL PRODUCT DETAILS
- **Quantity Produced:** ____________
- **Number of Containers:** ____________
- **Lot Number Assigned:** ____________

### 9. BATCH DISPOSITION
□ Released  □ Rejected  □ On Hold

**Reason:** ____________

### 10. APPROVALS
| Department | Name | Signature | Date |
|------------|------|-----------|------|
| Production | | | |
| QC | | | |
| QA | | | |
    """
]

def generate_sop_document(steps: str, roles: str, notes: str) -> Dict[str, Any]:
    """Generate a complete SOP document based on input parameters"""
    
    # Parse roles into structured format
    roles_list = [role.strip() for role in roles.split(',')]
    roles_section = ""
    for role in roles_list:
        responsibilities = []
        if "Quality" in role:
            responsibilities = [
                f"Review and approve documentation",
                f"Ensure compliance with regulations",
                f"Perform quality checks as specified"
            ]
        elif "Operator" in role or "Technician" in role:
            responsibilities = [
                f"Execute procedure as outlined",
                f"Document all activities accurately",
                f"Report deviations to supervisor"
            ]
        elif "Supervisor" in role or "Manager" in role:
            responsibilities = [
                f"Oversee execution of the procedure",
                f"Review completed documentation",
                f"Address deviations and issues"
            ]
        
        roles_section += f"**{role}**\n"
        for resp in responsibilities:
            roles_section += f"- {resp}\n"
        roles_section += "\n"
    
    # Generate random values for template placeholders
    doc_id = f"{random.randint(100, 999)}-{random.randint(10, 99)}"
    current_year = 2025
    date = f"{current_year}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
    review_date = f"{current_year + 1}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
    
    # Determine SOP type and title
    sop_types = ["Quality Control", "Manufacturing", "Laboratory", "Equipment", "Cleaning", "Documentation"]
    activities = ["Procedure", "Process", "Operation", "Testing", "Maintenance", "Validation"]
    sop_type = random.choice(sop_types)
    activity = random.choice(activities)
    title = f"{sop_type} {activity}"
    
    # Generate purpose and scope statements
    purpose_statement = f"{sop_type.lower()} {activity.lower()} in a consistent and compliant manner"
    scope_statement = f"personnel involved in {sop_type.lower()} {activity.lower()}"
    
    # Generate equipment list
    equipment_items = [
        "Analytical balance", "pH meter", "Thermometer", "Timer", "Calibrated pipettes",
        "Mixing vessel", "Heating plate", "Refrigerator", "Incubator", "Microscope",
        "HPLC system", "Dissolution apparatus", "Tablet hardness tester", "Autoclave",
        "Laminar flow hood", "Centrifuge", "Spectrophotometer", "Moisture analyzer"
    ]
    equipment_list = "\n- ".join(random.sample(equipment_items, k=min(5, len(equipment_items))))
    
    # Format procedure steps
    procedure_steps = steps.replace("\n", "\n\n")
    
    # Generate documentation list
    documentation_items = [
        "Completed procedure form", "Equipment usage log", "Calibration records",
        "Training records", "Deviation reports", "Change control documentation",
        "Batch records", "Test results", "Environmental monitoring data"
    ]
    documentation_list = "\n- ".join(random.sample(documentation_items, k=min(3, len(documentation_items))))
    
    # Generate references list
    references_items = [
        "21 CFR Part 211 - Current Good Manufacturing Practice for Finished Pharmaceuticals",
        "USP <1116> Microbiological Control and Monitoring",
        "ISO 9001:2015 Quality Management Systems",
        "ICH Q7 Good Manufacturing Practice Guide for Active Pharmaceutical Ingredients",
        "EU GMP Guidelines Annex 1: Manufacture of Sterile Medicinal Products",
        "Company Quality Manual, Section 4.2",
        "Equipment Manual: Model XYZ-123"
    ]
    references_list = "\n- ".join(random.sample(references_items, k=min(3, len(references_items))))
    
    # Generate safety considerations
    safety_items = [
        "Wear appropriate PPE including gloves, lab coat, and safety glasses.",
        "Review Safety Data Sheets (SDS) for all chemicals before use.",
        "Follow waste disposal procedures according to EHS-SOP-001.",
        "Ensure proper ventilation when working with volatile materials.",
        "Use proper lifting techniques for heavy equipment."
    ]
    safety_considerations = "\n".join(random.sample(safety_items, k=min(3, len(safety_items))))
    
    # Generate quality control section
    qc_items = [
        "Verify all measurements against calibrated standards.",
        "Document all results in the appropriate log book.",
        "Any result outside of specification must be reported immediately.",
        "Perform duplicate testing for critical parameters.",
        "Verify calculations using the four-eyes principle."
    ]
    quality_control_section = "\n".join(random.sample(qc_items, k=min(3, len(qc_items))))
    
    # Generate documentation section
    doc_items = [
        "Complete all records in blue or black ink.",
        "Any corrections must follow the single-line strikethrough method, initialed and dated.",
        "Electronic records must be backed up according to IT-SOP-005.",
        "Retain all records for a minimum of 5 years.",
        "Submit completed forms to Document Control within 3 business days."
    ]
    documentation_section = "\n".join(random.sample(doc_items, k=min(3, len(doc_items))))
    
    # Generate terms and definitions
    terms = ["CAPA", "OOS", "SOP", "GMP", "QMS", "IQ/OQ/PQ", "API", "QA", "QC"]
    definitions = [
        "Corrective and Preventive Action",
        "Out of Specification",
        "Standard Operating Procedure",
        "Good Manufacturing Practice",
        "Quality Management System",
        "Installation/Operational/Performance Qualification",
        "Active Pharmaceutical Ingredient",
        "Quality Assurance",
        "Quality Control"
    ]
    term_indices = random.sample(range(len(terms)), 2)
    term1, term2 = terms[term_indices[0]], terms[term_indices[1]]
    definition1, definition2 = definitions[term_indices[0]], definitions[term_indices[1]]
    
    # Generate attachments
    attachment_items = [
        "Form F-001: Equipment Cleaning Log",
        "Form F-002: Calibration Record",
        "Form F-003: Deviation Report",
        "Appendix A: Acceptance Criteria",
        "Appendix B: Troubleshooting Guide"
    ]
    attachment1, attachment2 = random.sample(attachment_items, 2)
    
    # Select and fill template
    template = random.choice(SOP_OUTPUT_TEMPLATES)
    output = template.format(
        title=title,
        doc_id=doc_id,
        date=date,
        review_date=review_date,
        purpose_statement=purpose_statement,
        scope_statement=scope_statement,
        roles_section=roles_section,
        equipment_list=equipment_list,
        procedure_steps=procedure_steps,
        documentation_list=documentation_list,
        references_list=references_list,
        safety_considerations=safety_considerations,
        quality_control_section=quality_control_section,
        documentation_section=documentation_section,
        term1=term1,
        term2=term2,
        definition1=definition1,
        definition2=definition2,
        attachment1=attachment1,
        attachment2=attachment2
    )
    
    return output

def generate_batch_document(steps: str, roles: str, notes: str) -> Dict[str, Any]:
    """Generate a complete batch record document based on input parameters"""
    
    # Generate random values for template placeholders
    batch_number = f"B{random.randint(10000, 99999)}"
    product_code = f"P{random.randint(100, 999)}"
    batch_size = f"{random.randint(10, 500)} kg"
    current_year = 2025
    date = f"{current_year}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
    
    # Generate product details
    product_types = ["Tablet", "Capsule", "Injection", "Cream", "Ointment", "Solution", "Suspension"]
    product_names = ["Amoxicillin", "Ibuprofen", "Paracetamol", "Omeprazole", "Lisinopril", "Metformin", "Atorvastatin"]
    product_name = f"{random.choice(product_names)} {random.choice(product_types)}"
    strength = f"{random.randint(5, 500)} mg"
    dosage_form = random.choice(product_types)
    
    # Generate raw materials table
    raw_materials = [
        {"name": "Active Ingredient", "code": f"RM-{random.randint(1000, 9999)}", "quantity": f"{random.randint(1, 100)} kg"},
        {"name": "Excipient 1", "code": f"RM-{random.randint(1000, 9999)}", "quantity": f"{random.randint(1, 50)} kg"},
        {"name": "Excipient 2", "code": f"RM-{random.randint(1000, 9999)}", "quantity": f"{random.randint(1, 30)} kg"},
        {"name": "Coating Material", "code": f"RM-{random.randint(1000, 9999)}", "quantity": f"{random.randint(1, 10)} kg"}
    ]
    
    raw_materials_table = ""
    for material in raw_materials:
        raw_materials_table += f"| {material['name']} | {material['code']} | {material['quantity']} | | | |\n"
    
    # Generate equipment table
    equipment = [
        {"name": "Mixer", "id": f"EQ-{random.randint(100, 999)}"},
        {"name": "Reactor", "id": f"EQ-{random.randint(100, 999)}"},
        {"name": "Filling Machine", "id": f"EQ-{random.randint(100, 999)}"},
        {"name": "Packaging Line", "id": f"EQ-{random.randint(100, 999)}"}
    ]
    
    equipment_table = ""
    for eq in equipment:
        equipment_table += f"| {eq['name']} | {eq['id']} | | |\n"
    
    # Format manufacturing steps
    manufacturing_steps = steps.replace("\n", "\n\n")
    
    # Generate in-process control table
    in_process_controls = [
        {"test": "pH", "spec": "6.8 - 7.2"},
        {"test": "Temperature", "spec": "60°C - 65°C"},
        {"test": "Dissolution", "spec": "NLT 80% in 30 minutes"},
        {"test": "Weight Variation", "spec": "± 5% of target weight"}
    ]
    
    in_process_table = ""
    for control in in_process_controls:
        in_process_table += f"| {control['test']} | {control['spec']} | | | |\n"
    
    # Calculate theoretical yield
    theoretical_yield = f"{random.randint(80, 95)}%"
    
    # Additional details for second template
    product_description = f"{strength} {product_name}"
    physical_form = random.choice(["White crystalline powder", "Off-white granules", "Clear solution", "Viscous suspension"])
    storage_requirements = random.choice([
        "Store at 15-25°C, protect from light and moisture",
        "Refrigerate at 2-8°C",
        "Store at controlled room temperature (20-25°C)"
    ])
    
    # Generate materials table for second template
    materials_table = ""
    for material in raw_materials:
        materials_table += f"| {material['name']} | {material['code']} | {material['quantity']} | | | | |\n"
    
    # Generate equipment list table for second template
    equipment_list_table = ""
    for eq in equipment:
        next_year = current_year + 1
        cal_date = f"{next_year}-{random.randint(1, 12):02d}-{random.randint(1, 28):02d}"
        equipment_list_table += f"| {eq['name']} | {eq['id']} | {cal_date} | | |\n"
    
    # Format production steps
    production_steps = steps.replace("\n", "\n\n")
    
    # Generate in-process testing section
    in_process_tests = [
        "**Step 3:** Check pH and temperature before proceeding",
        "**Step 5:** Sample for appearance and weight check",
        "**Step 7:** Test for dissolution and content uniformity"
    ]
    in_process_testing = "\n\n".join(in_process_tests)
    
    # Generate deviations section
    deviations_section = "Record any deviations from the standard procedure here:\n\n_______________________________________________\n\n_______________________________________________"
    
    # Select and fill template
    template = random.choice(BATCH_OUTPUT_TEMPLATES)
    output = template.format(
        product_name=product_name,
        batch_number=batch_number,
        product_code=product_code,
        batch_size=batch_size,
        date=date,
        strength=strength,
        dosage_form=dosage_form,
        raw_materials_table=raw_materials_table,
        equipment_table=equipment_table,
        manufacturing_steps=manufacturing_steps,
        in_process_table=in_process_table,
        theoretical_yield=theoretical_yield,
        product_description=product_description,
        physical_form=physical_form,
        storage_requirements=storage_requirements,
        materials_table=materials_table,
        equipment_list_table=equipment_list_table,
        production_steps=production_steps,
        in_process_testing=in_process_testing,
        deviations_section=deviations_section
    )
    
    return output

def generate_training_examples(num_examples: int = 20) -> List[Dict[str, Any]]:
    """Generate training examples for the model"""
    training_data = []
    
    for i in range(num_examples):
        # Determine document type
        doc_type = "sop" if i % 2 == 0 else "batch"
        
        # Select templates based on document type
        if doc_type == "sop":
            steps = random.choice(SOP_STEPS_TEMPLATES)
            roles = random.choice(SOP_ROLES_TEMPLATES)
            notes = random.choice(SOP_NOTES_TEMPLATES)
            output = generate_sop_document(steps, roles, notes)
        else:
            steps = random.choice(BATCH_STEPS_TEMPLATES)
            roles = random.choice(BATCH_ROLES_TEMPLATES)
            notes = random.choice(BATCH_NOTES_TEMPLATES)
            output = generate_batch_document(steps, roles, notes)
        
        # Create training example
        example = {
            "input": {
                "type": doc_type,
                "steps": steps,
                "roles": roles,
                "notes": notes
            },
            "output": output,
            "feedback_score": random.uniform(4.0, 5.0)  # High quality examples for training
        }
        
        training_data.append(example)
    
    return training_data

def save_training_data(training_data: List[Dict[str, Any]]) -> None:
    """Save training data to file"""
    with open("ml_model/saved_models/training_data.json", "w") as f:
        json.dump(training_data, f, indent=2)
    
    # Also save individual examples to collected_data directory for the data collector
    for i, example in enumerate(training_data):
        # Create a unique ID for each document
        doc_id = f"doc_{i:03d}_{example['input']['type']}"
        doc_path = os.path.join("collected_data", f"{doc_id}.json")
        
        # Format the document data
        doc_data = {
            "input": example["input"],
            "generated_content": example["output"],
            "doc_type": example["input"]["type"],
            "metadata": {
                "model_version": "v1",
                "template_type": "standard",
                "timestamp": "2025-07-19T12:00:00"
            },
            "feedback": {
                "score": example["feedback_score"],
                "text": "Generated from industry standard templates"
            }
        }
        
        # Save the document
        with open(doc_path, "w") as f:
            json.dump(doc_data, f, indent=2)

if __name__ == "__main__":
    print("Generating training data from industry standard templates...")
    training_data = generate_training_examples(num_examples=30)
    save_training_data(training_data)
    print(f"Generated {len(training_data)} training examples.")
    print("Training data saved to ml_model/saved_models/training_data.json")
    print("Individual examples saved to collected_data/ directory")
