"""LLM prompt templates for GMP document content generation."""

from typing import Optional


GMP_SYSTEM_PROMPT = (
    "You are a GMP documentation specialist for pharmaceutical and biotech "
    "manufacturing. You generate precise, regulatory-compliant content for "
    "batch records, SOPs, deviation reports, CAPA forms, and change controls. "
    "Use technical language appropriate for cell therapy, biologics, and "
    "pharmaceutical manufacturing. Be specific, detailed, and follow "
    "21 CFR Part 211 and EU GMP Annex guidelines.\n\n"
    "HARD RULES FOR JSON OUTPUT:\n"
    "1. Return a single JSON object and nothing else. No prose before or "
    "   after. No ```json fences.\n"
    "2. Follow the exact shape shown in the prompt's examples — same keys, "
    "   same types, same nesting.\n"
    "3. If you don't know a value, use a realistic placeholder (e.g. "
    "   'TBD by supervisor', 'As Needed', '[to be assigned]'). Do NOT "
    "   return null or empty strings for required fields.\n"
    "4. Use passive voice and imperative verbs appropriate for GMP "
    "   procedures ('The operator shall…', 'Verify that…', 'Record the…')."
)


PROCEDURE_STEPS_PROMPT = """Generate 8–15 detailed manufacturing procedure steps.

Product: {product_name}
Process: {process_type}
Description: {description}

SCHEMA (return JSON matching this shape exactly):
{{
  "steps": [
    {{
      "number": "<string like '5.1'>",
      "title": "<short section title>",
      "instructions": [
        {{
          "text": "<one instruction, imperative voice>",
          "type": "action" | "verification" | "record" | "calculation",
          "bsc": <true if inside a Biosafety Cabinet>,
          "options": ["Yes - ...", "No - ..."],         // only for type=verification
          "variables": [                                  // only for type=record
            {{"name": "<field>", "type": "text|number|date|time", "format": "HHMM"}}
          ],
          "formula": "<e.g. Step 5.2 / Step 5.1 * 100>"   // only for type=calculation
        }}
      ]
    }}
  ]
}}

INSTRUCTION TYPE GUIDE:
  action        – the operator DOES something ("Attach label", "Open bag port")
  verification  – a yes/no gate ("Does value fall within spec?") with options[]
  record        – capture a measurement/ID/time — MUST include variables[]
  calculation   – a computed value referencing other steps — MUST include formula

TWO CONCRETE EXAMPLES:

EXAMPLE 1 (CD8+ Enrichment — step 5.1 "Setup"):
{{
  "steps": [
    {{
      "number": "5.1", "title": "Setup and Equipment Staging",
      "instructions": [
        {{"text": "Don PPE per gowning SOP GN-012.", "type": "action", "bsc": false}},
        {{"text": "[BSC] Wipe interior surfaces with 70% IPA, top-down.",
          "type": "action", "bsc": true}},
        {{"text": "Does the sample label match Part No., Lot No., and Subject ID for this BR?",
          "type": "verification", "bsc": false,
          "options": ["Yes - Proceed", "No - Notify supervisor"]}},
        {{"text": "Record room number, equipment ID, and start time.",
          "type": "record", "bsc": false,
          "variables": [
            {{"name": "Room Number", "type": "text"}},
            {{"name": "Equipment ID", "type": "text"}},
            {{"name": "Start Time", "type": "time", "format": "HHMM"}}
          ]}}
      ]
    }}
  ]
}}

EXAMPLE 2 (Viability calculation):
{{
  "steps": [
    {{
      "number": "7.3", "title": "Post-Thaw Viability",
      "instructions": [
        {{"text": "Remove 50 µL aliquot and mix 1:1 with trypan blue.",
          "type": "action", "bsc": true}},
        {{"text": "Count viable and non-viable cells on hemocytometer.",
          "type": "record", "bsc": true,
          "variables": [
            {{"name": "Viable Count", "type": "number"}},
            {{"name": "Non-viable Count", "type": "number"}}
          ]}},
        {{"text": "Calculate % viability.",
          "type": "calculation", "bsc": false,
          "formula": "Viable / (Viable + Non-viable) * 100"}}
      ]
    }}
  ]
}}

REQUIREMENTS:
- Include realistic BSC operations for any aseptic cell-handling process.
- Include at least one verification and one record step.
- Number sequentially (5.1, 5.2, 5.3 …) or by section (5.1, 5.2; 6.1, 6.2).
- Each instruction.text should be a single imperative sentence (≤ 25 words)."""


EQUIPMENT_LIST_PROMPT = """Generate the equipment and materials required.

Product: {product_name}
Process: {process_type}
Description: {description}

SCHEMA:
{{
  "equipment": [
    {{
      "description": "<equipment name>",
      "requires_id": <true if the operator records a serial/ID>,
      "requires_service_date": <true if last-service date must be recorded>
    }}
  ],
  "materials": [
    {{
      "part_number": "<org part number like 'B095-03'>",
      "description": "<material name with concentration/size if applicable>",
      "quantity": "<integer, 'As Needed', or 'N/A'>"
    }}
  ]
}}

EXAMPLE (T-Cell enrichment from PBMC):
{{
  "equipment": [
    {{"description": "Biosafety Cabinet (ISO 5, Class II Type A2)", "requires_id": true, "requires_service_date": true}},
    {{"description": "CliniMACS Prodigy", "requires_id": true, "requires_service_date": true}},
    {{"description": "Benchtop centrifuge (swing-bucket, refrigerated)", "requires_id": true, "requires_service_date": true}},
    {{"description": "Cell counter with hemocytometer", "requires_id": true, "requires_service_date": false}},
    {{"description": "TSCD (Total Sterile Connecting Device)", "requires_id": true, "requires_service_date": false}},
    {{"description": "Liquid nitrogen Dewar", "requires_id": true, "requires_service_date": true}}
  ],
  "materials": [
    {{"part_number": "B095-03", "description": "Leukapheresis product (source material)", "quantity": "1"}},
    {{"part_number": "F184-01", "description": "X-Vivo 15 media (40 mL aliquots)", "quantity": "As Needed"}},
    {{"part_number": "R221-00", "description": "CliniMACS CD8 Microbeads (7.5 mL)", "quantity": "1"}},
    {{"part_number": "T091-05", "description": "CliniMACS PBS/EDTA buffer (100 mL)", "quantity": "2"}},
    {{"part_number": "B412-02", "description": "CryoStor CS10 (100 mL)", "quantity": "As Needed"}},
    {{"part_number": "L055-01", "description": "Trypan Blue 0.4%", "quantity": "As Needed"}}
  ]
}}

REQUIREMENTS:
- At least 4 equipment items and 4 materials for any aseptic cell process.
- Use org-style part number prefixes: B- (biologics), F- (fluid), R- (reagent),
  T- (tubing/connectors), C- (consumable), E- (equipment).
- Quantity must be one of: a positive integer string, "As Needed", or "N/A"."""


REFERENCES_PROMPT = """Generate 4–10 referenced SOPs and controlled documents.

Document Type: {doc_type}
Product: {product_name}
Process: {process_type}
Description: {description}

SCHEMA:
{{
  "references": [
    {{ "doc_number": "<GMP doc number>", "title": "<document title>" }}
  ]
}}

EXAMPLE (batch record for cell enrichment):
{{
  "references": [
    {{"doc_number": "EQ-002", "title": "Operation and Maintenance of Biological Safety Cabinets"}},
    {{"doc_number": "EQ-014", "title": "Operation of CliniMACS Prodigy"}},
    {{"doc_number": "GN-005", "title": "Aseptic Technique for Cell Processing"}},
    {{"doc_number": "GN-012", "title": "Gowning and PPE for Manufacturing Areas"}},
    {{"doc_number": "PR-010", "title": "Cell Processing and Cryopreservation"}},
    {{"doc_number": "QA-022", "title": "Deviation Reporting and Investigation"}},
    {{"doc_number": "TM-008", "title": "Cell Count and Viability by Trypan Blue Exclusion"}}
  ]
}}

NUMBERING CONVENTION (use these prefixes):
  EQ-  equipment operation / maintenance
  GN-  general / foundational SOPs
  PR-  processing / manufacturing
  QA-  quality assurance
  TM-  test methods
  FR-  forms"""


ATTACHMENTS_PROMPT = """Generate 2–5 attachments referenced by this document.

Product: {product_name}
Process: {process_type}
Description: {description}
References: {references}

SCHEMA:
{{
  "attachments": [
    {{ "doc_number": "Attachment N", "title": "<name>", "quantity": <int> }}
  ]
}}

EXAMPLE:
{{
  "attachments": [
    {{"doc_number": "Attachment 1", "title": "Sample Plan", "quantity": 1}},
    {{"doc_number": "Attachment 2", "title": "Test Summary Sheet", "quantity": 1}},
    {{"doc_number": "Attachment 3", "title": "Equipment Qualification Checklist", "quantity": 1}},
    {{"doc_number": "Attachment 4", "title": "Cryopreservation Label", "quantity": 4}}
  ]
}}"""


GENERAL_INSTRUCTIONS_PROMPT = """Generate 5–8 general instructions that apply to the whole batch record.

Process: {process_type}
Product: {product_name}

SCHEMA:
{{
  "instructions": [
    "<one rule per item, complete sentence, 10–30 words>"
  ]
}}

EXAMPLE (aseptic cell processing):
{{
  "instructions": [
    "Instructions preceded by [BSC] describe operations performed inside an ISO 5 Biosafety Cabinet to maintain aseptic conditions.",
    "Sanitize all bag ports, vial septa, and tubing penetrations with 70% IPA before making any sterile connection.",
    "Centrifugations shall use a counter-balanced second container matching the test tube mass within 1 g.",
    "Record every deviation from the procedure — no matter how minor — in the Deviations section on the back page.",
    "All timed steps must be recorded using 24-hour format (HHMM). Tolerance is ±2 minutes unless otherwise specified."
  ]
}}

REQUIREMENTS:
- Cover aseptic technique, labeling, equipment, deviations, and timing at minimum.
- Each instruction is a standalone rule; avoid pronouns like 'it', 'this'.
- Use imperative voice ('Sanitize…', 'Record…', 'Verify…')."""


REVIEW_CHECKLIST_PROMPT = """Generate a 6–10 item manufacturing review checklist.

Process: {process_type}
Product: {product_name}

SCHEMA:
{{
  "checklist_items": [
    "<one reviewable item per line, 4–15 words, noun-phrase style>"
  ]
}}

EXAMPLE:
{{
  "checklist_items": [
    "Label and expiration date verified against Part No. and Lot No.",
    "All equipment IDs, service dates, and calibration status recorded",
    "Every processing step completed and signed by Manufacturing Technician",
    "All calculations checked and signed by a second technician",
    "Deviations identified, documented, and routed per QA-022",
    "Material consumption reconciled against Title 21 inventory",
    "Post-process sample pulled and labeled per Sample Plan",
    "Document reviewed end-to-end and signed by QA"
  ]
}}

REQUIREMENTS:
- Cover at least: labels, equipment, steps, calculations, deviations, materials.
- Each item is a single noun phrase describing something a reviewer checks,
  not a procedure step."""


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

NODE TYPES:
  start     – exactly ONE start node in the graph
  action    – a single operator action or process step
  decision  – a Yes/No gate, MUST have exactly 2 next entries with "Yes"/"No" labels
  end       – at least ONE end node; end nodes have "next": []

RULES (must all hold):
- Every "next.target_id" must reference a declared step id (no dangling edges).
- Node ids are short strings, usually "1", "2", "3a", "3b"…
- Decision labels must be short (1–3 words); use \\n in a label to force a wrap.
- Generate 6–15 nodes total. Include at least one decision point."""


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
