# ASTRA-v2

**A**utonomous **S**elf-healing **T**est **R**unner & **A**utomation framework — v2.

A lightweight Python automation framework for UI + API testing with **Shadow Coding**
(record-and-enhance test generation in corporate POM style) and **in-house ML-driven
self-healing locators** (no LLM tokens, CPU-only ONNX).

---

## Highlights

| Capability | How |
|---|---|
| UI automation | Playwright (sync) + POM, transparent self-healing |
| API automation | `httpx` + 5 auth adapters + WebSocket + OpenAPI contract tests |
| Shadow Coding | Wraps `playwright codegen`, generates 3 corporate-style files: `{name}_UI.py`, `{name}_Data.json`, `Base_page.py` |
| Self-healing locators | 6-strategy pipeline + 16-dim ML re-ranker (sklearn → ONNX) |
| Locator history | SQLite registry with success counts and historical variants |
| Reporting | Allure + screenshots + traces on failure |
| Notifications | Slack / MS Teams / Email after every run |
| CI | GitHub Actions matrix (chromium/firefox) + Jenkins pipeline |

> **Note:** The previous `autopilot` (A\* search) module has been **removed** in this
> release. In practice, A\* search proved unreliable on real-world authenticated SPAs
> (it has no concept of login/auth context, and DOM-order locators like
> `button:nth-of-type(3)` time out almost immediately). Use **Shadow Coding** instead —
> it produces working corporate-style POM code from a real recorded user session.

---

## Folder Tree

```
A-STRA/
├── main.py                    CLI entry (preflight | ui | api | e2e | shadow | train | registry)
├── config.json                Non-secret config (env URLs, timeouts, browser opts)
├── requirements.txt
├── conftest.py                Session-wide pytest fixtures (page, api_client, run-stats hooks)
├── pytest.ini
├── Jenkinsfile
├── .github/workflows/astra-v2-ci.yml
│
├── core/
│   ├── config/                Config loader (.env + config.json + --env CLI)
│   ├── logging/               Custom levels: HEAL, SHADOW, API
│   ├── retry/                 @retry decorator with exponential backoff
│   └── reporting/             Allure helpers + Slack/Teams/Email notifiers
│
├── Prism_view/
│   ├── self_healing/
│   │   ├── locator_registry.py    SQLite-backed history of every locator
│   │   ├── healer.py              Pipeline orchestrator + ML re-rank + auto-apply
│   │   ├── strategies/            6 strategies (id, name, aria, class, dom, registry)
│   │   └── ml/                    Feature extractor (16-dim) + GBM trainer + ONNX predictor
│   └── shadow_coding/             playwright codegen wrapper + 3-file CodeEnhancer
│
├── UI/
│   ├── pages/                     BasePage + LoginPage + MenuPage examples
│   ├── components/                PopupHandler, TooltipHelper, TabPanel
│   └── tests/                     Example UI tests (login flows)
│
├── API/
│   ├── client/                    APIClient + 5 auth adapters + WebSocket client
│   ├── openapi/                   OpenAPI 3.x spec loader + stub generator
│   └── tests/                     Example API tests (users CRUD + contract)
│
└── Data/
    ├── UI/                        Test data (login_data.json, …)
    ├── API/                       Payloads + openapi_example.json
    └── locators/                  SQLite registry + ML training JSONL (auto-created)
```

---

## Install

```bash
python3.11 -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium       # add firefox / webkit if needed
```

---

## Configuration

Two-tier:

* `config.json` — committed defaults (URLs per env, timeouts, browser opts, healing thresholds).
* `.env` — secrets (tokens, passwords, webhook URLs, SMTP creds). **Never committed.**

Selecting an environment:
* CLI flag: `python main.py ui --env=stg`
* Env var: `ASTRA_ENV=stg pytest`
* Default from `config.json` → `default_env`

All fields are flat on `CONFIG`:

```python
from core.config import CONFIG
print(CONFIG.env, CONFIG.base_url, CONFIG.api_url)
print(CONFIG.healing_enabled, CONFIG.healing_min_confidence)
```

---

## Quick Start

### Run preflight

```bash
python main.py preflight
```

### Run UI tests

```bash
python main.py ui --env=stg --browser=chromium -m smoke
# or directly
pytest UI/tests -m smoke --browser=chromium -n auto
```

### Run API tests

```bash
python main.py api -m smoke
```

### Shadow Coding (record and generate corporate POM files)

```bash
python main.py shadow --url https://mrm.stg.example.com/
# Browser opens — interact with the app, then close it.
# Three files are generated in Prism_view/shadow_coding/sessions/:
#   {entity}_UI.py     — class-based POM with data-driven create_*() method
#   {entity}_Data.json — extracted test data ({"MRM": [{"NetworkName": …}]})
#   Base_page.py       — reusable methods (mrm_login, wait_until_page_loaded, …)
```

### Train self-healing ML model

```bash
python main.py train
# Reads Data/locators/training_data.jsonl (collected automatically by healer)
# Writes models/healer_model.pkl + .onnx
```

### Inspect locator registry

```bash
python main.py registry --export Data/locators/dump.json
```

---

## Shadow Coding — How it Works

The `shadow` command wraps `playwright codegen --target python-pytest`. After you
finish recording, the raw output is parsed into phases (login, navigation, create
form, submit) and emitted as three corporate-style files matching the
`pytest-sekiro` 3-layer architecture:

| File | Purpose |
|---|---|
| `{entity}_UI.py` | `class Entity(BasePage)` with a `create_*(items_list, skip_create_if_exists=False)` method. Includes `for item in list:` loop, `logger.info()` checkpoints, `if "Field" in item:` optional-field guards, and date-picker handling. |
| `{entity}_Data.json` | Hard-coded values lifted into a structured payload: `{"MRM": [{"NetworkName": "...", "Entity": [{...}]}]}` |
| `Base_page.py` | Common reusable methods: `mrm_login`, `wait_until_page_loaded`, `create_btn_click`, `direct_to_network_items`, `set_relationship`, `set_restriction`, `search_detail_ui_instead_oltp`, dropdown helpers. **Not overwritten** on subsequent recordings. |

Re-recording overwrites `{entity}_UI.py` and `{entity}_Data.json` (so you can iterate
on the recording), but never overwrites `Base_page.py` (so your customisations are
safe).

---

## How Self-Healing Works

1. Test calls `pom.click("login.submit")`.
2. `BasePage.find()` looks up the active selector in the SQLite registry.
3. If it resolves on the page → record success and return.
4. If it fails → `HealerOrchestrator.heal()` runs the **6-strategy pipeline**:

   | # | Strategy | Confidence |
   |---|---|---|
   | 1 | `id` exact match            | 0.99 |
   | 2 | `name` exact match          | 0.95 |
   | 3 | `aria-label` similarity     | ≤ 0.95 |
   | 4 | CSS class Jaccard           | ≤ 0.85 |
   | 5 | DOM neighbour / nth-of-type | 0.65 – 0.70 |
   | 6 | Registry historical variants| 0.55 – 0.75 |

5. **ML re-rank**: each candidate is scored by the 16-dim feature extractor + ONNX predictor. The ML score is blended with the heuristic confidence (default weight 0.40 once a model is trained; 0.0 on cold start).
6. Best candidate above `min_confidence` (default 0.75) is verified live, then `replace_with_healed()` updates the SQLite registry atomically.
7. Test continues with the new selector — no test code changes needed.
8. Training rows (1 positive + up to 3 hard negatives) are appended to `Data/locators/training_data.jsonl` for future model improvement.

---

## Architecture (5-Layer)

```
┌───────────────────────────────────────────────────────────────┐
│  L5  CI / Reporting     GitHub Actions, Jenkins, Allure, Slack │
├───────────────────────────────────────────────────────────────┤
│  L4  Tests              UI/tests/, API/tests/                  │
├───────────────────────────────────────────────────────────────┤
│  L3  Test Generation    Shadow Coding (codegen + 3-file POM)   │
├───────────────────────────────────────────────────────────────┤
│  L2  Domain             POM (UI/pages), Clients (API/client)   │
│      Self-healing       6-strategy pipeline + ML re-rank       │
├───────────────────────────────────────────────────────────────┤
│  L1  Core               Config, Logging, Retry, Registry       │
└───────────────────────────────────────────────────────────────┘
```

---

## CLI Cheat Sheet

```bash
python main.py preflight                     # validate config + imports
python main.py ui  --browser=firefox -m smoke
python main.py api -m regression -n 4
python main.py e2e --browser=chromium
python main.py shadow   --url URL
python main.py train    --min-samples 30
python main.py registry --export Data/locators/dump.json
```

---

## Tech Stack

| Layer | Library |
|---|---|
| Browser | playwright + pytest-playwright |
| Test runner | pytest, pytest-xdist, pytest-rerunfailures |
| HTTP | httpx |
| WebSocket | websockets |
| ML | scikit-learn (GBM), skl2onnx, onnxruntime, numpy, joblib |
| Config | python-dotenv + json |
| Logging | colorlog (custom levels) |
| Reporting | allure-pytest |
| Notifications | httpx (Slack/Teams) + smtplib (Email) |
| OpenAPI | pyyaml (optional) |

---

## What was removed in this release

The `autopilot` subcommand and the `Prism_view/astar/` + `Prism_view/autopilot/` packages
were removed. Reasons:

* **No auth context** — A\* couldn't handle login flows; on the FreeWheel MRM staging
  app it was redirected to SSO and failed every successor.
* **DOM-order locators (`button:nth-of-type(3)`)** are unstable on any real SPA —
  they timed out within seconds in production.
* **State model too coarse** — node = `(url, tab, fields, popup)` doesn't capture
  modals, loaded data, or async state in modern apps.
* **Shadow Coding solves the same problem better** — record once, generate proper
  POM code based on real user actions instead of brute-forcing the DOM.

If you previously used `python main.py autopilot ...`, switch to:

```bash
python main.py shadow --url <url>
```

---

## License

Internal use — not yet published.
