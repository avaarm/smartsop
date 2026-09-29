"""Facility document templates — the "smart template per task" content.

A pre-established GMP facility writes each new document from a standard template
(or an existing similar document). These built-in templates encode the structure
that facility's own SOPs mandate — e.g. Fred Hutch TPP DC-004 for batch records
and master production specifications — so picking "what do you want to write?"
lands the user on a correctly-structured document, not a blank page.

Batch-record templates are document-format (body blocks: headings, tables,
paragraphs) with {{fill-in}} fields. Procedure templates can be either. Every
template lands as a draft that still goes through review/approval.
"""

# ── reusable block fragments (DC-004 §8.4, §9.2.1) ──────────────────────────

def _approval_table():
    return {"type": "table", "rows": [
        ["APPROVED BY", "", "", ""],
        ["Document Owner:", "{{document_owner}}", "Date:", ""],
        ["Technical Authority:", "{{technical_authority}}", "Date:", ""],
        ["TPP Facility Director:", "{{facility_director}}", "Date:", ""],
        ["Quality Assurance:", "{{quality_assurance}}", "Date:", ""],
    ]}


def _references_section():
    return [
        {"type": "heading", "level": 1, "text": "1. REFERENCES"},
        {"type": "paragraph", "text": "List all documents referenced in this record — document number in CAPS, title in italics, alphanumeric order. Do not include the revision level."},
        {"type": "table", "rows": [["Document Number", "Title"], ["", ""], ["", ""]]},
    ]


def _attachments_section(n):
    return [
        {"type": "heading", "level": 1, "text": f"{n}. ATTACHMENTS"},
        {"type": "paragraph", "text": "List each attachment used to execute this record — document number in CAPS, title in italics, and number of copies needed in parentheses. List BR attachments first, then SOP attachments."},
        {"type": "table", "rows": [["Document Number", "Title", "Copies"], ["", "", ""]]},
    ]


def _general_instruction_section(n):
    return [
        {"type": "heading", "level": 1, "text": f"{n}. GENERAL INSTRUCTION"},
        {"type": "paragraph", "text": "Provide any useful context, facts, or background that orients the operator before executing the process."},
    ]


def _equipment_materials_section(n):
    return [
        {"type": "heading", "level": 1, "text": f"{n}. EQUIPMENT / MATERIALS LIST"},
        {"type": "paragraph", "text": "List equipment (alphanumeric) and all part-numbered materials in tabular format, ordered by Material ID Number."},
        {"type": "table", "rows": [
            ["Item #", "Material ID Number", "Description", "Quantity"],
            ["1", "", "", ""],
            ["2", "", "", ""],
        ]},
    ]


def _header_table(rows):
    return {"type": "table", "rows": rows}


# ── the templates ───────────────────────────────────────────────────────────

DOC_TEMPLATES = [
    {
        "key": "br_production",
        "name": "Production Batch Record",
        "doc_category": "BR",
        "protocol_type": "gmp_sop",
        "doc_format": "document",
        "description": "Manufacturing instructions for a clinical protocol / IND. Structured per DC-004: references, attachments, general instruction, process flow, equipment/materials, processing steps.",
        "standard": "DC-004 §9.2.1",
        "body": [
            {"type": "heading", "level": 1, "text": "{{product}} Production Batch Record"},
            _header_table([
                ["Document Number:", "{{document_number}}", "Revision Number:", "00"],
                ["Effective Date:", "", "Page:", "1 of __"],
                ["Part Number:", "{{part_number}}", "Lot Number:", "{{lot_number}}"],
                ["Subject ID:", "{{subject_id}}", "Protocol Number:", "{{protocol_number}}"],
            ]),
            _approval_table(),
            *_references_section(),
            *_attachments_section(2),
            *_general_instruction_section(3),
            {"type": "heading", "level": 1, "text": "4. PROCESS FLOW"},
            {"type": "paragraph", "text": "Insert a process-flow diagram (Visio / flowchart) that outlines the batch-record process."},
            *_equipment_materials_section(5),
            {"type": "heading", "level": 1, "text": "6. PROCESSING STEPS"},
            {"type": "paragraph", "text": "Write each instruction in the active voice (begin with an action word). Provide a results space to record data instead of a checkbox. Add equations for any calculation. Keep sub-steps to four levels or fewer."},
        ],
    },
    {
        "key": "br_formulation",
        "name": "Formulation Batch Record",
        "doc_category": "BR",
        "protocol_type": "gmp_sop",
        "doc_format": "document",
        "description": "Instructions for formulating / aliquoting reagents used in production. Includes the DC-004 EXPIRATION section for storage temperature & expiration dating.",
        "standard": "DC-004 §9.2.1, §8.8",
        "body": [
            {"type": "heading", "level": 1, "text": "{{product}} Formulation Batch Record"},
            _header_table([
                ["Document Number:", "{{document_number}}", "Revision Number:", "00"],
                ["Effective Date:", "", "Page:", "1 of __"],
                ["Part Number:", "{{part_number}}", "Lot Number:", "{{lot_number}}"],
            ]),
            _approval_table(),
            *_references_section(),
            *_attachments_section(2),
            *_general_instruction_section(3),
            *_equipment_materials_section(4),
            {"type": "heading", "level": 1, "text": "5. FORMULATION / PROCESSING STEPS"},
            {"type": "paragraph", "text": "Provide target volumes, batch size and aliquot size per the schedule. Take an archival sample (≥1 mL) after formulation and before aliquoting when applicable."},
            {"type": "heading", "level": 1, "text": "6. EXPIRATION"},
            {"type": "paragraph", "text": "Provide storage temperature and expiration dating, and document the preparation and calculated expiration dates. Expiration dates are based on storage temperature per the material category (DC-004 Table 2)."},
            {"type": "table", "rows": [
                ["Material", "Storage Temp", "Date Prepared", "Expiration Date"],
                ["", "", "", ""],
            ]},
        ],
    },
    {
        "key": "mps",
        "name": "Master Production Specification (MPS)",
        "doc_category": "BR",
        "protocol_type": "gmp_sop",
        "doc_format": "document",
        "description": "Protocol/project-specific record of Incoming Products Received & Lot Numbers and Subject Identification, per DC-004.",
        "standard": "DC-004 Table 1",
        "body": [
            {"type": "heading", "level": 1, "text": "{{product}} Master Production Specification"},
            _header_table([
                ["Document Number:", "{{document_number}}", "Revision Number:", "00"],
                ["Effective Date:", "", "Page:", "1 of __"],
                ["Subject ID:", "{{subject_id}}", "Protocol Number:", "{{protocol_number}}"],
                ["IND Number:", "{{ind_number}}", "IND Sponsor:", "{{ind_sponsor}}"],
            ]),
            _approval_table(),
            {"type": "heading", "level": 1, "text": "1. PRODUCT DESCRIPTION"},
            {"type": "paragraph", "text": "Describe the product this specification governs."},
            *_references_section(),
            {"type": "heading", "level": 1, "text": "3. INCOMING PRODUCTS RECEIVED"},
            {"type": "paragraph", "text": "Record each incoming product, its lot number and expiration."},
            {"type": "table", "rows": [
                ["Material", "Part Number", "Lot Number", "Expiration", "Received By"],
                ["", "", "", "", ""],
            ]},
        ],
    },
    {
        "key": "tm_test_method",
        "name": "Analytical Test Method",
        "doc_category": "TM",
        "protocol_type": "gmp_sop",
        "doc_format": "document",
        "description": "A characterization / release test method — purpose, scope, references, equipment & reagents, procedure, acceptance criteria, data recording.",
        "standard": "GMP",
        "body": [
            {"type": "heading", "level": 1, "text": "{{method_name}}"},
            _header_table([
                ["Document Number:", "{{document_number}}", "Revision Number:", "00"],
                ["Effective Date:", "", "Page:", "1 of __"],
            ]),
            _approval_table(),
            {"type": "heading", "level": 1, "text": "1. PURPOSE"},
            {"type": "paragraph", "text": "State what this method measures and why."},
            {"type": "heading", "level": 1, "text": "2. SCOPE"},
            {"type": "paragraph", "text": "State the samples / products this method applies to."},
            *_references_section(),
            {"type": "heading", "level": 1, "text": "4. EQUIPMENT & REAGENTS"},
            {"type": "table", "rows": [["Item", "ID / Catalog #", "Description"], ["", "", ""]]},
            {"type": "heading", "level": 1, "text": "5. PROCEDURE"},
            {"type": "paragraph", "text": "Write each step in the active voice. Provide equations for any calculation."},
            {"type": "heading", "level": 1, "text": "6. ACCEPTANCE CRITERIA & DATA"},
            {"type": "paragraph", "text": "State the acceptance criteria and provide a space to record results."},
        ],
    },
    {
        "key": "eq_operation",
        "name": "Equipment Operation & Maintenance SOP",
        "doc_category": "EQ",
        "protocol_type": "gmp_sop",
        "doc_format": "document",
        "description": "Operation, maintenance and calibration of an instrument — purpose, scope, references, safety, operation, maintenance & calibration schedule.",
        "standard": "GMP",
        "body": [
            {"type": "heading", "level": 1, "text": "Operation & Maintenance of {{equipment_name}}"},
            _header_table([
                ["Document Number:", "{{document_number}}", "Revision Number:", "00"],
                ["Effective Date:", "", "Page:", "1 of __"],
            ]),
            _approval_table(),
            {"type": "heading", "level": 1, "text": "1. PURPOSE"},
            {"type": "paragraph", "text": "State what this SOP covers for the equipment."},
            {"type": "heading", "level": 1, "text": "2. SCOPE"},
            {"type": "paragraph", "text": "State where and to which equipment this applies."},
            *_references_section(),
            {"type": "heading", "level": 1, "text": "4. SAFETY"},
            {"type": "paragraph", "text": "Describe hazards and required PPE / precautions."},
            {"type": "heading", "level": 1, "text": "5. OPERATION"},
            {"type": "paragraph", "text": "Write the operating steps in the active voice."},
            {"type": "heading", "level": 1, "text": "6. MAINTENANCE & CALIBRATION"},
            {"type": "table", "rows": [
                ["Task", "Frequency", "Performed By"],
                ["", "", ""],
            ]},
        ],
    },
    {
        "key": "vp_protocol",
        "name": "Validation / Qualification Protocol",
        "doc_category": "VP",
        "protocol_type": "gmp_sop",
        "doc_format": "document",
        "description": "IQ/OQ/PQ or process/cleaning validation protocol — purpose, scope, responsibilities, acceptance criteria, test procedures, results & approval.",
        "standard": "GMP",
        "body": [
            {"type": "heading", "level": 1, "text": "{{system_name}} Validation Protocol"},
            _header_table([
                ["Document Number:", "{{document_number}}", "Revision Number:", "00"],
                ["Effective Date:", "", "Page:", "1 of __"],
            ]),
            _approval_table(),
            {"type": "heading", "level": 1, "text": "1. PURPOSE"},
            {"type": "paragraph", "text": "State what is being qualified/validated and the objective."},
            {"type": "heading", "level": 1, "text": "2. SCOPE"},
            {"type": "paragraph", "text": "Define the boundaries of the validation."},
            {"type": "heading", "level": 1, "text": "3. RESPONSIBILITIES"},
            {"type": "table", "rows": [["Role", "Responsibility"], ["", ""]]},
            *_references_section(),
            {"type": "heading", "level": 1, "text": "5. ACCEPTANCE CRITERIA"},
            {"type": "paragraph", "text": "State the criteria that constitute a passing result."},
            {"type": "heading", "level": 1, "text": "6. TEST PROCEDURES & RESULTS"},
            {"type": "table", "rows": [
                ["Test #", "Test / Step", "Acceptance Criteria", "Result", "Pass/Fail"],
                ["1", "", "", "", ""],
            ]},
        ],
    },
]

_BY_KEY = {t["key"]: t for t in DOC_TEMPLATES}


def doc_template_summaries():
    """Gallery listing — no bodies."""
    out = []
    for t in DOC_TEMPLATES:
        out.append({
            "key": t["key"],
            "name": t["name"],
            "doc_category": t["doc_category"],
            "protocol_type": t["protocol_type"],
            "doc_format": t["doc_format"],
            "description": t["description"],
            "standard": t.get("standard", ""),
        })
    return out


def get_doc_template(key):
    return _BY_KEY.get(key)
