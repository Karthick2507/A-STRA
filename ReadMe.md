npm run preflight        # Health check + auto schema
npm run test:ui          # UI tests
npm run test:api         # API tests
npm run full:run         # Everything end to end
npx playwright test tests/generated/ui/*.spec.ts --ui 
PWDEBUG=1 npm run test:ui


Welcome to ASTRA! 🌟
Hey, welcome to the team! Don't worry — we'll go through everything step by step. By the end of this, you'll understand exactly what this project does and how it works.

**1) What is this Project About?**
The Problem We're Solving
Imagine you join a company and your job is to test a website — say, a user registration form. Normally, as a QA engineer, you would have to:

Manually look at every field on the form
Write test cases one by one
Manually type test data for each field
Run the tests and check if they pass

This takes days or weeks for a large application. And every time the app changes, you have to redo it all.

What ASTRA Does Instead
ASTRA is a framework that does all of that automatically.
You give ASTRA just two things:
1. The URL of your web app
2. A valid username and password to log in
ASTRA then does everything else on its own:
Step 1 → Visits your app and studies every field on the page
Step 2 → Captures every API call the app makes in the background
Step 3 → Uses an AI algorithm to figure out how to fill the form
Step 4 → Generates and writes the actual test code files
Step 5 → Runs those tests and gives you a report

A Simple Analogy
Think of ASTRA like a very smart new hire on your QA team:
Human QA EngineerASTRALooks at the form manuallyScans the DOM automaticallyWrites test data manuallyGenerates test data algorithmicallyWrites test scripts by handGenerates Playwright .ts filesRuns tests manuallyExecutes tests automaticallyTypes up a reportGenerates HTML + JSON reports
The key difference: ASTRA does it in minutes, not days.

What Makes ASTRA Unique — The A* Algorithm
The name ASTRA comes from the A* (pronounced "A-star") algorithm — a famous pathfinding algorithm used in GPS navigation and video games.
In GPS, A* finds the shortest route from point A to point B avoiding roads that are blocked.
In ASTRA, A* finds the optimal path through a form — which fields to fill, in what order, using what data — to reach the goal (a successful form submission).
GPS World          →    ASTRA World
────────────────────────────────────
Map                →    Web Form
Roads              →    Form Fields
Blocked Roads      →    Invalid/Missing Fields
Destination        →    Successful Submission
Shortest Route     →    Optimal Fill Sequence

What ASTRA Tests
ASTRA covers three types of testing:
1. UI Testing — filling forms in a real browser
2. API Testing — sending HTTP requests directly (GET, POST, PUT, PATCH, DELETE)
3. E2E Testing — running both UI and API together as one full flow

The Name
ASTRA =      Autonomous A* Search Based Test & Reporting Architecture
Each word matters:

Autonomous → runs itself, no manual intervention
A* Search → uses the A* algorithm to find optimal paths
Test → it's a testing framework
Reporting → generates structured reports automatically
Architecture → it's a full system, not just a script


Summary

ASTRA is an autonomous test framework. You give it a URL and credentials. It studies your app, writes tests using an AI search algorithm, runs those tests, and delivers a full report — all without you writing a single line of test code.

ASTRA's Big Picture — 5 Layers

┌─────────────────────────────────────────────────────────────┐
│                    YOU (The User)                           │
│              npm run preflight / test:ui / full:run         │
└─────────────────────────────┬───────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 1 — PREFLIGHT LAYER  (The Inspector)                 │
│  "Study the app before testing"                             │
│                                                             │
│  domAnalyser.ts          → Scans every field on the page    │
│  bearerTokenAnalyser.ts  → Finds & saves auth token         │
│  networkInterceptor.ts   → Captures all API calls           │
│  antiBotAnalyser.ts      → Detects CAPTCHA / WAF / bots     │
│  healthCheck.orchestrator.ts → Runs all 4, generates report │
└─────────────────────────────┬───────────────────────────────┘
                              │ outputs findings
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 2 — CORE LAYER  (The Brain)                          │
│  "Figure out what to test and how"                          │
│                                                             │
│  schemaBuilder.ts     → Converts findings → field schema    │
│  heuristicScorer.ts   → Calculates g(n), h(n), f(n) scores  │
│  dataGenerator.ts     → Creates valid + invalid test data   │
│  aStarEngine.ts       → Finds optimal path through fields   │
└─────────────────────────────┬───────────────────────────────┘
                              │ outputs A* path + data
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 3 — CODEGEN LAYER  (The Writer)                      │
│  "Write the actual test scripts"                            │
│                                                             │
│  uiCodeGenerator.ts  → Writes Playwright UI test files      │
│  apiCodeGenerator.ts → Writes Playwright API test files     │
└─────────────────────────────┬───────────────────────────────┘
                              │ outputs .spec.ts files
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 4 — RUNNER LAYER  (The Executor)                     │
│  "Run the generated tests"                                  │
│                                                             │
│  uiTestRunner.ts   → Runs UI tests via Playwright CLI       │
│  apiTestRunner.ts  → Runs API tests via Playwright CLI      │
│  e2eTestRunner.ts  → Orchestrates all runners together      │
└─────────────────────────────┬───────────────────────────────┘
                              │ outputs test results
                              ▼
┌─────────────────────────────────────────────────────────────┐
│  LAYER 5 — SUPPORT LAYER  (The Foundation)                  │
│  "Utilities that every layer depends on"                    │
│                                                             │
│  envLoader.ts       → Reads .env configuration              │
│  logger.ts          → Logs everything to console + file     │
│  reportGenerator.ts → Builds HTML + JSON reports            │
│  schemaResolver.ts  → Safely loads schema files             │
└─────────────────────────────────────────────────────────────┘

The Folder Structure Explained

Astra/
│
├── .env                    ← Your app's URL, credentials, settings
├── package.json            ← Project dependencies + npm scripts
├── tsconfig.json           ← TypeScript configuration
├── playwright.config.ts    ← Playwright browser settings
│
├── preflight/              ← LAYER 1: Inspector
│   ├── domAnalyser.ts
│   ├── bearerTokenAnalyser.ts
│   ├── networkInterceptorAnalyser.ts
│   ├── antiBotAnalyser.ts
│   └── healthCheck.orchestrator.ts
│
├── core/                   ← LAYER 2: Brain
│   ├── schemaBuilder.ts
│   ├── scorer/
│   │   └── heuristicScorer.ts
│   ├── generator/
│   │   └── dataGenerator.ts
│   └── search/
│       └── aStarEngine.ts
│
├── codegen/                ← LAYER 3: Writer
│   ├── uiCodeGenerator.ts
│   └── apiCodeGenerator.ts
│
├── runners/                ← LAYER 4: Executor
│   ├── ui/uiTestRunner.ts
│   ├── api/apiTestRunner.ts
│   └── e2e/e2eTestRunner.ts
│
├── utils/                  ← LAYER 5: Foundation
│   ├── envLoader.ts
│   ├── logger.ts
│   ├── reportGenerator.ts
│   └── schemaResolver.ts
│
├── schemas/                ← Schema definitions (the "map" of your form)
│   ├── fieldSchema.interface.ts
│   ├── ui/registrationSchema.ts
│   └── api/registrationSchema.ts
│
├── reports/                ← Generated reports (auto-created)
│   ├── preflight/
│   └── testResults/
│
└── tests/                  ← Generated test files (auto-created)
    └── generated/
        ├── ui/
        └── api/       


The Technology Stac
1. TypeScript

What it is: A programming language. An upgraded version of JavaScript.
Why not plain JavaScript?
JavaScript (loose):           TypeScript (strict):
────────────────────────────────────────────────────
let name = 42;               let name: string = "Karthick";
name = "hello"; // ✅ ok     name = 42; // ❌ Error caught!
// Bug found only at runtime  // Bug caught before running
TypeScript adds types — it tells the computer "this variable must always be a string" — and catches mistakes before you even run the code.

2. Playwright
What it is: A tool that controls a real web browser from code.

3. Node.js
What it is: Lets you run TypeScript/JavaScript on your computer (outside the browser).
Without Node.js, JavaScript only runs inside browsers. Node.js lets ASTRA run as a command-line tool on your terminal.

4. ts-node
What it is: Runs TypeScript files directly without compiling first.
Normally: TypeScript → compile → JavaScript → run
With ts-node: TypeScript → run directly ✅

5. fs-extra
What it is: A utility to read and write files.

// In code — reads from .env automatically
console.log(process.env.BASE_URL); // "https://myapp.com"
```

---

## The A\* Algorithm — Visual Explanation

This is the core concept. Let's visualise it:
```
FORM FIELDS (the maze):

  [firstName] ──→ [lastName] ──→ [email] ──→ [phone]
                                    │
                                    ▼
                              [street] ──→ [city] ──→ [state]
                                                         │
                                                         ▼
                                                    [username]
                                                         │
                                                         ▼
                                                    [password]
                                                         │
                                                         ▼
                                                   🎯 GOAL (Submit)

A* finds this path automatically using:
  g(n) = how many fields filled so far (cost paid)
  h(n) = how many mandatory fields still left (cost ahead)
  f(n) = g(n) + h(n)  ← always pick the lowest f next
```

---

## How Everything Connects — One Sentence Each

| File | One-Line Role |
|------|--------------|
| `.env` | Stores your app's URL and credentials |
| `envLoader.ts` | Reads `.env` and validates all settings |
| `healthCheck.orchestrator.ts` | Master controller that runs all 4 inspectors |
| `domAnalyser.ts` | Opens browser, reads every field on the form |
| `bearerTokenAnalyser.ts` | Extracts and saves the auth token |
| `networkInterceptorAnalyser.ts` | Records every API call the page makes |
| `antiBotAnalyser.ts` | Checks if the app has CAPTCHA or bot protection |
| `schemaBuilder.ts` | Converts inspector findings into a field map |
| `heuristicScorer.ts` | Calculates priority scores for each field |
| `dataGenerator.ts` | Creates test data (valid and invalid) for each field |
| `aStarEngine.ts` | Runs A\* search to find optimal fill order |
| `uiCodeGenerator.ts` | Writes Playwright UI test `.ts` files |
| `apiCodeGenerator.ts` | Writes Playwright API test `.ts` files |
| `uiTestRunner.ts` | Runs generated UI tests |
| `apiTestRunner.ts` | Runs generated API tests |
| `e2eTestRunner.ts` | Runs everything end-to-end |
| `reportGenerator.ts` | Builds HTML + JSON reports |
| `schemaResolver.ts` | Safely loads the right schema file |

---

## The Complete Flow in One Diagram
```
You type: npm run full:run
              │
              ▼
        ┌─────────────┐
        │  .env file  │ ← BASE_URL, credentials, settings
        └──────┬──────┘
               │
               ▼
    ┌──────────────────────┐
    │  Preflight (4 checks)│
    │  DOM + Token +       │
    │  Network + AntiBot   │
    └──────────┬───────────┘
               │ findings
               ▼
    ┌──────────────────────┐
    │   Schema Builder     │ ← Converts findings to field map
    └──────────┬───────────┘
               │ schema
               ▼
    ┌──────────────────────┐
    │   A* Engine          │ ← Finds optimal field fill path
    │   + DataGenerator    │ ← Generates test data
    └──────────┬───────────┘
               │ path + values
               ▼
    ┌──────────────────────┐
    │   Code Generators    │ ← Writes .spec.ts test files
    │   UI + API           │
    └──────────┬───────────┘
               │ spec files
               ▼
    ┌──────────────────────┐
    │   Runners            │ ← Executes tests via Playwright
    │   UI + API + E2E     │
    └──────────┬───────────┘
               │ results
               ▼
    ┌──────────────────────┐
    │   Reports            │ ← HTML + JSON reports saved
    └──────────────────────┘

3) Every File — Purpose, Code & Explanation

LAYER 5 FIRST — Foundation Files
(We start here because every other layer depends on these)

📄 File 1: .env
What is it?
Think of it as the settings panel of ASTRA. No code here — just key=value pairs.
Why does it exist?
Instead of hardcoding your app's URL inside the code (which is bad — you'd have to change 10 files every time URL changes), you put it in one place: .env.

📄 File 2: utils/envLoader.ts
What is it?
The gatekeeper — reads .env, validates it, and gives the rest of the code a clean typed object to use.
Why does it exist?
Without this, every file would have to call process.env.BASE_URL directly — messy, no validation, no defaults. envLoader does it once and does it right.

📄 File 3: utils/logger.ts
What is it?
The diary of ASTRA — records everything that happens, with timestamps, colours, and categories.
Why does it exist?
When something goes wrong at 3am in a CI pipeline, you need to know exactly what happened and when. The logger keeps a permanent record.

📄 File 4: utils/reportGenerator.ts
What is it?
The report card writer — takes results from all 4 preflight analysers and creates a beautiful HTML report.

📄 File 5: utils/schemaResolver.ts
What is it?
The safe schema loader — finds and loads the right schema file without crashing.
Why does it exist?
This was added to fix a real bug: when autoGeneratedSchema.json didn't exist yet, the code was accidentally trying to read a TypeScript .ts file as JSON — which crashes.


LAYER 1 — Preflight Files

📄 File 6: schemas/fieldSchema.interface.ts
What is it?
The blueprint of a blueprint — defines the exact shape that every schema must follow.
Why does it exist?
TypeScript interfaces are contracts. By defining FieldSchema, we guarantee that the UI schema, API schema, auto-generated schema, and everything in the core layer all speak the same language.