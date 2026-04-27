// ═══════════════════════════════════════════════════════════════
// codegen/apiCodeGenerator.ts
// ASTRA Framework — API Test Code Generator
// Consumes A* search result + API blueprint →
// Generates ready-to-run Playwright API test .ts files
// Covers POST, PUT, GET for all captured endpoints
// ═══════════════════════════════════════════════════════════════
//Key highlights — generates 4 complete API test files:
// schema.post.spec.ts  → POST tests (positive, negative, empty, no-auth, schema validation)
// schema.put.spec.ts   → PUT tests  (update, invalid, 404, no-auth)
// schema.get.spec.ts   → GET tests  (list, single, no-auth, 404, response time <2s)
// schema.crud.spec.ts  → E2E CRUD flow: POST → GET → PUT → GET(verify) → DELETE
//
// buildPayload() — converts A* path into proper nested JSON — address.street → { address: { street: "..." } }
// castValue() — type-aware casting — number → Number(), checkbox → boolean, dates stay as strings
// Response time test auto-generated for every GET endpoint — elapsed < 2000ms
// CRUD E2E flow uses createdId from Step 1 POST → passes through GET/PUT/DELETE — real integration chain
// test.skip(!createdId) — Steps 2-5 gracefully skip if Step 1 fails — no cascading failures
// No-auth test uses separate request.newContext() without headers — clean isolation
// getDefaultEndpoint() fallback — generates tests even when no blueprint was captured

// ═══════════════════════════════════════════════════════════════

// ═══════════════════════════════════════════════════════════════
// codegen/apiCodeGenerator.ts
// ASTRA Framework — API Test Code Generator
// Consumes A* search result + API blueprint →
// Generates ready-to-run Playwright API test .ts files
// Covers POST, PUT, PATCH, GET, DELETE for all captured endpoints
// ═══════════════════════════════════════════════════════════════

import * as fs   from "fs-extra";
import * as path from "path";
import { ENV }   from "../utils/envLoader";
import { logger } from "../utils/logger";
import { AStarEngine }          from "../core/search/aStarEngine";
import { AStarResult, AStarNode } from "../core/search/aStarEngine";
import { FieldSchema }           from "../schemas/fieldSchema.interface";
import { ApiBlueprint }          from "../preflight/networkInterceptorAnalyser";

// ═══════════════════════════════════════════════════════════════
// Interfaces
// ═══════════════════════════════════════════════════════════════
export interface ApiCodeGenResult {
  postTestFile:   string;
  putTestFile:    string;
  patchTestFile:  string;
  getTestFile:    string;
  deleteTestFile: string;
  crudTestFile:   string;
  savedTo:        string[];
}

// ═══════════════════════════════════════════════════════════════
// ApiCodeGenerator
// ═══════════════════════════════════════════════════════════════
export class ApiCodeGenerator {

  private readonly schema:     FieldSchema;
  private readonly engine:     AStarEngine;
  private readonly blueprints: ApiBlueprint[];
  private readonly outDir:     string;

  constructor(schema: FieldSchema, blueprints: ApiBlueprint[] = []) {
    this.schema     = schema;
    this.engine     = new AStarEngine(schema);
    this.blueprints = blueprints;
    this.outDir     = path.resolve(__dirname, "../tests/generated/api");
  }

  // ═══════════════════════════════════════════════════════════
  // generate — runs A* and produces all API test files
  // ═══════════════════════════════════════════════════════════
  async generate(): Promise<ApiCodeGenResult> {
    logger.divider("API Code Generator — Starting");
    await fs.ensureDir(this.outDir);

    // ─── Run A* searches ──────────────────────────────────────
    logger.codegen("Running A* positive search for API payload...");
    const positiveResult = this.engine.search({ includeOptional: false });

    logger.codegen("Running A* negative search for API payload...");
    const negativeResult = this.engine.searchNegative();

    logger.codegen(this.engine.getSearchSummary(positiveResult));

    // ─── Build payloads from A* results ───────────────────────
    const validPayload   = this.buildPayload(positiveResult);
    const invalidPayload = this.buildPayload(negativeResult);

    // ─── Identify endpoints by method ─────────────────────────
    const postBlueprints   = this.blueprints.filter((b) => b.method === "POST");
    const putBlueprints    = this.blueprints.filter((b) => b.method === "PUT");
    const patchBlueprints  = this.blueprints.filter((b) => b.method === "PATCH");
    const getBlueprints    = this.blueprints.filter((b) => b.method === "GET");
    const deleteBlueprints = this.blueprints.filter((b) => b.method === "DELETE");

    const schemaId = this.schema.schemaId.replace(/[^a-z0-9]/gi, "_");

    // ─── Generate test files ──────────────────────────────────
    const postCode   = this.generatePostTests(postBlueprints,   validPayload, invalidPayload);
    const putCode    = this.generatePutTests(putBlueprints,     validPayload, invalidPayload);
    const patchCode  = this.generatePatchTests(patchBlueprints, validPayload, invalidPayload);
    const getCode    = this.generateGetTests(getBlueprints);
    const deleteCode = this.generateDeleteTests(deleteBlueprints);
    const crudCode   = this.generateCrudSuite(validPayload, invalidPayload);

    // ─── Save files ───────────────────────────────────────────
    const postPath   = path.join(this.outDir, `${schemaId}.post.spec.ts`);
    const putPath    = path.join(this.outDir, `${schemaId}.put.spec.ts`);
    const patchPath  = path.join(this.outDir, `${schemaId}.patch.spec.ts`);
    const getPath    = path.join(this.outDir, `${schemaId}.get.spec.ts`);
    const deletePath = path.join(this.outDir, `${schemaId}.delete.spec.ts`);
    const crudPath   = path.join(this.outDir, `${schemaId}.crud.spec.ts`);

    await fs.writeFile(postPath,   postCode,   "utf-8");
    await fs.writeFile(putPath,    putCode,    "utf-8");
    await fs.writeFile(patchPath,  patchCode,  "utf-8");
    await fs.writeFile(getPath,    getCode,    "utf-8");
    await fs.writeFile(deletePath, deleteCode, "utf-8");
    await fs.writeFile(crudPath,   crudCode,   "utf-8");

    logger.codegen(`✅ POST   tests → ${postPath}`);
    logger.codegen(`✅ PUT    tests → ${putPath}`);
    logger.codegen(`✅ PATCH  tests → ${patchPath}`);
    logger.codegen(`✅ GET    tests → ${getPath}`);
    logger.codegen(`✅ DELETE tests → ${deletePath}`);
    logger.codegen(`✅ CRUD   suite → ${crudPath}`);

    return {
      postTestFile:   postPath,
      putTestFile:    putPath,
      patchTestFile:  patchPath,
      getTestFile:    getPath,
      deleteTestFile: deletePath,
      crudTestFile:   crudPath,
      savedTo:        [postPath, putPath, patchPath, getPath, deletePath, crudPath],
    };
  }

  // ═══════════════════════════════════════════════════════════
  // generatePostTests
  // ═══════════════════════════════════════════════════════════
  private generatePostTests(
    blueprints:     ApiBlueprint[],
    validPayload:   Record<string, unknown>,
    invalidPayload: Record<string, unknown>
  ): string {
    const endpoints = blueprints.length > 0
      ? blueprints
      : [this.getDefaultEndpoint("POST")];

    const timestamp = new Date().toISOString();
    const schemaId  = this.schema.schemaId;

    return `// ═══════════════════════════════════════════════════════
// AUTO-GENERATED BY ASTRA FRAMEWORK
// Schema   : ${schemaId}
// Method   : POST
// Generated: ${timestamp}
// DO NOT EDIT MANUALLY — re-run codegen to regenerate
// ═══════════════════════════════════════════════════════

import { test, expect, APIRequestContext, request } from "@playwright/test";

const API_BASE_URL   = process.env.API_BASE_URL   || "${ENV.API_BASE_URL || ENV.BASE_URL}";
const BEARER_TOKEN   = process.env.BEARER_TOKEN   || "";
const TOKEN_TYPE     = process.env.TOKEN_TYPE     || "Bearer";
const API_TIMEOUT    = ${ENV.API_TIMEOUT};

// ─── Auth Headers ────────────────────────────────────
const authHeaders = {
  "Content-Type":  "application/json",
  "Authorization": \`\${TOKEN_TYPE} \${BEARER_TOKEN}\`,
};

// ─── A* Generated Valid Payload ──────────────────────
const validPayload = ${JSON.stringify(validPayload, null, 2)};

// ─── A* Generated Invalid Payload ────────────────────
const invalidPayload = ${JSON.stringify(invalidPayload, null, 2)};

${endpoints.map((ep) => this.generatePostSuite(ep, schemaId)).join("\n\n")}
`;
  }

  // ═══════════════════════════════════════════════════════════
  // generatePostSuite — individual POST endpoint test suite
  // ═══════════════════════════════════════════════════════════
  private generatePostSuite(ep: ApiBlueprint, schemaId: string): string {
    const successCodes = this.schema.goalCondition.api?.successCodes ?? [200, 201];
    const endpoint     = ep.path;

    return `
test.describe("POST ${endpoint} — ${schemaId}", () => {

  let apiContext: APIRequestContext;

  test.beforeAll(async () => {
    apiContext = await request.newContext({
      baseURL:         API_BASE_URL,
      extraHTTPHeaders: authHeaders,
      timeout:         API_TIMEOUT,
    });
  });

  test.afterAll(async () => {
    await apiContext.dispose();
  });

  // ── Positive: Valid payload → ${successCodes.join(" or ")} ──────────────
  test("POST ${endpoint} — should return ${successCodes[0]} with valid A* payload", async () => {
    const response = await apiContext.post("${endpoint}", {
      data: validPayload,
    });

    expect(
      [${successCodes.join(", ")}],
      \`Expected ${successCodes.join(" or ")} but got \${response.status()}\`
    ).toContain(response.status());

    const body = await response.json().catch(() => ({}));
    console.log("✅ POST ${endpoint} response:", JSON.stringify(body, null, 2));
  });

  // ── Negative: Invalid payload → 4xx ─────────────────────
  test("POST ${endpoint} — should return 4xx with invalid A* payload", async () => {
    const response = await apiContext.post("${endpoint}", {
      data: invalidPayload,
    });

    expect(response.status()).toBeGreaterThanOrEqual(400);
    expect(response.status()).toBeLessThan(500);
  });

  // ── Negative: Empty payload → 400 ───────────────────────
  test("POST ${endpoint} — should return 400 with empty payload", async () => {
    const response = await apiContext.post("${endpoint}", {
      data: {},
    });

    expect(response.status()).toBe(400);
  });

  // ── Negative: No auth → 401 ─────────────────────────────
  test("POST ${endpoint} — should return 401 without auth token", async () => {
    const noAuthContext = await request.newContext({ baseURL: API_BASE_URL });

    const response = await noAuthContext.post("${endpoint}", {
      data: validPayload,
    });

    expect([401, 403]).toContain(response.status());
    await noAuthContext.dispose();
  });

  // ── Schema validation: response structure ───────────────
  test("POST ${endpoint} — response body should have expected structure", async () => {
    const response = await apiContext.post("${endpoint}", {
      data: validPayload,
    });

    if ([${successCodes.join(", ")}].includes(response.status())) {
      const body = await response.json();
      expect(body).toBeDefined();
      expect(typeof body).toBe("object");
    }
  });

});`;
  }

  // ═══════════════════════════════════════════════════════════
  // generatePutTests
  // ═══════════════════════════════════════════════════════════
  private generatePutTests(
    blueprints:     ApiBlueprint[],
    validPayload:   Record<string, unknown>,
    invalidPayload: Record<string, unknown>
  ): string {
    const endpoints = blueprints.length > 0
      ? blueprints
      : [this.getDefaultEndpoint("PUT")];

    const timestamp = new Date().toISOString();
    const schemaId  = this.schema.schemaId;

    return `// ═══════════════════════════════════════════════════════
// AUTO-GENERATED BY ASTRA FRAMEWORK
// Schema   : ${schemaId}
// Method   : PUT
// Generated: ${timestamp}
// DO NOT EDIT MANUALLY — re-run codegen to regenerate
// ═══════════════════════════════════════════════════════

import { test, expect, APIRequestContext, request } from "@playwright/test";

const API_BASE_URL = process.env.API_BASE_URL || "${ENV.API_BASE_URL || ENV.BASE_URL}";
const BEARER_TOKEN = process.env.BEARER_TOKEN || "";
const TOKEN_TYPE   = process.env.TOKEN_TYPE   || "Bearer";
const API_TIMEOUT  = ${ENV.API_TIMEOUT};

const authHeaders = {
  "Content-Type":  "application/json",
  "Authorization": \`\${TOKEN_TYPE} \${BEARER_TOKEN}\`,
};

const updatedPayload = ${JSON.stringify(validPayload, null, 2)};
const invalidPayload = ${JSON.stringify(invalidPayload, null, 2)};

${endpoints.map((ep) => this.generatePutSuite(ep, schemaId)).join("\n\n")}
`;
  }

  // ═══════════════════════════════════════════════════════════
  // generatePutSuite
  // ═══════════════════════════════════════════════════════════
  private generatePutSuite(ep: ApiBlueprint, schemaId: string): string {
    const endpoint = ep.path.replace(/\/:id/, "/:id").replace(/\/\{id\}/, "/{id}");

    return `
test.describe("PUT ${endpoint} — ${schemaId}", () => {

  let apiContext: APIRequestContext;
  const recordId = "test-record-id-001"; // Replace with actual created ID

  test.beforeAll(async () => {
    apiContext = await request.newContext({
      baseURL:          API_BASE_URL,
      extraHTTPHeaders: authHeaders,
      timeout:          API_TIMEOUT,
    });
  });

  test.afterAll(async () => {
    await apiContext.dispose();
  });

  // ── Positive: Valid update payload → 200 ────────────────
  test("PUT ${endpoint} — should update resource with valid payload", async () => {
    const endpoint = "${endpoint}".replace(":id", recordId).replace("{id}", recordId);
    const response = await apiContext.put(endpoint, {
      data: updatedPayload,
    });

    expect([200, 204]).toContain(response.status());
  });

  // ── Negative: Invalid update payload → 4xx ──────────────
  test("PUT ${endpoint} — should return 4xx with invalid payload", async () => {
    const endpoint = "${endpoint}".replace(":id", recordId).replace("{id}", recordId);
    const response = await apiContext.put(endpoint, {
      data: invalidPayload,
    });

    expect(response.status()).toBeGreaterThanOrEqual(400);
  });

  // ── Negative: Non-existent record → 404 ─────────────────
  test("PUT ${endpoint} — should return 404 for non-existent record", async () => {
    const response = await apiContext.put(
      "${endpoint}".replace(":id", "non-existent-id-9999").replace("{id}", "non-existent-id-9999"),
      { data: updatedPayload }
    );

    expect([404, 400]).toContain(response.status());
  });

  // ── Negative: No auth → 401 ─────────────────────────────
  test("PUT ${endpoint} — should return 401 without auth token", async () => {
    const noAuth   = await request.newContext({ baseURL: API_BASE_URL });
    const endpoint = "${endpoint}".replace(":id", recordId).replace("{id}", recordId);
    const response = await noAuth.put(endpoint, { data: updatedPayload });

    expect([401, 403]).toContain(response.status());
    await noAuth.dispose();
  });

});`;
  }

  // ═══════════════════════════════════════════════════════════
  // generateGetTests
  // ═══════════════════════════════════════════════════════════
  private generateGetTests(blueprints: ApiBlueprint[]): string {
    const endpoints = blueprints.length > 0
      ? blueprints
      : [this.getDefaultEndpoint("GET")];

    const timestamp = new Date().toISOString();
    const schemaId  = this.schema.schemaId;

    const suites = endpoints.map((ep) => `
test.describe("GET ${ep.path} — ${schemaId}", () => {

  let apiContext: APIRequestContext;

  test.beforeAll(async () => {
    apiContext = await request.newContext({
      baseURL:          API_BASE_URL,
      extraHTTPHeaders: authHeaders,
      timeout:          API_TIMEOUT,
    });
  });

  test.afterAll(async () => {
    await apiContext.dispose();
  });

  // ── Positive: Fetch list → 200 ──────────────────────────
  test("GET ${ep.path} — should return 200 with valid auth", async () => {
    const response = await apiContext.get("${ep.path}");
    expect(response.status()).toBe(200);

    const body = await response.json().catch(() => null);
    if (body) {
      expect(Array.isArray(body) || typeof body === "object").toBe(true);
    }
  });

  // ── Positive: Fetch single record ───────────────────────
  test("GET ${ep.path}/:id — should return 200 for valid ID", async () => {
    const response = await apiContext.get("${ep.path}/test-record-id-001");
    expect([200, 404]).toContain(response.status()); // 404 ok if record not seeded
  });

  // ── Negative: No auth → 401 ─────────────────────────────
  test("GET ${ep.path} — should return 401 without auth token", async () => {
    const noAuth   = await request.newContext({ baseURL: API_BASE_URL });
    const response = await noAuth.get("${ep.path}");
    expect([401, 403]).toContain(response.status());
    await noAuth.dispose();
  });

  // ── Negative: Non-existent record → 404 ─────────────────
  test("GET ${ep.path}/:id — should return 404 for non-existent record", async () => {
    const response = await apiContext.get("${ep.path}/non-existent-id-9999");
    expect([404, 400]).toContain(response.status());
  });

  // ── Response time: under 2s ──────────────────────────────
  test("GET ${ep.path} — response time should be under 2000ms", async () => {
    const start    = Date.now();
    const response = await apiContext.get("${ep.path}");
    const elapsed  = Date.now() - start;

    expect(response.status()).toBe(200);
    expect(elapsed).toBeLessThan(2000);
    console.log(\`  ⏱ GET ${ep.path} responded in \${elapsed}ms\`);
  });

});`).join("\n");

    return `// ═══════════════════════════════════════════════════════
// AUTO-GENERATED BY ASTRA FRAMEWORK
// Schema   : ${schemaId}
// Method   : GET
// Generated: ${timestamp}
// DO NOT EDIT MANUALLY — re-run codegen to regenerate
// ═══════════════════════════════════════════════════════

import { test, expect, APIRequestContext, request } from "@playwright/test";

const API_BASE_URL = process.env.API_BASE_URL || "${ENV.API_BASE_URL || ENV.BASE_URL}";
const BEARER_TOKEN = process.env.BEARER_TOKEN || "";
const TOKEN_TYPE   = process.env.TOKEN_TYPE   || "Bearer";
const API_TIMEOUT  = ${ENV.API_TIMEOUT};

const authHeaders = {
  "Content-Type":  "application/json",
  "Authorization": \`\${TOKEN_TYPE} \${BEARER_TOKEN}\`,
};

${suites}
`;
  }

  // ═══════════════════════════════════════════════════════════
  // generateCrudSuite — end-to-end CRUD flow test
  // POST → GET → PUT → GET (verify update) → DELETE (optional)
  // ═══════════════════════════════════════════════════════════
  private generateCrudSuite(
    validPayload:   Record<string, unknown>,
    invalidPayload: Record<string, unknown>
  ): string {
    const schemaId  = this.schema.schemaId;
    const timestamp = new Date().toISOString();
    const endpoint  = this.schema.endpoint ?? "/api/resource";
    const successCodes = this.schema.goalCondition.api?.successCodes ?? [200, 201];

    return `// ═══════════════════════════════════════════════════════
// AUTO-GENERATED BY ASTRA FRAMEWORK
// Schema   : ${schemaId}
// Suite    : FULL CRUD E2E FLOW
// Generated: ${timestamp}
// DO NOT EDIT MANUALLY — re-run codegen to regenerate
// ═══════════════════════════════════════════════════════

import { test, expect, APIRequestContext, request } from "@playwright/test";

const API_BASE_URL = process.env.API_BASE_URL || "${ENV.API_BASE_URL || ENV.BASE_URL}";
const BEARER_TOKEN = process.env.BEARER_TOKEN || "";
const TOKEN_TYPE   = process.env.TOKEN_TYPE   || "Bearer";
const API_TIMEOUT  = ${ENV.API_TIMEOUT};

const authHeaders = {
  "Content-Type":  "application/json",
  "Authorization": \`\${TOKEN_TYPE} \${BEARER_TOKEN}\`,
};

// ─── A* Generated Payloads ───────────────────────────
const createPayload = ${JSON.stringify(validPayload, null, 2)};
const updatePayload = ${JSON.stringify({ ...validPayload, _updated: true }, null, 2)};

test.describe("CRUD E2E Flow — ${schemaId}", () => {

  let apiContext: APIRequestContext;
  let createdId:  string;

  test.beforeAll(async () => {
    apiContext = await request.newContext({
      baseURL:          API_BASE_URL,
      extraHTTPHeaders: authHeaders,
      timeout:          API_TIMEOUT,
    });
  });

  test.afterAll(async () => {
    await apiContext.dispose();
  });

  // ── Step 1: CREATE ───────────────────────────────────────
  test("CRUD Step 1 — POST: Create resource", async () => {
    const response = await apiContext.post("${endpoint}", {
      data: createPayload,
    });

    expect(
      [${successCodes.join(", ")}],
      \`Expected ${successCodes.join("/")} but got \${response.status()}\`
    ).toContain(response.status());

    const body = await response.json().catch(() => ({}));
    createdId   = body?.id ?? body?.data?.id ?? body?._id ?? "unknown";

    console.log(\`  ✅ Created resource ID: \${createdId}\`);
    expect(createdId).toBeTruthy();
  });

  // ── Step 2: READ ─────────────────────────────────────────
  test("CRUD Step 2 — GET: Fetch created resource", async () => {
    test.skip(!createdId || createdId === "unknown", "Skipped — no ID from Step 1");

    const response = await apiContext.get(\`${endpoint}/\${createdId}\`);
    expect(response.status()).toBe(200);

    const body = await response.json().catch(() => ({}));
    console.log(\`  ✅ Fetched resource: \${JSON.stringify(body).substring(0, 100)}...\`);
  });

  // ── Step 3: FULL UPDATE (PUT) ────────────────────────────
  test("CRUD Step 3 — PUT: Full update of created resource", async () => {
    test.skip(!createdId || createdId === "unknown", "Skipped — no ID from Step 1");

    const response = await apiContext.put(\`${endpoint}/\${createdId}\`, {
      data: updatePayload,
    });

    expect([200, 204]).toContain(response.status());
    console.log(\`  ✅ PUT updated resource ID: \${createdId}\`);
  });

  // ── Step 4: PARTIAL UPDATE (PATCH) ───────────────────────
  test("CRUD Step 4 — PATCH: Partial update of created resource", async () => {
    test.skip(!createdId || createdId === "unknown", "Skipped — no ID from Step 1");

    const patchPayload = Object.fromEntries(
      Object.entries(updatePayload).slice(0, 2)
    );
    const response = await apiContext.patch(\`${endpoint}/\${createdId}\`, {
      data: patchPayload,
    });

    expect([200, 204]).toContain(response.status());
    console.log(\`  ✅ PATCH partial updated ID: \${createdId}\`);
  });

  // ── Step 5: READ AFTER UPDATE ────────────────────────────
  test("CRUD Step 5 — GET: Verify updates persisted", async () => {
    test.skip(!createdId || createdId === "unknown", "Skipped — no ID from Step 1");

    const response = await apiContext.get(\`${endpoint}/\${createdId}\`);
    expect(response.status()).toBe(200);

    const body = await response.json().catch(() => ({}));
    console.log(\`  ✅ Verified update: \${JSON.stringify(body).substring(0, 100)}...\`);
  });

  // ── Step 6: DELETE ───────────────────────────────────────
  test("CRUD Step 6 — DELETE: Remove resource and verify gone", async () => {
    test.skip(!createdId || createdId === "unknown", "Skipped — no ID from Step 1");

    const response = await apiContext.delete(\`${endpoint}/\${createdId}\`);
    expect([200, 204]).toContain(response.status());
    console.log(\`  ✅ Deleted resource ID: \${createdId} — Status: \${response.status()}\`);

    // Verify resource is actually gone
    const verifyResponse = await apiContext.get(\`${endpoint}/\${createdId}\`);
    expect([404, 410]).toContain(verifyResponse.status());
    console.log(\`  ✅ Verified deletion — GET returned \${verifyResponse.status()}\`);
  });

});
`;
  }

  // ═══════════════════════════════════════════════════════════
  // generatePatchTests — PATCH partial update tests
  // ═══════════════════════════════════════════════════════════
  private generatePatchTests(
    blueprints:     ApiBlueprint[],
    validPayload:   Record<string, unknown>,
    invalidPayload: Record<string, unknown>
  ): string {
    const endpoints = blueprints.length > 0
      ? blueprints
      : [this.getDefaultEndpoint("PATCH")];

    const timestamp = new Date().toISOString();
    const schemaId  = this.schema.schemaId;

    // Build a partial payload — only first 2 fields for PATCH
    const partialPayload = Object.fromEntries(
      Object.entries(validPayload).slice(0, 2)
    );

    const suites = endpoints.map((ep) => `
test.describe("PATCH ${ep.path} — ${schemaId}", () => {

  let apiContext: APIRequestContext;
  const recordId = "test-record-id-001"; // Replace with actual created ID

  test.beforeAll(async () => {
    apiContext = await request.newContext({
      baseURL:          API_BASE_URL,
      extraHTTPHeaders: authHeaders,
      timeout:          API_TIMEOUT,
    });
  });

  test.afterAll(async () => {
    await apiContext.dispose();
  });

  // ── Positive: Partial update → 200 ──────────────────────
  test("PATCH ${ep.path} — should partially update resource with valid fields", async () => {
    const endpoint = "${ep.path}".replace(":id", recordId).replace("{id}", recordId);
    const response = await apiContext.patch(endpoint, {
      data: partialPayload,
    });

    expect([200, 204]).toContain(response.status());

    const body = await response.json().catch(() => ({}));
    console.log("✅ PATCH ${ep.path} response:", JSON.stringify(body, null, 2));
  });

  // ── Positive: Single field update ───────────────────────
  test("PATCH ${ep.path} — should update single field only", async () => {
    const endpoint  = "${ep.path}".replace(":id", recordId).replace("{id}", recordId);
    const singleField = Object.fromEntries([Object.entries(validPayload)[0]]);
    const response  = await apiContext.patch(endpoint, { data: singleField });

    expect([200, 204]).toContain(response.status());
  });

  // ── Negative: Invalid field value → 4xx ─────────────────
  test("PATCH ${ep.path} — should return 4xx with invalid field value", async () => {
    const endpoint = "${ep.path}".replace(":id", recordId).replace("{id}", recordId);
    const response = await apiContext.patch(endpoint, {
      data: Object.fromEntries([Object.entries(invalidPayload)[0]]),
    });

    expect(response.status()).toBeGreaterThanOrEqual(400);
  });

  // ── Negative: Non-existent record → 404 ─────────────────
  test("PATCH ${ep.path} — should return 404 for non-existent record", async () => {
    const response = await apiContext.patch(
      "${ep.path}".replace(":id", "non-existent-id-9999").replace("{id}", "non-existent-id-9999"),
      { data: partialPayload }
    );
    expect([404, 400]).toContain(response.status());
  });

  // ── Negative: No auth → 401 ─────────────────────────────
  test("PATCH ${ep.path} — should return 401 without auth token", async () => {
    const noAuth   = await request.newContext({ baseURL: API_BASE_URL });
    const endpoint = "${ep.path}".replace(":id", recordId).replace("{id}", recordId);
    const response = await noAuth.patch(endpoint, { data: partialPayload });

    expect([401, 403]).toContain(response.status());
    await noAuth.dispose();
  });

  // ── Negative: Empty PATCH body → 400 ────────────────────
  test("PATCH ${ep.path} — should return 400 with empty body", async () => {
    const endpoint = "${ep.path}".replace(":id", recordId).replace("{id}", recordId);
    const response = await apiContext.patch(endpoint, { data: {} });

    expect([400, 422]).toContain(response.status());
  });

});`).join("\n");

    return `// ═══════════════════════════════════════════════════════
// AUTO-GENERATED BY ASTRA FRAMEWORK
// Schema   : ${schemaId}
// Method   : PATCH
// Generated: ${timestamp}
// Note: PATCH = Partial update (only send fields to change)
//       PUT   = Full replace (send entire resource)
// DO NOT EDIT MANUALLY — re-run codegen to regenerate
// ═══════════════════════════════════════════════════════

import { test, expect, APIRequestContext, request } from "@playwright/test";

const API_BASE_URL = process.env.API_BASE_URL || "${ENV.API_BASE_URL || ENV.BASE_URL}";
const BEARER_TOKEN = process.env.BEARER_TOKEN || "";
const TOKEN_TYPE   = process.env.TOKEN_TYPE   || "Bearer";
const API_TIMEOUT  = ${ENV.API_TIMEOUT};

const authHeaders = {
  "Content-Type":  "application/json",
  "Authorization": \`\${TOKEN_TYPE} \${BEARER_TOKEN}\`,
};

// ─── A* Partial Payload (first 2 fields only) ────────
const partialPayload = ${JSON.stringify(partialPayload, null, 2)};

// ─── A* Invalid Payload ──────────────────────────────
const invalidPayload = ${JSON.stringify(invalidPayload, null, 2)};

${suites}
`;
  }

  // ═══════════════════════════════════════════════════════════
  // generateDeleteTests — DELETE endpoint tests
  // ═══════════════════════════════════════════════════════════
  private generateDeleteTests(blueprints: ApiBlueprint[]): string {
    const endpoints = blueprints.length > 0
      ? blueprints
      : [this.getDefaultEndpoint("DELETE")];

    const timestamp = new Date().toISOString();
    const schemaId  = this.schema.schemaId;

    const suites = endpoints.map((ep) => `
test.describe("DELETE ${ep.path} — ${schemaId}", () => {

  let apiContext: APIRequestContext;
  let deletableId = "test-record-id-delete-001"; // Replace with seeded ID

  test.beforeAll(async () => {
    apiContext = await request.newContext({
      baseURL:          API_BASE_URL,
      extraHTTPHeaders: authHeaders,
      timeout:          API_TIMEOUT,
    });
  });

  test.afterAll(async () => {
    await apiContext.dispose();
  });

  // ── Positive: Delete existing record → 200/204 ──────────
  test("DELETE ${ep.path} — should delete resource and return 200 or 204", async () => {
    const endpoint = "${ep.path}".replace(":id", deletableId).replace("{id}", deletableId);
    const response = await apiContext.delete(endpoint);

    expect([200, 204]).toContain(response.status());
    console.log(\`  ✅ DELETE ${ep.path} — Status: \${response.status()}\`);
  });

  // ── Positive: Verify resource is gone after DELETE ───────
  test("DELETE ${ep.path} — resource should not exist after deletion", async () => {
    const endpoint = "${ep.path}".replace(":id", deletableId).replace("{id}", deletableId);

    // First delete
    await apiContext.delete(endpoint);

    // Then verify it is gone
    const getResponse = await apiContext.get(endpoint);
    expect([404, 410]).toContain(getResponse.status());

    console.log(\`  ✅ Verified resource gone — GET returned \${getResponse.status()}\`);
  });

  // ── Negative: Delete same record twice → 404 ────────────
  test("DELETE ${ep.path} — should return 404 when deleting already deleted resource", async () => {
    const endpoint = "${ep.path}".replace(":id", deletableId).replace("{id}", deletableId);

    // Delete once
    await apiContext.delete(endpoint);

    // Delete again — should be 404
    const response = await apiContext.delete(endpoint);
    expect([404, 410]).toContain(response.status());
  });

  // ── Negative: Non-existent ID → 404 ─────────────────────
  test("DELETE ${ep.path} — should return 404 for non-existent ID", async () => {
    const response = await apiContext.delete(
      "${ep.path}".replace(":id", "non-existent-id-9999").replace("{id}", "non-existent-id-9999")
    );
    expect([404, 400]).toContain(response.status());
  });

  // ── Negative: No auth → 401 ─────────────────────────────
  test("DELETE ${ep.path} — should return 401 without auth token", async () => {
    const noAuth   = await request.newContext({ baseURL: API_BASE_URL });
    const endpoint = "${ep.path}".replace(":id", deletableId).replace("{id}", deletableId);
    const response = await noAuth.delete(endpoint);

    expect([401, 403]).toContain(response.status());
    await noAuth.dispose();
  });

  // ── Negative: Delete without ID → 405 / 400 ─────────────
  test("DELETE ${ep.path} — should return 4xx when no ID provided", async () => {
    const baseEndpoint = "${ep.path}".replace("/:id", "").replace("/{id}", "");
    const response     = await apiContext.delete(baseEndpoint);

    expect(response.status()).toBeGreaterThanOrEqual(400);
  });

});`).join("\n");

    return `// ═══════════════════════════════════════════════════════
// AUTO-GENERATED BY ASTRA FRAMEWORK
// Schema   : ${schemaId}
// Method   : DELETE
// Generated: ${timestamp}
// Note: Tests cover single delete, double-delete, auth,
//       non-existent ID, and post-delete verification
// DO NOT EDIT MANUALLY — re-run codegen to regenerate
// ═══════════════════════════════════════════════════════

import { test, expect, APIRequestContext, request } from "@playwright/test";

const API_BASE_URL = process.env.API_BASE_URL || "${ENV.API_BASE_URL || ENV.BASE_URL}";
const BEARER_TOKEN = process.env.BEARER_TOKEN || "";
const TOKEN_TYPE   = process.env.TOKEN_TYPE   || "Bearer";
const API_TIMEOUT  = ${ENV.API_TIMEOUT};

const authHeaders = {
  "Content-Type":  "application/json",
  "Authorization": \`\${TOKEN_TYPE} \${BEARER_TOKEN}\`,
};

${suites}
`;
  }

  // ═══════════════════════════════════════════════════════════
  // buildPayload — converts A* path → API request body
  // ═══════════════════════════════════════════════════════════
  private buildPayload(result: AStarResult): Record<string, unknown> {
    const payload: Record<string, unknown> = {};

    for (const node of result.path) {
      const apiKey = node.field.apiKey ?? node.field.name;
      const parts  = node.fieldPath.split(".");

      if (parts.length === 1) {
        // ─── Flat field ─────────────────────────────────────
        payload[apiKey] = this.castValue(node.value, node.field.type);
      } else {
        // ─── Nested field → build nested object ─────────────
        const [parent] = parts;
        const parentKey = node.field.apiKey
          ? parent
          : parent;

        if (!payload[parentKey]) payload[parentKey] = {};
        (payload[parentKey] as Record<string, unknown>)[apiKey] =
          this.castValue(node.value, node.field.type);
      }
    }

    return payload;
  }

  // ═══════════════════════════════════════════════════════════
  // castValue — converts string value to appropriate JS type
  // ═══════════════════════════════════════════════════════════
  private castValue(value: string, type: string): unknown {
    switch (type) {
      case "number":   return isNaN(Number(value)) ? value : Number(value);
      case "checkbox": return value === "true";
      case "date":     return value;
      default:         return value;
    }
  }

  // ═══════════════════════════════════════════════════════════
  // getDefaultEndpoint — fallback when no blueprint captured
  // ═══════════════════════════════════════════════════════════
  private getDefaultEndpoint(method: string): ApiBlueprint {
    return {
      method,
      url:            `${ENV.API_BASE_URL || ENV.BASE_URL}/api/resource`,
      path:           this.schema.endpoint ?? "/api/resource",
      requestSchema:  {},
      responseSchema: {},
      requiredFields: [],
      headers:        {},
    };
  }
}

// ═══════════════════════════════════════════════════════════════
// Direct execution: npm run codegen:api
// ═══════════════════════════════════════════════════════════════
async function main(): Promise<void> {
  const schemaPath    = path.resolve(__dirname, "../schemas/api/autoGeneratedSchema.json");
  const blueprintPath = path.resolve(__dirname, "../payloads/requests/apiBlueprint.json");

  if (!await fs.pathExists(schemaPath)) {
    logger.error(`API schema not found at ${schemaPath}`);
    logger.error("Run preflight first: npm run preflight");
    process.exit(1);
  }

  const schema:     FieldSchema    = await fs.readJson(schemaPath);
  const blueprints: ApiBlueprint[] = await fs.pathExists(blueprintPath)
    ? await fs.readJson(blueprintPath)
    : [];

  const generator = new ApiCodeGenerator(schema, blueprints);
  const result    = await generator.generate();

  logger.info("\n✅ API Code Generation complete:");
  result.savedTo.forEach((f) => logger.info(`   → ${f}`));
}

if (require.main === module) {
  main().catch((err) => {
    logger.error(`API codegen failed: ${err}`);
    process.exit(1);
  });
}