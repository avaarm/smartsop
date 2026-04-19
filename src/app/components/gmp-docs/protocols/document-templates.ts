/**
 * Known document templates (synced with backend ml_model/gmp/templates/*.json).
 * Keep the `id` values aligned with the filenames — they are what the backend
 * stores in ProtocolUpload.doc_type and what the Document Builder renders.
 */

export interface DocTemplate {
  /** Template ID (filename stem of the JSON template). */
  id: string;
  /** Human-readable display name. */
  name: string;
  /** Category bucket used to group templates in pickers. */
  category: string;
}

export const DOCUMENT_TEMPLATES: DocTemplate[] = [
  // Manufacturing (GMP)
  { id: 'annual_product_review', name: 'Annual Product Review (APR)', category: 'Manufacturing (GMP)' },
  { id: 'batch_record', name: 'Cell Processing Facility Batch Record', category: 'Manufacturing (GMP)' },
  { id: 'change_control_form', name: 'Change Control Form', category: 'Manufacturing (GMP)' },
  { id: 'deviation_form', name: 'Deviation / Nonconformance Form', category: 'Manufacturing (GMP)' },
  { id: 'equipment_qualification', name: 'Equipment Qualification Record', category: 'Manufacturing (GMP)' },
  { id: 'investigation_report', name: 'Investigation Report', category: 'Manufacturing (GMP)' },
  { id: 'sop', name: 'Standard Operating Procedure (SOP)', category: 'Manufacturing (GMP)' },

  // Clinical Trial
  { id: 'clinical_protocol', name: 'Clinical Trial Protocol (Phase 1)', category: 'Clinical Trial' },
  { id: 'crf_template', name: 'Case Report Form (CRF) Template', category: 'Clinical Trial' },
  { id: 'informed_consent', name: 'Informed Consent Form (ICF)', category: 'Clinical Trial' },
  { id: 'investigator_brochure', name: "Investigator's Brochure (IB)", category: 'Clinical Trial' },

  // Regulatory / IND
  { id: 'form_1571', name: 'FDA Form 1571 - IND Application', category: 'Regulatory / IND' },

  // CMC (Module 3)
  { id: 'cmc_drug_product', name: 'CMC Module 3.2.P - Drug Product', category: 'CMC (Module 3)' },
  { id: 'cmc_drug_substance', name: 'CMC Module 3.2.S - Drug Substance', category: 'CMC (Module 3)' },

  // Quality Systems
  { id: 'quality_agreement', name: 'Quality Agreement (Contract Manufacturer)', category: 'Quality Systems' },
  { id: 'quality_risk_assessment', name: 'Quality Risk Assessment (ICH Q9)', category: 'Quality Systems' },
  { id: 'tech_transfer', name: 'Technology Transfer Protocol', category: 'Quality Systems' },

  // Validation
  { id: 'cleaning_validation', name: 'Cleaning Validation Protocol', category: 'Validation' },
  { id: 'method_validation', name: 'Analytical Method Validation Protocol', category: 'Validation' },
  { id: 'process_validation', name: 'Process Performance Qualification (PPQ) Protocol', category: 'Validation' },
  { id: 'stability_protocol', name: 'Stability Study Protocol', category: 'Validation' },
  { id: 'validation_protocol', name: 'Validation Protocol (IQ/OQ/PQ)', category: 'Validation' },
];

/** Ordered list of category names (for grouping in a `<select>` via <optgroup>). */
export const TEMPLATE_CATEGORIES: string[] = [
  'Manufacturing (GMP)',
  'Clinical Trial',
  'Regulatory / IND',
  'CMC (Module 3)',
  'Quality Systems',
  'Validation',
];

/** Templates grouped by category in the same order as TEMPLATE_CATEGORIES. */
export const TEMPLATES_BY_CATEGORY: { category: string; templates: DocTemplate[] }[] =
  TEMPLATE_CATEGORIES.map(cat => ({
    category: cat,
    templates: DOCUMENT_TEMPLATES.filter(t => t.category === cat),
  }));

/** Look up the display name for a template ID (empty string if unknown). */
export function templateName(id: string): string {
  return DOCUMENT_TEMPLATES.find(t => t.id === id)?.name ?? '';
}

/** Look up the category for a template ID. */
export function templateCategory(id: string): string {
  return DOCUMENT_TEMPLATES.find(t => t.id === id)?.category ?? '';
}
