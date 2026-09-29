"""The document taxonomy of a real GMP facility.

A pre-established cell/gene-therapy or CMC facility does not invent structure per
project — it files everything under a fixed set of controlled-document categories
(EQ, QA, QC, TM, VP, …) and groups batch records by protocol / part number. This
module encodes that taxonomy so the app can mirror the facility a user already
knows: browse by category, and — the point — pick "what am I writing?" and get
the matching template.

Codes match the conventional GMP document-number prefixes (EQ-002, QA-005, …).
Names/examples are sensible defaults an org can rename; the codes are the anchor.
"""

# kind: "procedure" (a controlled procedure/SOP) or "record" (a batch record).
# examples: the concrete tasks a person writes in this category — this is what
# drives the "what do you want to write?" picker.
GMP_CATEGORIES = [
    {"code": "BR", "name": "Batch Records", "kind": "record",
     "description": "Executed manufacturing records for a specific protocol / product.",
     "examples": ["Master batch record", "Formulation record", "Fill-finish record"]},
    {"code": "PR", "name": "Production & Processing", "kind": "procedure",
     "description": "How the product is made, handled, and processed.",
     "examples": ["Cell thaw & culture", "Enrichment / selection", "Cryopreservation", "Aseptic processing"]},
    {"code": "QA", "name": "Quality Assurance", "kind": "procedure",
     "description": "Quality-system procedures and oversight.",
     "examples": ["Deviation management", "CAPA", "Change control", "Batch release / disposition"]},
    {"code": "QC", "name": "Quality Control", "kind": "procedure",
     "description": "Sampling, in-process and release testing operations.",
     "examples": ["In-process sampling", "Environmental monitoring", "Release testing"]},
    {"code": "TM", "name": "Test Methods", "kind": "procedure",
     "description": "Analytical and characterization methods.",
     "examples": ["Cell count & viability", "Flow cytometry assay", "Sterility", "Endotoxin", "Mycoplasma"]},
    {"code": "EQ", "name": "Equipment", "kind": "procedure",
     "description": "Operation, maintenance and calibration of instruments.",
     "examples": ["Instrument operation & maintenance", "Calibration", "Preventive maintenance"]},
    {"code": "VP", "name": "Validation Protocols", "kind": "procedure",
     "description": "Qualification and validation protocols and reports.",
     "examples": ["IQ / OQ / PQ", "Process validation", "Cleaning validation", "Method validation"]},
    {"code": "SP", "name": "Specifications", "kind": "procedure",
     "description": "Material, in-process and product specifications.",
     "examples": ["Raw material spec", "In-process spec", "Release specification"]},
    {"code": "ST", "name": "Stability", "kind": "procedure",
     "description": "Stability programs and study protocols.",
     "examples": ["Stability protocol", "Stability pull & test schedule"]},
    {"code": "FA", "name": "Facilities & Utilities", "kind": "procedure",
     "description": "Cleanroom, utilities and facility operations.",
     "examples": ["Gowning", "Cleanroom cleaning & sanitization", "Utility monitoring"]},
    {"code": "TR", "name": "Training", "kind": "procedure",
     "description": "Training and qualification of personnel.",
     "examples": ["Training procedure", "Operator qualification", "Read-and-understand"]},
    {"code": "DC", "name": "Document Control", "kind": "procedure",
     "description": "Control of documents and records.",
     "examples": ["Good documentation practices", "Document lifecycle", "Record retention"]},
    {"code": "RA", "name": "Regulatory Affairs", "kind": "procedure",
     "description": "Regulatory submissions and correspondence.",
     "examples": ["IND / CTA maintenance", "Regulatory reporting"]},
    {"code": "PL", "name": "Plans & Policies", "kind": "procedure",
     "description": "Program-level plans and quality policies.",
     "examples": ["Validation master plan", "Quality policy", "Project plan"]},
    {"code": "GN", "name": "General", "kind": "procedure",
     "description": "General procedures that don't fit another category.",
     "examples": ["General SOP"]},
]

_BY_CODE = {c["code"]: c for c in GMP_CATEGORIES}


def category(code):
    """Look up a category by code (case-insensitive), or None."""
    return _BY_CODE.get((code or "").strip().upper())


def category_name(code):
    """Human name for a code, falling back to the code itself."""
    c = category(code)
    return c["name"] if c else (code or "")


def is_valid(code):
    return (code or "").strip().upper() in _BY_CODE
