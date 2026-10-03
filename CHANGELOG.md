# Changelog

All notable changes to SmartSOP. Dates are ISO (UTC).

## [Unreleased]

### Added
- **Global SOP search** in the top navigation — works from any page, routes to
  the Protocols finder via `?q=` (shareable by URL).
- **Document number** surfaced in the detail header (badge) and in PDF exports;
  the Fill-in & export dialog pre-fills `{{document_number}}` and `{{revision}}`.
- Accessibility: `aria-current="page"` on the active top-nav tab.

### Changed
- Landing page (avaarm.github.io/smartsop) rebranded to the app's indigo and
  repositioned to the client+server product; download cards link straight to the
  latest release's installers and auto-track future releases.

### Fixed
- CI: backend tests now import under a bare `pytest` invocation (`pythonpath`),
  turning the pipeline green (frontend + backend + Docker build).
- Desktop release workflow: unsigned macOS builds no longer fail on empty signing
  env; `contents: write` lets the release publish; dmg-only avoids the hdiutil race.

### Removed
- Dead legacy ELN module (11 unreferenced components + service with a hardcoded
  localhost API base).

### Tests
- Edge cases (render/original error paths, numbering, register filters) and
  multi-tenant isolation for the document endpoints. 235 backend tests.

## [1.1.2] — 2026-10-02

The first release with downloadable desktop apps and the full GMP document-control
feature set.

### Added
- **Desktop clients for macOS & Windows** (Electron) that connect to a SmartSOP
  server — first-run connect screen, native menus, auto-update wiring. Built and
  published via CI on version tags.
- **One-command self-hosted deploy** — `deploy.sh` + `docker-compose.prod.yml`
  bring up the full stack behind Caddy with automatic HTTPS, on any Docker host
  (cloud or on-prem). See `DEPLOY.md`.
- **Document-fidelity import** — upload Word/PDF SOPs and batch records; tables,
  headings, approval blocks and checkboxes are preserved 1:1. Fill in
  `{{variables}}` and export a `.docx` that matches the original; download the
  original any time; document-aware PDF export.
- **Facility document taxonomy** and a **"what do you want to write?" picker** —
  categories (EQ, QA, QC, TM, VP, BR…) with built-in, DC-004-accurate templates
  (Production/Formulation batch records, MPS, test method, equipment O&M,
  validation protocol).
- **Controlled-document register** — effective batch records grouped by protocol,
  procedures by category — and **auto document numbering** (EQ-002, QA-005…).
- **Top navigation bar** (protocols.io-style) replacing the sidebar.

## [1.1.1] / [1.1.0] — 2026-10-02

- Iterations of the desktop release pipeline (superseded by 1.1.2).

## [1.0.1] / [1.0.0] — 2026-04

- Initial GMP document builder, controlled-document lifecycle with 21 CFR Part 11
  e-signatures, audit trail, protocols/run mode, assets & QR, scheduling,
  deviations, competency/training, analytics, multi-tenant workspaces, and the
  initial landing page.
