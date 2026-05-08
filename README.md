# PRISM — Automated Testing Framework

**P**laywright-powered **R**ecord, **I**ntelligent **S**elf-healing & **M**ulti-language & **ML**-based automation framework.

PRISM does three big things for your team:

1. **Records your clicks in a browser** and turns them into clean, reusable test code automatically *(Shadow Coding)*
2. **Fixes broken selectors by itself** when the app UI changes — no manual test maintenance *(Self-Healing)*
3. **Learns your company's coding style** by scanning your existing framework folder and generates files that look like your team wrote them *(Folder Scan)*

> Think of it like a smart assistant that watches you use a website, writes the test code for you in your team's style, and then keeps fixing the code whenever the website changes.

---

## Table of Contents

1. [How Everything Fits Together](#1-how-everything-fits-together)
2. [Folder Structure](#2-folder-structure)
3. [Install in 5 Minutes](#3-install-in-5-minutes)
4. [Configuration](#4-configuration)
5. [Shadow Coding — Record to Code](#5-shadow-coding--record-to-code)
6. [Corporate Style (Folder Scan)](#6-corporate-style-folder-scan)
7. [Self-Healing Locators](#7-self-healing-locators)
8. [Running Tests](#8-running-tests)
9. [CLI Cheat Sheet](#9-cli-cheat-sheet)
10. [Tech Stack](#10-tech-stack)

---

## 1. How Everything Fits Together

```
You (developer)
     │
     │  Step 1 — teach PRISM your coding style
     ▼
 python main.py learn --scan ./your_corporate_framework
     │                            scans every .py/.ts/.js/.java/data file,
     │                            classifies each into a PRISM role, and writes
     │                            style_profile.json
     │
     │  Step 2 — record a user session
     ▼
 python main.py shadow --url https://your-app.com
     │                            browser opens, you click around
     │                            browser closes
     │
     │  Step 3 — PRISM generates files in YOUR style
     ▼
 Prism_view/shadow_coding/sessions/
   ├── videos_UI.py          ← page object class (actions)
   ├── videos_Locators.py    ← all element selectors in one place
   ├── videos_Controller.py  ← wires everything together
   ├── videos_Data.json      ← test data extracted from your recording
   ├── videos_test.py        ← API test scaffold
   └── Base_page.py          ← shared helper methods (login, wait, etc.)
     │
     │  Step 4 — run the tests
     ▼
 python main.py ui --env=stg
     │
     │  App UI changed? A selector broke?
     ▼
 Self-Healing kicks in automatically
   → tries 6 strategies to find the element
   → ML model picks the best match
   → test continues, no code change needed
   → broken selector is updated in the database for next time
```

---

## 2. Folder Structure

```
PRISM/
│
├── main.py                        ← ALL commands start here
├── config.json                    ← non-secret settings (URLs, timeouts, browser)
├── .env                           ← secrets: passwords, tokens (never commit this!)
├── requirements.txt
├── conftest.py                    ← pytest fixtures shared across all tests
├── pytest.ini
│
├── core/                          ← engine room
│   ├── config/
│   │   └── config_loader.py       ← merges config.json + .env + CLI flags
│   ├── logging/
│   │   └── logger.py              ← custom log levels: HEAL, SHADOW, API
│   ├── retry/
│   │   └── retry_handler.py       ← @retry decorator (exponential backoff)
│   └── reporting/
│       ├── allure_helper.py       ← attach screenshots/traces to Allure
│       └── notifiers.py           ← Slack / Teams / Email after every run
│
├── Prism_view/
│   │
│   ├── self_healing/              ← broken selector? PRISM fixes it itself
│   │   ├── locator_registry.py    ← SQLite database of every selector + history
│   │   ├── healer.py              ← orchestrates the 6-strategy healing pipeline
│   │   ├── strategies/            ← 6 individual healing strategies
│   │   │   ├── id_strategy.py
│   │   │   ├── name_strategy.py
│   │   │   ├── aria_strategy.py
│   │   │   ├── class_strategy.py
│   │   │   ├── dom_neighbour_strategy.py
│   │   │   └── registry_strategy.py
│   │   └── ml/                    ← machine learning re-ranker (no cloud needed)
│   │       ├── feature_extractor.py
│   │       ├── predictor.py
│   │       └── trainer.py
│   │
│   └── shadow_coding/             ← the record-and-generate engine
│       ├── recorder.py            ← wraps playwright codegen
│       ├── code_enhancer.py       ← turns raw recording into corporate POM files
│       ├── roles.py               ← role registry (single source of truth)
│       ├── prism_config.json      ← plugin-mode config home
│       ├── style_profile.json     ← learned corporate style (auto-updated)
│       ├── slate_learner.py       ← persists scan results into style_profile.json
│       │
│       ├── scanner/               ← Folder Scan engine (replaces slates/)
│       │   ├── folder_scanner.py  ← recursive directory walker
│       │   ├── file_classifier.py ← regex + AST per-file role classifier
│       │   ├── scan_result.py     ← ScannedFile / RoleAssignment / ScanResult
│       │   ├── scan_report.py     ← formatted summary tables
│       │   └── interactive_cli.py ← Y/N/R/S review prompts
│       │
│       └── slate_parser/          ← reads Python / TypeScript / Java source
│           ├── base_parser.py
│           ├── python_parser.py
│           ├── typescript_parser.py
│           └── java_parser.py
│
├── UI/
│   ├── pages/                     ← hand-written page objects
│   │   ├── base_page.py
│   │   ├── login_page.py
│   │   └── menu_page.py
│   ├── components/                ← reusable UI components
│   │   ├── popup.py
│   │   ├── tab_panel.py
│   │   └── tooltip.py
│   └── tests/                     ← UI test files
│       └── test_login.py
│
├── API/
│   ├── client/                    ← HTTP client + auth adapters
│   │   ├── base_client.py
│   │   ├── auth_adapters.py
│   │   └── websocket_client.py
│   ├── openapi/                   ← OpenAPI spec loader + contract tests
│   └── tests/                     ← API test files
│       └── test_users_api.py
│
└── Data/
    ├── UI/                        ← UI test data (JSON)
    ├── API/                       ← API payloads + OpenAPI examples
    └── locators/                  ← SQLite registry + ML training data (auto-created)
```

---

## 3. Install in 5 Minutes

**Requirements:** Python 3.11+, pip

```bash
# 1. Clone the repo and go into it
cd PRISM

# 2. Create a virtual environment (keeps your system clean)
python3.11 -m venv .venv

# 3. Activate it
source .venv/bin/activate          # Mac / Linux
.venv\Scripts\activate             # Windows

# 4. Install all dependencies
pip install -r requirements.txt

# 5. Install the browser (only needed once)
playwright install chromium

# 6. Check everything is working
python main.py preflight
```

If preflight prints `Preflight OK.` you are good to go.

---

## 4. Configuration

### prism_config.json — non-secret settings

PRISM looks for its config in this order:

1. `$PRISM_CONFIG` environment variable (explicit path) — highest priority
2. `Prism_view/shadow_coding/prism_config.json` — plugin-mode default
3. `config.json` at project root — legacy fallback

The config file controls browser settings, timeouts, healing thresholds, and
session output paths. **Corporate style is no longer configured here** — it
is learned automatically by `prism learn --scan` (see [Section 6](#6-corporate-style-folder-scan)).

```json
{
  "default_env": "stg",
  "environments": {
    "stg":  { "base_url": "https://yourapp.stg.com" },
    "prod": { "base_url": "https://yourapp.com" }
  },
  "browser": { "default": "chromium", "headless": false },
  "self_healing": {
    "enabled": true,
    "min_confidence": 0.75
  },
  "shadow_coding": {
    "session_dir": "Prism_view/shadow_coding/sessions",
    "auto_assertions": true
  }
}
```

### .env — secrets (never commit this file!)

Create a `.env` file in the project root (copy from `.env.example` if provided):

```ini
APP_USERNAME=your-username
APP_PASSWORD=your-password
BEARER_TOKEN=your-api-token
SLACK_WEBHOOK_URL=https://hooks.slack.com/...
```

### Choosing an environment

Three ways, in order of priority:

```bash
python main.py ui --env=prod          # 1. CLI flag (highest priority)
ASTRA_ENV=prod pytest                 # 2. Environment variable
# or just leave it — uses default_env from config.json
```

---

## 5. Shadow Coding — Record to Code

Shadow Coding is the headline feature. In one command it:
- Opens a real browser
- Records every click and keystroke you make
- Closes the browser when you are done
- Transforms the raw recording into clean, corporate-style test files

### Step-by-step

```bash
python main.py shadow --url https://yourapp.stg.com
```

1. A browser window opens at your URL
2. **Do the thing you want to test** — log in, navigate, fill a form, click Create, etc.
3. Close the browser window when you are done
4. PRISM prints the generated files:

```
Shadow recording started: 20240504-143210
Interact with the browser. Close it when finished.
Raw codegen output: Prism_view/shadow_coding/sessions/20240504-143210/raw.py

Generated UI page object : sessions/20240504-143210/videos_UI.py
Generated test data      : sessions/20240504-143210/videos_Data.json
Generated base page      : sessions/20240504-143210/Base_page.py
Generated locators       : sessions/20240504-143210/videos_Locators.py    ← if ui_locator role detected
Generated controller     : sessions/20240504-143210/videos_Controller.py  ← if controller role detected
Generated api_test       : sessions/20240504-143210/videos_test.py        ← if api_test role detected
```

### What does each generated file do?

| File | What it is | Re-recorded? |
|------|------------|-------------|
| `{entity}_UI.py` | Page object class with `create_*()` method, data-driven loop, logging | Yes — safe to re-record |
| `{entity}_Data.json` | All the values you typed, stored as structured JSON | Yes — safe to re-record |
| `Base_page.py` | Shared helpers: `mrm_login`, `wait_until_page_loaded`, `create_btn_click` | **No** — preserved so your customisations are safe |
| `{entity}_Locators.py` | Every element selector in one place (emitted only if `ui_locator` slate exists) | Yes |
| `{entity}_Controller.py` | Wires UI + Locators together + a pytest fixture (emitted if `controller` slate exists) | Yes |
| `{entity}_test.py` | API test scaffold with create + get stubs (emitted if `api_test` slate exists) | Yes |

### How the raw recording is transformed

```
Your browser actions
        │
        ▼
playwright codegen (raw Python)
        │
        ▼
 _parse_raw()    ← reads every line, identifies role/locator/fill/click
        │
        ▼
 _classify()     ← groups lines into phases:
                    login block → extracts username / password
                    navigation  → detects entity name (e.g. "Videos")
                    create form → collects each field + value
                    submit      → marks end of form
        │
        ▼
 code generators ← one per output file, uses style_profile.json
        │
        ▼
 6 output files written to sessions/TIMESTAMP/
```

---

## 6. Corporate Style (Folder Scan)

### The problem

Out of the box, PRISM generates code in PRISM's default style. But your team
already has conventions — a specific base class, logging pattern, naming
scheme, maybe TypeScript or Java instead of Python.

### The solution — point PRISM at your existing framework

Instead of asking you to hand-craft "slate" files, PRISM **scans your real
test framework folder**, classifies each file into one of six roles, and
learns the style automatically.

```bash
prism learn --scan /path/to/your_corporate_framework
```

### The six roles PRISM looks for

| Role key | What PRISM looks for | Drives generation of |
|----------|----------------------|----------------------|
| `ui_page` | Base classes, shared helpers (`extends`, no `@Test`/`def test_`) | `Base_page.{py,ts,java}` |
| `ui_action` | Files calling `.click()`, `.fill()`, `page.goto(...)` | `{entity}_UI.{py,ts,java}` |
| `ui_locator` | Static selector constants (`By.`, `data-testid`, `getByRole`) | `{entity}_Locators.{py,ts,java}` |
| `api_test` | `@pytest.mark`, `@Test`, `def test_…`, REST clients | `{entity}_test.{py,ts,java}` |
| `data_verify` | Data builders, parametrize fixtures, `.xlsx`/`.json`/`.yaml`/`.docx`/`.pptx` | `{entity}_Data.json` |
| `controller` | Files importing multiple page objects, fixtures, `@BeforeClass` | `{entity}_Controller.{py,ts,java}` |

### Supported languages

PRISM handles **mixed-language** projects. Each role is detected independently —
your `ui_page` can be Java while `ui_action` is TypeScript and `api_test` is
Python. The generated file picks up the same language as the role's source.

| Language | Source extensions read | Output extension |
|----------|------------------------|------------------|
| Python | `.py` | `.py` |
| TypeScript | `.ts` | `.ts` |
| JavaScript | `.js` | `.js` |
| Java | `.java` | `.java` |
| Data | `.xlsx` `.pptx` `.docx` `.yaml` `.json` | classified as `data_verify` |

### How the scan works

1. **Walk** the folder you point at — skips `.git`, `node_modules`,
   `__pycache__`, `vendor`, `target`, `build`, `.venv` automatically.
2. **Classify** every supported file into one of the six roles using
   regex signals + Python AST inspection. Each assignment gets a confidence:
   - **HIGH**  ≥ 0.85 → auto-accepted
   - **MEDIUM** 0.70–0.84 → auto-accepted, you can drop in review
   - **LOW**   < 0.70 → PRISM **asks you** per file
3. **Review** — PRISM shows a summary table and prompts:
   - `[Y]` accept   `[N]` drop   `[R]` reassign to another role   `[S]` skip
4. **Learn** — PRISM picks the highest-confidence file per role as the
   representative slate, parses it, and writes role-keyed style data into
   `Prism_view/shadow_coding/style_profile.json`.

### Walkthrough

```bash
prism learn --scan ./acme_test_framework
```

```
──────────────────────────────────────────────────────────────────────────────
PRISM folder scan — /home/me/acme_test_framework
──────────────────────────────────────────────────────────────────────────────
  Files scanned    : 87
  Languages found  : python, typescript
  Roles assigned   : 6
  Unclassified     : 0

  Role           Conf     Files   Examples
  -------------- -------- ------  ----------------------------------------
  ui_page        HIGH     2       BasePage.py, base_page.ts
  ui_action      HIGH     14      login_page.py, dashboard.ts, … (+12)
  ui_locator     MEDIUM   8       login_locators.py, dashboard.locators.ts
  controller     HIGH     3       login_controller.py, … (+1)
  api_test       HIGH     12      test_auth.py, test_users.ts, … (+10)
  data_verify    HIGH     5       users.json, fixtures.yaml, … (+2)
──────────────────────────────────────────────────────────────────────────────

Action for 'ui_page'? [Y/n/r/s]: y
Action for 'ui_action'? [Y/n/r/s]: y
...
✓ style_profile.json updated — roles: ['api_test', 'controller', 'data_verify',
                                       'ui_action', 'ui_locator', 'ui_page']
```

### Single-file mode

If you only want to point PRISM at one specific file (instead of a whole
folder), use `--slate`:

```bash
prism learn --slate path/to/my_login_page.ts
```

This runs the same classifier engine on that one file.

### Skip the prompts (CI mode)

```bash
prism learn --scan ./acme_test_framework --yes
```

`--yes` / `-y` auto-accepts every assignment. Useful in CI pipelines where
no human is at the keyboard.

### What PRISM learns

For each accepted role, PRISM extracts and stores:

| What it reads | Example (Python) | Example (TypeScript) |
|---------------|-----------------|----------------------|
| Base class | `class MyPage(BasePage)` | `class MyPage extends BasePage` |
| Import style | `from __future__ import annotations` first | `import { Page } from "@playwright/test"` |
| Logging | `logger.info(f"...")` | `console.log(...)` |
| Type hints | `def fill(self, val: str) -> None` | `async fill(val: string): Promise<void>` |
| Locator API | `get_by_role` vs `locator` | `getByRole` vs `locator` |

### What if a role isn't detected?

If your framework doesn't contain (say) a `controller` file, PRISM simply
won't generate `{entity}_Controller.*` during `prism shadow`. Roles you
don't have are silently skipped — there's no failure.

### What gets written

Every successful scan updates `Prism_view/shadow_coding/style_profile.json`
with two new top-level sections:

```json
{
  "by_role": {
    "ui_page":   { "source": { "language": "python", "path": "..." }, "patterns": {...} },
    "ui_action": { "source": { "language": "typescript", "path": "..." }, "patterns": {...} }
  },
  "scanned_from": {
    "root": "/home/me/acme_test_framework",
    "files": [
      { "role": "ui_page", "path": "...", "confidence": 0.92, "language": "python", "all_files": [...] }
    ]
  }
}
```

---

## 7. Self-Healing Locators

### The problem

Web apps change. A button's `id` gets renamed, a CSS class gets refactored.
Your tests break, even though the button is still there.

### How PRISM heals a broken locator

When a locator fails during a test, PRISM does not give up. It runs a
**6-strategy healing pipeline** to find the element by other means:

```
Locator fails
      │
      ▼
Strategy 1: try exact id match           → confidence 0.99
Strategy 2: try exact name match         → confidence 0.95
Strategy 3: aria-label text similarity   → confidence up to 0.95
Strategy 4: CSS class overlap (Jaccard)  → confidence up to 0.85
Strategy 5: DOM position / nth-of-type   → confidence 0.65–0.70
Strategy 6: historical variants (SQLite) → confidence 0.55–0.75
      │
      ▼
ML re-ranker (16-dim features, ONNX)
  → blends heuristic confidence with ML score
  → picks the best candidate
      │
      ▼
Best candidate above threshold (default 0.75)?
  YES → verify it is visible on the page right now
         → update the SQLite registry with the new selector
         → test continues — no code changes needed
  NO  → test fails with a clear error (not a silent wrong click)
```

### Training the ML model

The more tests run, the better the ML model gets. Training happens automatically:

```bash
python main.py train
```

This reads `Data/locators/training_data.jsonl` (appended automatically on every
heal) and saves a new model to:
- `Prism_view/self_healing/ml/models/healer_model.pkl` (sklearn)
- `Prism_view/self_healing/ml/models/healer_model.onnx` (CPU-only, no cloud)

### Inspecting the locator registry

```bash
python main.py registry
python main.py registry --export Data/locators/dump.json
```

---

## 8. Running Tests

PRISM does **not** ship its own test runner — it generates clean POM files
that plug into your existing framework (pytest, Playwright Test, JUnit, …).

### Run with your existing framework

```bash
# Python / pytest
pytest tests/ -n auto

# TypeScript / Playwright Test
npx playwright test

# Java / JUnit
mvn test
```

### Writing a test with a generated page object

After running `prism shadow --url ...`, copy the generated files into your
test structure and write a test like this:

```python
# UI/tests/test_videos.py
import json
from pathlib import Path
from Videos_UI import Videos

def test_create_video(page):
    data = json.loads(Path("videos_Data.json").read_text())
    vids = Videos(page)
    vids.mrm_login(network="MyNetwork", username="user", password="pass")
    vids.create_videos(
        od_name="MyNetwork",
        headers={},
        videos_list=data["MRM"][0]["Videos"],
    )
```

---

## 9. CLI Cheat Sheet

After `pip install prism-fw`, the `prism` command is on your PATH. From a
checked-out repo, replace `prism` with `python main.py`.

```bash
# Check your install
prism preflight

# Learn corporate style by scanning a folder (interactive)
prism learn --scan ./your_corporate_framework

# Learn from a single file (same engine, one-file scan)
prism learn --slate path/to/my_page.py

# Skip prompts (CI mode)
prism learn --scan ./your_corporate_framework --yes

# Record a session and generate POM files in your style
prism shadow --url https://yourapp.stg.com

# Train the self-healing ML model
prism train
prism train --min-samples 50

# Inspect the locator registry
prism registry
prism registry --export Data/locators/dump.json
```

---

## 10. Tech Stack

| What it does | Library |
|---|---|
| Browser automation | `playwright` + `pytest-playwright` |
| Test runner (host framework) | `pytest`, Playwright Test, JUnit, … (your choice) |
| ML (self-healing) | `scikit-learn`, `skl2onnx`, `onnxruntime`, `numpy`, `joblib` |
| Data file readers (Folder Scan) | `pyyaml`, `openpyxl`, `python-docx`, `python-pptx` |
| Config / secrets | `python-dotenv` + `json` |
| Logging | `colorlog` |

---

## Common Questions

**Q: Do I need to scan a folder before I can use Shadow Coding?**
No. PRISM works without any scan — it falls back to built-in defaults.
Scanning your framework only adds the ability to match your team's specific
coding conventions.

**Q: Can I mix languages? Python UI + Java API tests?**
Yes. Each role is detected independently during the folder scan. If your
`ui_action` files are Python and your `api_test` files are Java, PRISM emits
the corresponding generated files in those languages.

**Q: What if I re-record the same entity?**
`{entity}_UI.py` and `{entity}_Data.json` are overwritten (so your latest
recording wins). `Base_page.py` is **never** overwritten — your customisations
are always safe.

**Q: Does the ML model need a GPU or internet access?**
No. The model is a scikit-learn Gradient Boosting classifier exported to ONNX,
running locally on CPU only. No cloud, no GPU, no API calls.

**Q: Where are secrets stored?**
In a `.env` file in the project root. This file must **never** be committed to
version control. It is already in `.gitignore`.

---

*Internal use — not yet published.*
