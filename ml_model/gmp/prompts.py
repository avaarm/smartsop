"""LLM prompt templates for GMP document content generation."""

from typing import Optional


GMP_SYSTEM_PROMPT = (
    "You are a GMP documentation specialist for pharmaceutical and biotech "
    "manufacturing. You generate precise, regulatory-compliant content for "
    "batch records, SOPs, deviation reports, CAPA forms, and change controls. "
    "Use technical language appropriate for cell therapy, biologics, and "
    "pharmaceutical manufacturing. Be specific, detailed, and follow "
    "21 CFR Part 211 and EU GMP Annex guidelines."
)


PROCEDURE_STEPS_PROMPT = """Generate detailed manufacturing procedure steps for the following process:

Product: {product_name}
Process: {process_type}
Description: {description}

Generate steps in this exact JSON format:
{{
  "steps": [
    {{
      "number": "5.1",
      "title": "Label and Equipment Staging",
      "instructions": [
        {{
          "text": "Attach an in-process label.",
          "type": "action",
          "bsc": false
        }},
        {{
          "text": "Does this label match Part No., Lot No., and Subject ID for this BR?",
          "type": "verification",
          "options": ["Yes - Proceed", "No - Notify supervisor"]
        }},
        {{
          "text": "Record the room number and equipment ID number.",
          "type": "record",
          "variables": [
            {{"name": "Room Number", "type": "text"}},
            {{"name": "Process Date", "type": "date"}},
            {{"name": "Start Time", "type": "time", "format": "HHMM"}}
          ]
        }}
      ]
    }}
  ]
}}

Each step should include:
- Clear, imperative instructions
- Variables to record (measurements, IDs, times)
- Verification checkpoints where needed
- [BSC] prefix for operations inside biosafety cabinets
- Calculations referencing other step numbers
- Sample collection and tracking instructions where applicable

Generate 8-15 detailed steps appropriate for this process."""


EQUIPMENT_LIST_PROMPT = """Generate an equipment list for the following manufacturing process:

Product: {product_name}
Process: {process_type}
Description: {description}

Return a JSON object with this format:
{{
  "equipment": [
    {{
      "description": "Biosafety Cabinet",
      "requires_id": true,
      "requires_service_date": true
    }}
  ],
  "materials": [
    {{
      "part_number": "B095-03",
      "description": "Cells",
      "quantity": "N/A"
    }},
    {{
      "part_number": "F184-01",
      "description": "X-Vivo 15 (40 mL Aliquots)",
      "quantity": "1"
    }}
  ]
}}

Include all equipment and materials typically needed for this type of process.
Use realistic CPF-style part numbers. Include quantities where known, 'As Needed' otherwise."""


REFERENCES_PROMPT = """Generate a references list for the following GMP document:

Document Type: {doc_type}
Product: {product_name}
Process: {process_type}
Description: {description}

Return a JSON object:
{{
  "references": [
    {{
      "doc_number": "EQ-002",
      "title": "Operation and Maintenance of Biological Safety Cabinets"
    }}
  ]
}}

Include relevant SOPs, equipment manuals, and quality documents.
Use standard GMP document numbering (EQ- for equipment, GN- for general,
PR- for processing, QA- for quality, TM- for test methods)."""


ATTACHMENTS_PROMPT = """Generate an attachments list for the following batch record:

Product: {product_name}
Process: {process_type}
Description: {description}
References: {references}

Return a JSON object:
{{
  "attachments": [
    {{
      "doc_number": "Attachment 1",
      "title": "Sample Plan",
      "quantity": 1
    }}
  ]
}}

Include sample plans, test summary sheets, equipment checklists, and any
forms referenced in the procedure steps."""


GENERAL_INSTRUCTIONS_PROMPT = """Generate general instructions for a batch record:

Process: {process_type}
Product: {product_name}

Return a JSON object:
{{
  "instructions": [
    "Instructions preceded by [BSC] include operations that take place inside the ISO 5 zone of biosafety cabinets to prevent microbial contamination.",
    "Sanitize bag ports/penetrations with alcohol prior to connections.",
    "Centrifugations require the use of a second container to balance the rotor."
  ]
}}

Include 4-8 general instructions appropriate for this type of manufacturing process.
Cover aseptic practices, labeling, equipment operation, and safety."""


REVIEW_CHECKLIST_PROMPT = """Generate a manufacturing review checklist for a batch record:

Process: {process_type}
Product: {product_name}

Return a JSON object:
{{
  "checklist_items": [
    "Label and if applicable expiration date are correct",
    "Equipment recorded",
    "All processing steps completed",
    "Calculations checked",
    "Deviations identified and documented",
    "Material consumption in Title 21 reviewed"
  ]
}}

Include 6-10 items covering labels, equipment, steps, calculations, deviations,
and material tracking."""


DEVIATION_DESCRIPTION_PROMPT = """Generate a deviation report framework for:

Product: {product_name}
Process: {process_type}
Deviation Type: {deviation_type}
Brief Description: {description}

Return a JSON object:
{{
  "description": "Detailed description of the deviation...",
  "impact_assessment": "Assessment of impact on product quality...",
  "immediate_actions": ["Action 1", "Action 2"],
  "root_cause_categories": ["Equipment", "Personnel", "Process", "Material"],
  "investigation_steps": ["Step 1", "Step 2"]
}}"""


CAPA_PROMPT = """Generate a CAPA (Corrective and Preventive Action) framework for:

Product: {product_name}
Issue: {description}
Root Cause: {root_cause}

Return a JSON object:
{{
  "corrective_actions": [
    {{
      "action": "Description of corrective action",
      "responsible": "Role/Department",
      "target_date": "Timeline"
    }}
  ],
  "preventive_actions": [
    {{
      "action": "Description of preventive action",
      "responsible": "Role/Department",
      "target_date": "Timeline"
    }}
  ],
  "effectiveness_check": "Description of how effectiveness will be verified"
}}"""


CHANGE_CONTROL_PROMPT = """Generate a change control document framework for:

System/Process: {process_type}
Change Description: {description}

Return a JSON object:
{{
  "change_description": "Detailed description of the proposed change...",
  "reason_for_change": "Reason and justification...",
  "impact_assessment": {{
    "product_quality": "Impact on product quality...",
    "regulatory": "Regulatory impact...",
    "validation": "Validation requirements..."
  }},
  "implementation_plan": ["Step 1", "Step 2"],
  "training_requirements": ["Training item 1"],
  "risk_assessment": "Overall risk assessment..."
}}"""


PAPER_METHODS_EXTRACTION_PROMPT = """You are extracting a GMP batch record from a published scientific paper's methods section.

PAPER CONTEXT:
Title: {paper_title}
Journal: {paper_journal} ({paper_year})
Authors: {paper_authors}

PRODUCT BEING MANUFACTURED: {product_name}
PROCESS TYPE: {process_type}

METHODS SECTION FROM PAPER:
{methods_text}

Extract the key GMP manufacturing information from this methods section and return a JSON object with these fields:

{{
  "equipment": [
    {{"description": "Biosafety Cabinet"}},
    {{"description": "Centrifuge"}}
  ],
  "materials": [
    {{"part_number": "", "description": "RPMI 1640 Medium", "quantity": "500 mL"}},
    {{"part_number": "", "description": "Fetal Bovine Serum", "quantity": "10% final"}}
  ],
  "procedure_steps": [
    {{
      "number": "1",
      "title": "Sample Preparation",
      "instructions": [
        {{"text": "Thaw sample at 37C for 2 minutes", "type": "action", "bsc": false}},
        {{"text": "Centrifuge at 400g for 5 minutes", "type": "action", "bsc": false}}
      ]
    }}
  ],
  "references": [
    {{"doc_number": "", "title": "Any cited protocol or method reference mentioned"}}
  ],
  "notes": "Any critical parameters, concentrations, temperatures, or timings from the paper"
}}

IMPORTANT:
- Extract REAL equipment names and materials actually mentioned in the paper
- Preserve exact concentrations, temperatures, times, and volumes from the paper
- Use [BSC] prefix (bsc: true) for aseptic operations
- Break continuous prose into discrete numbered steps
- If equipment/materials not explicitly named, leave that category empty
- Do not invent CPF part numbers - leave part_number empty if not in paper
- Cite the paper in the notes field
"""


FLOWCHART_GENERATION_PROMPT = """Generate a process flowchart for the following manufacturing process:

{process_description}

Return a JSON object with this exact format:
{{
  "steps": [
    {{
      "id": "1",
      "label": "Start: Receive Materials",
      "type": "start",
      "next": [{{"target_id": "2"}}]
    }},
    {{
      "id": "2",
      "label": "Verify Documentation",
      "type": "action",
      "next": [{{"target_id": "3"}}]
    }},
    {{
      "id": "3",
      "label": "Materials\\nAcceptable?",
      "type": "decision",
      "next": [
        {{"target_id": "4", "label": "Yes"}},
        {{"target_id": "5", "label": "No"}}
      ]
    }},
    {{
      "id": "4",
      "label": "Process Cells",
      "type": "action",
      "next": [{{"target_id": "6"}}]
    }},
    {{
      "id": "5",
      "label": "Notify Supervisor",
      "type": "action",
      "next": [{{"target_id": "3"}}]
    }},
    {{
      "id": "6",
      "label": "End: Product Released",
      "type": "end",
      "next": []
    }}
  ]
}}

Types: "start", "action", "decision", "end"
Decision nodes must have exactly 2 next entries with "Yes"/"No" labels.
Generate 8-15 steps covering the full process with appropriate decision points."""


# Map section types to their prompt templates
_SECTION_PROMPTS = {
    "procedure_steps": PROCEDURE_STEPS_PROMPT,
    "equipment_list": EQUIPMENT_LIST_PROMPT,
    "references": REFERENCES_PROMPT,
    "attachments": ATTACHMENTS_PROMPT,
    "general_instructions": GENERAL_INSTRUCTIONS_PROMPT,
    "review_checklist": REVIEW_CHECKLIST_PROMPT,
    "deviation_description": DEVIATION_DESCRIPTION_PROMPT,
    "capa": CAPA_PROMPT,
    "change_control": CHANGE_CONTROL_PROMPT,
    "flowchart": FLOWCHART_GENERATION_PROMPT,
}


def get_section_prompt(section_type: str, context: dict,
                       custom_prompt: Optional[str] = None) -> str:
    """Get the formatted prompt for a given section type.

    Args:
        section_type: Key from _SECTION_PROMPTS
        context: Dict with template variables (product_name, process_type, etc.)
        custom_prompt: Optional override template string

    Returns:
        Formatted prompt string
    """
    template = custom_prompt or _SECTION_PROMPTS.get(section_type)
    if template is None:
        raise ValueError(f"Unknown section type: {section_type}")

    # Fill in available context variables, leave missing ones as placeholders
    try:
        return template.format(**context)
    except KeyError as e:
        # Fill missing keys with placeholder text
        import re
        placeholders = re.findall(r"\{(\w+)\}", template)
        filled_context = {k: context.get(k, f"[{k}]") for k in placeholders}
        return template.format(**filled_context)
