# PRISM Plugin Guide

PRISM ships in three modes. Pick the one that fits your team.

| Mode | Best for | How |
|------|---------|-----|
| **Python import** | Existing Python automation frameworks | `pip install prism-fw` → `from prism import ShadowCoder, SelfHealer` |
| **CLI subprocess** | Java / TypeScript / JavaScript / any-language frameworks | `pip install prism-fw` → call `prism ...` from your test runner |
| **Standalone** | Solo development or starting from scratch | clone the repo → `python main.py ...` |

All three modes use the same engine, the same config file, and produce the same outputs.

---

## 1. Python Import Mode

### Install
```bash
pip install prism-fw
playwright install chromium
```

### Record a session and generate corporate POM files
```python
from prism import ShadowCoder

coder = ShadowCoder(
    session_dir="./test_sessions",
    network_name="MyNetwork",
)
files = coder.record_and_generate("https://yourapp.stg.com")

# files is a dict of generated paths
print(files["ui"])         # → ./test_sessions/.../videos_UI.py
print(files["data"])       # → ./test_sessions/.../videos_Data.json
print(files["base_page"])  # → ./test_sessions/.../Base_page.py
```

### Heal a broken locator
```python
from prism import SelfHealer
from playwright.sync_api import sync_playwright

healer = SelfHealer()  # uses prism_config.json defaults

with sync_playwright() as pw:
    browser = pw.chromium.launch()
    page = browser.new_page()
    page.goto("https://yourapp.com")

    result = healer.heal(
        broken_locator='button[data-testid="submit-old"]',
        page=page,
    )
    if result.success:
        page.locator(result.healed_locator).click()
```

### Inspect the locator registry
```python
from prism import LocatorRegistry

reg = LocatorRegistry("Data/locators/locator_registry.db")
stats = reg.stats()  # → {"total": 142, "active": 138, "healed_in_last_7d": 4, ...}
```

### Learn corporate style by scanning your framework
```python
from prism import FolderScanner
from Prism_view.shadow_coding.slate_learner import SlateLearner

scanner = FolderScanner("./your_corporate_framework")
result  = scanner.scan()

print(f"Found {result.total_files_scanned} files in {result.languages_found}")
for role, assignment in result.assignments.items():
    print(f"  {role:15s} [{assignment.confidence_level}]  "
          f"{len(assignment.files)} file(s)")

# Persist to style_profile.json (used by ShadowCoder during generation)
SlateLearner().learn_from_scan(result)
```

---

## 2. CLI / Subprocess Mode (any language)

After `pip install prism-fw`, the `prism` command is on your PATH. Any test
framework (Java JUnit, TypeScript Playwright, Robot, etc.) can shell out to
it and read the JSON / file outputs.

### From Java
```java
public class PrismIntegration {
    public static void recordSession(String url) throws IOException, InterruptedException {
        ProcessBuilder pb = new ProcessBuilder("prism", "shadow", "--url", url);
        pb.inheritIO();
        Process p = pb.start();
        if (p.waitFor() != 0) {
            throw new RuntimeException("PRISM shadow recording failed");
        }
        // Generated files are now in Prism_view/shadow_coding/sessions/<timestamp>/
    }
}
```

### From TypeScript / Node
```typescript
import { spawnSync } from "child_process";

function recordSession(url: string): void {
  const result = spawnSync("prism", ["shadow", "--url", url], {
    stdio: "inherit",
  });
  if (result.status !== 0) {
    throw new Error("PRISM shadow recording failed");
  }
}
```

### From a shell script / Bash
```bash
prism preflight
prism learn --scan ./my_corporate_framework      # interactive review
prism learn --scan ./my_corporate_framework -y   # CI / non-interactive
prism shadow --url https://yourapp.stg.com
prism train
prism registry --export ./locator_dump.json
```

---

## 3. Standalone Mode

Clone the repo and run from source — no install needed.

```bash
git clone <repo>
cd PRISM
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

python main.py preflight
python main.py shadow --url https://yourapp.stg.com
```

This is the same as CLI mode, just from a checked-out repo.

---

## Configuration

PRISM reads its config from one of these locations, in priority order:

1. `$PRISM_CONFIG` env var (explicit path)
2. `Prism_view/shadow_coding/prism_config.json` *(installed location — default)*
3. `config.json` at project root *(legacy fallback)*

### Override programmatically
Pass values directly when constructing the API objects:

```python
coder = ShadowCoder(session_dir="/tmp/sessions", network_name="Acme")
healer = SelfHealer(registry_path="/var/data/locators.db", min_confidence=0.85)
```

### Override per-environment
Set `PRISM_CONFIG=/path/to/staging.json` in your CI to point at a different
config without changing the installed file.

---

## Multi-language Output

PRISM does **not** force you to use Python. Each role's slate language drives
the language of its generated file.

| Slate language | Output extension |
|----------------|-----------------|
| Python (`.py`) | `.py` |
| TypeScript (`.ts`) | `.ts` |
| JavaScript (`.js`) | `.js` |
| Java (`.java`) | `.java` |

Roles are independent. Your `ui_action` slate can be Java while `api_test` is
TypeScript and `controller` is Python — PRISM emits each output file in its
slate's language.

---

## What Each Generated File Is For

| File | When emitted | Role |
|------|------------|------|
| `{entity}_UI.py/ts/java` | Always | `ui_action` |
| `{entity}_Data.json` | Always | `data_verify` |
| `Base_page.py/ts/java` | Always (not overwritten) | `ui_page` |
| `{entity}_Locators.py/ts/java` | If `ui_locator` slate exists | `ui_locator` |
| `{entity}_Controller.py/ts/java` | If `controller` slate exists | `controller` |
| `{entity}_test.py/ts/java` | If `api_test` slate exists | `api_test` |

---

## Self-Healing in Plugin Mode

Two integration patterns:

### A. Manual integration (you control where healing fires)
```python
from prism import SelfHealer
healer = SelfHealer()

def safe_click(page, locator):
    try:
        page.locator(locator).click(timeout=2000)
    except Exception:
        result = healer.heal(locator, page)
        if result.success:
            page.locator(result.healed_locator).click()
        else:
            raise
```

### B. pytest plugin (automatic)
A `pytest-prism` entry point that fires healing on every locator failure is
on the roadmap — for now use the manual integration above.

---

## Common Questions

**Q: Where do generated files go?**
Default: `Prism_view/shadow_coding/sessions/<timestamp>/` (relative to CWD).
Override: `ShadowCoder(session_dir="...")` or `shadow_coding.session_dir` in `prism_config.json`.

**Q: Can I use PRISM offline?**
Yes. The ML model is local ONNX (CPU only). Playwright codegen runs locally.
Nothing calls out to the internet.

**Q: How do I update the corporate style without re-recording?**
Run `prism learn --scan /path/to/your/framework`. This refreshes
`style_profile.json`. Next time you run `prism shadow`, the new style is used.

**Q: Does PRISM modify my framework's source code?**
No. PRISM **reads** your framework files (during `learn`) and **writes** new
files into its own `sessions/` folder. Your code is never touched.
