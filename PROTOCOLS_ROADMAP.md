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
| Add / reorder / delete steps | ✅ |
| **Sections** + **sub-steps** (`1`, `2`, `2.1`) with rolled-up durations | ⬜ |
| **Full component set (28)**: `Amount`, `Sample`, `Concentration`, `Temperature`, `Duration`, `Protocol`, `Document`, `Equipment`, `Reagent`, `Command`, `Citation`, `Dataset`, `Software`, `Note`, `Safety Information`, `Expected Result`, `Geo. Coordinates`, `Centrifugation`, `Smart Component`, `Shaker`, `Spectral Data`, `Goto`, `PH`, `Cost`, `Pressure`, `Thickness`, `Relative Humidity`, `Well Plate Map` | ⬜ |
| Components as **inline atoms** in step prose (`🧪 10 µL`, `⏱ 00:05:00`, `🌡 60 °C`) | ⬜ |
| Reagent picker w/ vendor catalog, `Catalog #`, `CAS number`, `RRID`, `Home-made` | ⬜ |
| Equipment card (`NAME` / `TYPE` / `BRAND`) | ⬜ |
| **Step cases** (conditional branching: `Choose a case`) | ⬜ |
| Rich text toolbar (bold/italic/link/image/video/attachment/code/table/lists) | ⬜ |
| Doc tabs: `Description`, `Guidelines & Warnings`, `References`, `Materials`, `Acknowledgements`, `Troubleshooting` | ⬜ |
| Autosave (`Saving…` → `All changes saved`) | ✅ (save on blur) |
| Multi-user presence | ⬜ |
| Per-step **history / audit trail** (`Change step #2.1`, actor + timestamp) | ⬜ |

## 2. Running protocols (execution) — **the defining feature**

| Feature | Status |
|---|---|
| `New run record` modal: `Start run` vs `Create a completed record` (back-dated) | 🚧 |
| Run filed into a workspace **folder**; run is a first-class record | ⬜ |
| `/run/<id>` route with step cursor (`?step=1`) | 🚧 |
| Per-step outcomes: **`Done` / `Fail` / `Skip`** (not a binary checkbox) | 🚧 |
| Per-step **timers**: `Start ▸`, `Refresh ⟳`, live countdown | 🚧 |
| Progress ring `N out of M` + total countdown | 🚧 |
| `Suggested Run Time` recalculating as steps complete | ⬜ |
| `Experiment ID` field | 🚧 |
| Completion stamps: `Done` + timestamp + `by <user>` | 🚧 |
| `Finish Run`; run tabs `Steps`/`Materials`/`Comments`/`History`/`Metadata` | 🚧 |
| Edit steps mid-run | ⬜ |
| `Make fork from run` | ⬜ |

## 3. Versioning, forking, publishing

| Feature | Status |
|---|---|
| Draft vs published status | ✅ (basic toggle) |
| Version history; version id in title (`V.(jm6vck9e7)`) | ⬜ |
| `Copy / Fork` + `Forks` tab | ⬜ |
| `New Merge Request` (fork-and-merge contribution) | ⬜ |
| **Publish wizard** (6 steps): `Complete your protocol`, `Authors and Funders`, `Comments and Additional`, `Workspaces`, `Preview`, `Confirmation` | ⬜ |
| **DOI**: `Reserve DOI`, minted per version (`10.17504/protocols.io.<id>/vN`) | ⬜ |
| `Cite this` modal: formatted citation, copy, download (RIS/BibTeX) | ⬜ |
| Anonymous **reviewer private link** (`/private/<token>`) | ⬜ |
| `Sign` / `Signed` banner (e-signature) — pairs with existing GMP approval | ⬜ |
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
| **`protocolify`** — create a protocol from an uploaded file/text | ⬜ |
| Paste-to-steps: `Each number is a step` / `Each line is a step` / `Markdown text` | ⬜ |
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

---

## Build order

1. **Run mode** (§2) — the defining capability. 🚧
2. **Sections + sub-steps + full component set** (§1) — depth of the editor.
3. **AI import / protocolify + paste-to-steps** (§5) — we already have the LLM pipeline.
4. **Versioning + fork + publish wizard + export** (§3, §7) — reuse the DOCX engine.
5. **Comments + AI summary** (§4).
6. **File manager / folders / collections** (§6).
