# Protocols module — feature inventory & roadmap

Goal: SmartSOP = **all protocols.io capabilities + the existing GMP/AI features**.

This inventory was reconstructed from the `protocols.io` webinar screenshots
(Desktop/protocols.io) — labels below are verbatim from the product.

Legend: ✅ built · 🚧 in progress · ⬜ planned

---

## 1. Protocol authoring (editor)

| Feature | Status |
|---|---|
| Protocol with title, abstract/description, author, version | ✅ |
| Ordered steps with instruction text | ✅ |
| Step components: Duration, Safety Information, Reagent | ✅ (basic) |
| **Typed component library** (LOTO/GMP: 13 blocks — Duration, Temperature, Amount, Equipment, Reagent, Safety, PPE, Hazard, Verification, Critical Control, etc.) with icons + flags | ✅ |
| Add / reorder / delete steps | ✅ |
| **Sections** + **sub-steps** (`1`, `2`, `2.1`) with rolled-up durations | ⬜ |
| **Full component set (28)**: `Amount`, `Sample`, `Concentration`, `Temperature`, `Duration`, `Protocol`, `Document`, `Equipment`, `Reagent`, `Command`, `Citation`, `Dataset`, `Software`, `Note`, `Safety Information`, `Expected Result`, `Geo. Coordinates`, `Centrifugation`, `Smart Component`, `Shaker`, `Spectral Data`, `Goto`, `PH`, `Cost`, `Pressure`, `Thickness`, `Relative Humidity`, `Well Plate Map` | ⬜ |
| Components as **inline atoms** in step prose (`🧪 10 µL`, `⏱ 00:05:00`, `🌡 60 °C`) | ⬜ |
| Reagent picker w/ vendor catalog, `Catalog #`, `CAS number`, `RRID`, `Home-made` | ⬜ |
| Equipment card (`NAME` / `TYPE` / `BRAND`) | ⬜ |
| **Step cases** (conditional branching: `Choose a case` → jump / halt / continue) | ✅ |
| Rich text toolbar (bold/italic/link/image/video/attachment/code/table/lists) | ⬜ |
| Doc tabs: `Description`, `Guidelines & Warnings`, `References`, `Materials`, `Acknowledgements`, `Troubleshooting` | ⬜ |
| Autosave (`Saving…` → `All changes saved`) | ✅ (save on blur) |
| Multi-user presence | ⬜ |
| Per-step **history / audit trail** (`Change step #2.1`, actor + timestamp) | ⬜ |

## 2. Running protocols (execution) — **the defining feature**

| Feature | Status |
|---|---|
| `New run record` modal: `Start run` vs `Create a completed record` (back-dated) | ✅ |
| Run filed into a workspace **folder**; run is a first-class record | ⬜ |
| `/run/<id>` route with step cursor (`?step=1`) | ✅ |
| Per-step outcomes: **`Done` / `Fail` / `Skip`** (not a binary checkbox) | ✅ |
| Per-step **timers**: `Start ▸`, `Refresh ⟳`, live countdown | ✅ |
| Progress ring `N out of M` + total countdown | ✅ |
| `Suggested Run Time` recalculating as steps complete | ✅ |
| `Experiment ID` field | ✅ |
| Completion stamps: `Done` + timestamp + `by <user>` | ✅ |
| `Finish Run`; run tabs `Steps`/`Materials`/`Comments`/`History`/`Metadata` | ✅ |
| Edit steps mid-run | ⬜ |
| `Make fork from run` | ⬜ |

## 3. Versioning, forking, publishing

| Feature | Status |
|---|---|
| Controlled lifecycle: draft → in_review → approved → effective → retired | ✅ |
| Versioning: version numbers + supersedes chain (new-version clones) | ✅ (basic) |
| `Copy / Fork` + `Forks` tab | ⬜ |
| `New Merge Request` (fork-and-merge contribution) | ⬜ |
| **Publish wizard** (6 steps): `Complete your protocol`, `Authors and Funders`, `Comments and Additional`, `Workspaces`, `Preview`, `Confirmation` | ⬜ |
| **DOI**: `Reserve DOI`, minted per version (`10.17504/protocols.io.<id>/vN`) | ⬜ |
| `Cite this` modal: formatted citation, copy, download (RIS/BibTeX) | ⬜ |
| Anonymous **reviewer private link** (`/private/<token>`) | ⬜ |
| `Sign` (e-signature, password re-auth, meaning, audit trail) | ✅ |
| `Post draft`, `Peer Review options` | ⬜ |
| Public view w/ globe icon; `Change language` | ⬜ |

## 4. Comments & collaboration

| Feature | Status |
|---|---|
| Per-step comments (anchored, rich text, `Private comment`) | ⬜ |
| Protocol-level comments; `/comments` page | ⬜ |
| Filters `All` / `Step-level` / `Protocol-level` w/ counts; search | ⬜ |
| Threaded `Reply`; pinned comments | ⬜ |
| **AI generated summary** of comment thread + topic chips | ⬜ |

## 5. AI (leverages the existing Ollama + Celery pipeline)

| Feature | Status |
|---|---|
| **`protocolify`** — create a protocol from an uploaded file/text | ✅ |
| Paste-to-steps: `Each number is a step` / `Each line is a step` / `Markdown text` | ✅ |
| `Troubleshooting` tab — AI Q&A scoped to a protocol | ⬜ |
| `Refine a protocol` (magic wand) | ⬜ |
| AI comment summarisation + auto topic tagging | ⬜ |
| _Existing SmartSOP AI: section generation, paper import (PubMed)_ | ✅ |

## 6. Workspace / file manager

| Feature | Status |
|---|---|
| Workspaces (= accounts) w/ members + roles | ✅ |
| Public vs Private/Internal; membership `Open to all`/`By request`/`By invitation only` | ⬜ |
| **File manager**: folders, tree, `+ New`, `Recent files`, `Trash`, storage used | ⬜ |
| Table cols: `Type`, `Name`, `Version`, `Size`, `Last modified`, `Owner`; filters | ⬜ |
| Detail pane: `View`/`Share`/`Copy`/`Make fork from run`/`Export`/`Move to…`/`Trash` | ⬜ |
| Collections; metrics (likes / bookmarks / views); `Metrics` tab | ⬜ |

## 7. Export & integrations

| Feature | Status |
|---|---|
| Export **format × destination**: `JSON`, `PDF` → `To your computer`, `Box`, `Google Drive`, `LabArchives`, `SciSure` | ⬜ |
| _Existing: DOCX generation engine (reuse for protocol export)_ | ✅ |
| Settings → `Apps` integration toggles | ⬜ |
| Settings: `General`, `Security and Privacy`, `Email Notifications`, `Workspaces`, `Active sessions` | ⬜ (partial) |
| **SSO** (OIDC/OAuth2 — Okta, Azure AD, Google, Auth0, Keycloak): login button, IdP redirect, callback, auto-provision users | ✅ |

## 8. Analytics & reporting

| Feature | Status |
|---|---|
| **Analytics dashboard**: total protocols/runs, completion rate, outcome breakdown (Done/Fail/Skip), avg run duration, runs-by-week trend, top protocols | ✅ |
| Deviation / failure reporting drill-down | ✅ |
| Per-user / per-workspace activity reports | ⬜ |

## 9. Field execution & compliance (from the competitive-strategy research)

See `docs/competitive_strategy.pdf`. Note its "SmartSOP today" scorecard predates
the run-mode / typed-block / lifecycle / SSO work and is stale.

| Feature | Status |
|---|---|
| **Deviation / corrective action (CAPA)**: flag mid-run, severity, triage to resolution | ✅ |
| **Asset / equipment library**: hazard class, energy sources, linked SOPs | ✅ |
| **QR tags**: printable per-asset QR → `/scan/<slug>` opens that asset's hazards + SOPs | ✅ |
| **Regulatory template packs** (OSHA 1910.147 / 1910.146, NFPA 70E, HACCP) | ✅ |
| **Empty-state onboarding** — new workspace opens on the template gallery | ✅ |
| Responsive shell (sidebar collapses to a top bar on phones) | ✅ |
| **Version history + diff + rollback** ("what changed between v3 and v4", restore a prior version) | ✅ |
| **Task manager / scheduling** (assign a run, due dates, recurring PM, start→run) | ✅ |
| Offline mobile execution (local cache + sync-on-reconnect) | ⬜ |
| Inline comments + concurrent editing | ⬜ |
| Training & competency (assign SOP, quiz, expiry tracking) | ⬜ |
| Public REST API + webhooks | ⬜ |
| AI: video/voice → SOP | ⬜ |
| AI: semantic search ("SOP Finder") | ⬜ |
| AI: bilingual EN-ES rendering | ⬜ |
| AI: deviation assistant (suggest root cause / next action) | ⬜ |

---

## Build order

1. **Run mode** (§2) — the defining capability. 🚧
2. **Sections + sub-steps + full component set** (§1) — depth of the editor.
3. **AI import / protocolify + paste-to-steps** (§5) — we already have the LLM pipeline.
4. **Versioning + fork + publish wizard + export** (§3, §7) — reuse the DOCX engine.
5. **Comments + AI summary** (§4).
6. **File manager / folders / collections** (§6).
