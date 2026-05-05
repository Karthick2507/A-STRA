# PRISM — Automated Testing Framework

**P**laywright-powered **R**ecord, **I**ntelligent **S**elf-healing & **M**ulti-language & **ML**-based automation framework.

PRISM does three big things for your team:

1. **Records your clicks in a browser** and turns them into clean, reusable test code automatically *(Shadow Coding)*
2. **Fixes broken selectors by itself** when the app UI changes — no manual test maintenance *(Self-Healing)*
3. **Learns your company's coding style** and generates files that look like your team wrote them *(Corporate Slate)*

> Think of it like a smart assistant that watches you use a website, writes the test code for you in your team's style, and then keeps fixing the code whenever the website changes.

---

## Table of Contents

1. [How Everything Fits Together](#1-how-everything-fits-together)
2. [Folder Structure](#2-folder-structure)
3. [Install in 5 Minutes](#3-install-in-5-minutes)
4. [Configuration](#4-configuration)
5. [Shadow Coding — Record to Code](#5-shadow-coding--record-to-code)
6. [Corporate Style (Slate System)](#6-corporate-style-slate-system)
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
 python main.py learn          ← reads your corporate slate files
     │                            writes  style_profile.json
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
│       ├── slate_learner.py       ← reads slate files, writes style_profile.json
│       ├── style_profile.json     ← learned corporate style (auto-updated)
│       ├── corporate_slate.py     ← legacy single-file slate (still supported)
│       │
│       ├── slate_parser/          ← reads Python / TypeScript / Java slate files
│       │   ├── base_parser.py
│       │   ├── python_parser.py
│       │   ├── typescript_parser.py
│       │   └── java_parser.py
│       │
│       └── slates/                ← YOUR corporate code templates go here
│           ├── ui_action.py       ← template for page action methods
│           ├── ui_locator.py      ← template for locator definitions
│           ├── ui_page.py         ← template for base page class
│           ├── api_test.py        ← template for API tests
│           ├── data_verify.py     ← template for data verification helpers
│           └── controller.py      ← template for test controllers
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

### config.json — non-secret settings

This file is committed to the repo. It controls browser settings, timeouts,
healing thresholds, and the list of your corporate slate files.

```json
{
  "default_env": "stg",
  "environments": {
    "stg":  { "base_url": "https://yourapp.stg.com", "api_url": "https://yourapp.stg.com/api" },
    "prod": { "base_url": "https://yourapp.com",     "api_url": "https://yourapp.com/api" }
  },
  "browser": { "default": "chromium", "headless": false },
  "shadow_coding": {
    "slates": {
      "ui_action":  { "file": "Prism_view/shadow_coding/slates/ui_action.py",  "language": "python" },
      "ui_locator": { "file": "Prism_view/shadow_coding/slates/ui_locator.py", "language": "python" },
      "ui_page":    { "file": "Prism_view/shadow_coding/slates/ui_page.py",    "language": "python" }
    }
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
Generated locators       : sessions/20240504-143210/videos_Locators.py    ← if ui_locator slate exists
Generated controller     : sessions/20240504-143210/videos_Controller.py  ← if controller slate exists
Generated api_test       : sessions/20240504-143210/videos_test.py        ← if api_test slate exists
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

## 6. Corporate Style (Slate System)

### The problem

Out of the box, PRISM generates code that looks like PRISM's default style.
But your company probably has its own coding conventions — a specific base class,
logging pattern, import order, maybe TypeScript instead of Python.

### The solution — Slate files

A **slate** is simply a real file from your corporate codebase that PRISM reads,
learns from, and uses as the pattern for future generated files.

There is one slate per **role** (type of file). Six roles are supported:

| Role key | Slate file | Drives generation of |
|----------|-----------|----------------------|
| `ui_action` | `slates/ui_action.py` | `{entity}_UI.py` — page actions |
| `ui_locator` | `slates/ui_locator.py` | `{entity}_Locators.py` — element selectors |
| `ui_page` | `slates/ui_page.py` | `Base_page.py` — base page class |
| `api_test` | `slates/api_test.py` | `{entity}_test.py` — API tests |
| `data_verify` | `slates/data_verify.py` | `{entity}_Data.json` helpers |
| `controller` | `slates/controller.py` | `{entity}_Controller.py` — orchestrator |

### Supported languages per role

Each role's slate (and therefore its output file) can be in a different language:

| Language | Slate extension | Output extension |
|----------|----------------|------------------|
| Python | `.py` | `.py` |
| TypeScript | `.ts` | `.ts` |
| JavaScript | `.js` | `.js` |
| Java | `.java` | `.java` |

Roles are **independent** — `ui_locator` can be TypeScript while `api_test` is Java
and `ui_action` is Python. PRISM handles each role separately.

### How to teach PRISM your corporate style

#### 1. Drop your real corporate files into the slates folder

```
Prism_view/shadow_coding/slates/
├── ui_action.py     ← copy a real page object from your codebase
├── ui_locator.py    ← copy a real locator file
├── ui_page.py       ← copy your BasePage class
└── controller.py    ← copy a real controller/fixture file
```

The placeholder files already in those paths are just examples — replace them
with your real code. PRISM only reads the **style** (imports, class names, logging
calls, type hints) — it does not copy the actual test logic.

#### 2. If your team uses TypeScript, update config.json

```json
"slates": {
  "ui_action":  { "file": "Prism_view/shadow_coding/slates/ui_action.ts",  "language": "typescript" },
  "ui_locator": { "file": "Prism_view/shadow_coding/slates/ui_locator.ts", "language": "typescript" }
}
```

#### 3. Run the learn command

```bash
python main.py learn
```

PRISM will:
- Parse each slate file that exists
- Extract the style (imports, base class, logging, type hints, naming, Playwright API)
- Save everything to `style_profile.json`
- Train the block classifier (ML model that recognises login / form-fill / navigation blocks)

Sample output:

```
Style learned from 4 role(s):
  [ui_action]  python     | base=BasePage | method=snake_case
  [ui_locator] typescript | base=—        | method=camelCase
  [ui_page]    python     | base=—        | method=snake_case
  [controller] python     | base=—        | method=snake_case
  profile saved → Prism_view/shadow_coding/style_profile.json
```

#### 4. Learn a single slate manually (optional)

```bash
python main.py learn --slate path/to/my_page.py
```

### What PRISM learns from a slate

| What it reads | Example (Python) | Example (TypeScript) |
|---------------|-----------------|----------------------|
| Base class | `class MyPage(BasePage)` | `class MyPage extends BasePage` |
| Import order | `from __future__ import annotations` first | `import { Page } from "@playwright/test"` |
| Logging pattern | `logger.info(f"...")` | `console.log(...)` |
| Type hints | `def fill(self, val: str) -> None` | `async fill(val: string): Promise<void>` |
| Playwright API | `get_by_role` vs `locator` | `getByRole` vs `locator` |
| Docstring style | Google / NumPy / plain | JSDoc |

### What happens when a role's slate does NOT exist

If a slate file is missing for a role, that role is simply skipped.

- `ui_action` slate missing → `{entity}_UI.py` is generated using PRISM defaults
- `ui_locator` slate missing → `{entity}_Locators.py` is **not generated at all**
- `controller` slate missing → `{entity}_Controller.py` is **not generated at all**

This means you can start with zero slates and add them one by one as your team
decides on conventions.

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

### UI tests

```bash
python main.py ui                              # all UI tests, default env + browser
python main.py ui --env=stg --browser=firefox  # specific env and browser
python main.py ui -m smoke                     # only tests marked @pytest.mark.smoke
python main.py ui -n 4                         # 4 parallel workers
```

Or directly with pytest (same thing):

```bash
pytest UI/tests -m smoke --browser=chromium -n auto
```

### API tests

```bash
python main.py api
python main.py api -m regression -n 4
```

### UI + API together (end-to-end)

```bash
python main.py e2e --browser=chromium
```

### Writing a test with a generated page object

After running `python main.py shadow`, copy the generated files into your test
structure and write a test like this:

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

```bash
# Check your install
python main.py preflight

# Learn corporate style from all slate files
python main.py learn

# Learn from a single file
python main.py learn --slate path/to/my_page.py

# Record a session and generate files
python main.py shadow --url https://yourapp.stg.com

# Run tests
python main.py ui                              # all UI tests
python main.py ui --env=prod --browser=firefox # choose env + browser
python main.py ui -m smoke                     # filter by marker
python main.py ui -n auto                      # parallel (auto workers)
python main.py api                             # all API tests
python main.py api -m regression -n 4          # API, filtered, parallel
python main.py e2e --browser=chromium          # UI + API together

# Train self-healing ML model
python main.py train
python main.py train --min-samples 50          # require more data before training

# Inspect locator registry
python main.py registry
python main.py registry --export Data/locators/dump.json
```

---

## 10. Tech Stack

| What it does | Library |
|---|---|
| Browser automation | `playwright` + `pytest-playwright` |
| Test runner | `pytest`, `pytest-xdist` (parallel), `pytest-rerunfailures` |
| HTTP / API testing | `httpx` |
| WebSocket testing | `websockets` |
| ML (self-healing) | `scikit-learn`, `skl2onnx`, `onnxruntime`, `numpy`, `joblib` |
| Config / secrets | `python-dotenv` + `json` |
| Logging | `colorlog` (custom levels: HEAL, SHADOW, API) |
| Reporting | `allure-pytest` |
| Notifications | `httpx` (Slack / Teams) + `smtplib` (Email) |
| OpenAPI contracts | `pyyaml` |

---

## Common Questions

**Q: Do I need to set up slates before I can use Shadow Coding?**
No. PRISM works with zero slates — it uses built-in defaults. Slates only add the
ability to match your team's specific coding conventions.

**Q: Can I mix languages? Python UI + Java API tests?**
Yes. Each slate role is independent. Point `ui_action` at a `.py` file and
`api_test` at a `.java` file in `config.json`. PRISM generates each output file
in the language of its slate.

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
