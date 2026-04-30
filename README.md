# ASTRA-v2

**A**utonomous **S**elf-healing **T**est **R**unner & **A**utomation framework — v2.

A Python automation framework for UI + API testing with three "self-coding" modes,
in-house ML-driven self-healing locators (no LLM tokens, CPU-only ONNX), and
A\* search for autonomous form-completion.

---

## Highlights

| Capability | How |
|---|---|
| UI automation | Playwright (sync) + POM, transparent self-healing |
| API automation | `httpx` + 5 auth adapters + WebSocket + OpenAPI contract tests |
| Self-coding (Autopilot) | A\* search drives the browser, emits pytest POM file |
| Self-coding (Shadow) | Wraps `playwright codegen`, post-processes raw output to POM style |
| Self-healing locators | 6-strategy pipeline + 16-dim ML re-ranker (sklearn → ONNX) |
| Locator history | SQLite registry with success counts and historical variants |
| Reporting | Allure + screenshots + traces on failure |
| Notifications | Slack / MS Teams / Email after every run |
| CI | GitHub Actions matrix (chromium/firefox) + Jenkins pipeline |

---

## Folder Tree

```
ASTRA-v2/
├── main.py                    CLI entry point (preflight | ui | api | e2e | autopilot | shadow | train | registry)
├── config.json                Non-secret config (env URLs, timeouts, browser opts)
├── requirements.txt
├── conftest.py                Session-wide pytest fixtures (page, api_client, run-stats hooks)
├── pytest.ini
├── Jenkinsfile
├── .github/workflows/astra-v2-ci.yml
│
├── core/
│   ├── config/                Config loader (.env + config.json + --env CLI)
│   ├── logging/               Custom levels: ASTAR, HEAL, SHADOW, AUTOPILOT, API
│   ├── retry/                 @retry decorator with exponential backoff
│   └── reporting/             Allure helpers + Slack/Teams/Email notifiers
│
├── Asearch/
│   ├── self_healing/
│   │   ├── locator_registry.py    SQLite-backed history of every locator
│   │   ├── healer.py              Pipeline orchestrator + ML re-rank + auto-apply
│   │   ├── strategies/            6 strategies (id, name, aria, class, dom, registry)
│   │   └── ml/                    Feature extractor (16-dim) + GBM trainer + ONNX predictor
│   ├── astar/                     Node, GoalSpec/Heuristic, GraphBuilder, A* Engine
│   ├── autopilot/                 A* runner → ActionRecorder → CodeEmitter
│   └── shadow_coding/             playwright codegen wrapper + CodeEnhancer
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
cd ASTRA-v2
python3.11 -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -r requirements.txt
playwright install chromium       # add firefox / webkit if needed
```

---

## Configuration

Two-tier:

* `config.json` — committed defaults (URLs per env, timeouts, browser opts, healing thresholds, A\* limits).
* `.env` — secrets (tokens, passwords, webhook URLs, SMTP creds). **Never committed.**

Selecting an environment:
* CLI flag: `python main.py ui --env=stg`
* Env var: `ASTRA_ENV=staging pytest`
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
python main.py ui --env=staging --browser=chromium -m smoke
# or directly
pytest UI/tests -m smoke --browser=chromium -n auto
```

### Run API tests

```bash
python main.py api -m smoke
```

### Autopilot (A\* generates a test for you)

```bash
python main.py autopilot \
    --url       https://app.example.com/login \
    --goal-text "Welcome"
# Generated test → Asearch/autopilot/sessions/test_ap_<timestamp>.py
```

### Shadow Coding (record and enhance)

```bash
python main.py shadow --url https://app.example.com
# Browser opens — interact, then close it.
# Enhanced POM test → Asearch/shadow_coding/sessions/<id>_enhanced.py
```

### Train self-healing ML model

```bash
python main.py train
# Reads Data/locators/training_data.jsonl (collected automatically by healer)
# Writes models/healer_model.pkl + .onnx
```

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

## A\* Autopilot

Treats the application as a state graph:

* **Node** = `(page_url, tab_index, filled_fields, popup_state)` — frozen dataclass, hashable
* **Edge** = one UI action (`fill`, `click`, `select`, `navigate`, `dismiss_popup`) with cost 1.0
* **Goal** = `GoalSpec(url_patterns, text_patterns, element_selectors, required_fields)`
* **Heuristic h(n)** = `H_url + H_fields + H_popup` (admissible)

Standard A\* with `heapq` open-set + closed-set + `best_g` table. Default cap: 500 iterations.

---

## Architecture (5-Layer)

```
┌────────────────────────────────────────────────────────────────┐
│  L5  CI / Reporting     GitHub Actions, Jenkins, Allure, Slack  │
├────────────────────────────────────────────────────────────────┤
│  L4  Tests              UI/tests/, API/tests/                   │
├────────────────────────────────────────────────────────────────┤
│  L3  Self-coding        Autopilot (A*), Shadow Coding (codegen) │
├────────────────────────────────────────────────────────────────┤
│  L2  Domain             POM (UI/pages), Clients (API/client)    │
│      Self-healing       6-strategy pipeline + ML re-rank        │
├────────────────────────────────────────────────────────────────┤
│  L1  Core               Config, Logging, Retry, Registry        │
└────────────────────────────────────────────────────────────────┘
```

---

## CLI Cheat Sheet

```bash
python main.py preflight                     # validate config + imports
python main.py ui  --browser=firefox -m smoke
python main.py api -m regression -n 4
python main.py e2e --browser=chromium
python main.py autopilot --url URL --goal-text "Welcome"
python main.py shadow    --url URL
python main.py train     --min-samples 30
python main.py registry  --export Data/locators/dump.json
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

## License

Internal use — not yet published.
