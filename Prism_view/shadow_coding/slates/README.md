# Slate Files

Each file here is a **corporate style template** for a specific code role.  
Replace the placeholder content with a real file from your corporate codebase.

| File | Role key | Drives output |
|------|----------|---------------|
| `ui_action.py` | `ui_action` | `{entity}_UI.py` |
| `ui_locator.py` | `ui_locator` | `{entity}_Locators.py` |
| `ui_page.py` | `ui_page` | `Base_page.py` |
| `api_test.py` | `api_test` | `API/{entity}_test.py` |
| `data_verify.py` | `data_verify` | `{entity}_Data.json` + assertion helpers |
| `controller.py` | `controller` | `{entity}_Controller.py` |

## Switching language

To use TypeScript, Java, or any other supported language for a role, update
`config.json` under `shadow_coding.slates`:

```json
"ui_action": { "file": "Prism_view/shadow_coding/slates/ui_action.ts", "language": "typescript" }
```

Then run:

```bash
python main.py learn
```

PRISM will parse every slate that exists, merge results into `style_profile.json`
under `by_role`, and train the block classifier.
