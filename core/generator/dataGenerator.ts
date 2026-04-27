// ═══════════════════════════════════════════════════════════════
// core/generator/dataGenerator.ts
// ASTRA Framework — Data Generator
// Generates valid + invalid test data combinations for each field
// Feeds A* engine with value candidates per node
// No external LLM — pure algorithmic generation
//Key highlights — the self-generating data engine:
//
// 7 generation strategies per field — validSample, invalidSample, patternGenerated, typeDefault, boundary, empty, enumValue, unique
// Smart name detection — reads field name for context: firstName → names, city → cities, pincode → Indian pincodes, street → addresses — zero config needed
// Boundary value testing built-in — minLength - 1 (invalid), minLength (valid), maxLength (valid), maxLength + 1 (invalid) — classic SDET boundary analysis
// runId — short UUID per run — ensures username fields get unique values per execution, no collision
// recommended — always the first valid value — this is what A* uses for its happy path
// generateForAllFields() — returns Map<fieldPath, FieldDataSet> — entire form covered in one call
// deduplicate() — prevents same value appearing multiple times in valid/invalid lists
// No external API, no LLM — 100% algorithmic, fully offline, instant
// ═══════════════════════════════════════════════════════════════

import { v4 as uuidv4 }  from "uuid";
import { logger }         from "../../utils/logger";
import {
  ResolvedField,
  FieldType,
  ValidationRule,
  DataHints,
}                          from "../../schemas/fieldSchema.interface";

// ═══════════════════════════════════════════════════════════════
// Interfaces
// ═══════════════════════════════════════════════════════════════
export interface GeneratedValue {
  value:    string;
  isValid:  boolean;
  strategy: GenerationStrategy;
  reason:   string;
}

export type GenerationStrategy =
  | "validSample"       // From dataHints.validSamples
  | "invalidSample"     // From dataHints.invalidSamples
  | "patternGenerated"  // Generated from regex pattern
  | "typeDefault"       // Default for field type
  | "boundary"          // Boundary value (min/max length or value)
  | "empty"             // Empty string — tests required validation
  | "enumValue"         // From validValues list
  | "unique";           // UUID-based unique value

export interface FieldDataSet {
  fieldPath:   string;
  fieldType:   FieldType;
  mandatory:   boolean;
  valid:       GeneratedValue[];
  invalid:     GeneratedValue[];
  recommended: GeneratedValue;   // Best value for A* happy path
}

// ═══════════════════════════════════════════════════════════════
// DataGenerator
// ═══════════════════════════════════════════════════════════════
export class DataGenerator {

  private readonly runId: string;

  constructor() {
    this.runId = uuidv4().substring(0, 8); // Short unique run ID
    logger.info(`DataGenerator initialized — runId: ${this.runId}`);
  }

  // ═══════════════════════════════════════════════════════════
  // generateForField
  // Produces full FieldDataSet for one ResolvedField
  // ═══════════════════════════════════════════════════════════
  generateForField(field: ResolvedField): FieldDataSet {
    const valid:   GeneratedValue[] = [];
    const invalid: GeneratedValue[] = [];

    // ─── 1. From dataHints.validSamples ───────────────────────
    if (field.dataHints?.validSamples?.length) {
      for (const sample of field.dataHints.validSamples) {
        valid.push({
          value:    sample,
          isValid:  true,
          strategy: "validSample",
          reason:   "From schema dataHints.validSamples",
        });
      }
    }

    // ─── 2. From validValues (enum/dropdown) ──────────────────
    if (field.validValues?.length) {
      for (const val of field.validValues.slice(0, 3)) {
        valid.push({
          value:    val,
          isValid:  true,
          strategy: "enumValue",
          reason:   `Enum value from validValues`,
        });
      }
    }

    // ─── 3. Type-based generation ─────────────────────────────
    const typeGenerated = this.generateByType(field);
    valid.push(...typeGenerated.valid);
    invalid.push(...typeGenerated.invalid);

    // ─── 4. From dataHints.invalidSamples ────────────────────
    if (field.dataHints?.invalidSamples?.length) {
      for (const sample of field.dataHints.invalidSamples) {
        invalid.push({
          value:    sample,
          isValid:  false,
          strategy: "invalidSample",
          reason:   "From schema dataHints.invalidSamples",
        });
      }
    }

    // ─── 5. Boundary values ───────────────────────────────────
    const boundaries = this.generateBoundaryValues(field.validationRule, field.type);
    valid.push(...boundaries.valid);
    invalid.push(...boundaries.invalid);

    // ─── 6. Empty value — always invalid for mandatory ────────
    invalid.push({
      value:    "",
      isValid:  false,
      strategy: "empty",
      reason:   "Empty value tests required field validation",
    });

    // ─── 7. Unique value if needed ────────────────────────────
    if (field.dataHints?.unique) {
      valid.push(this.generateUniqueValue(field));
    }

    // ─── Deduplicate ──────────────────────────────────────────
    const dedupedValid   = this.deduplicate(valid);
    const dedupedInvalid = this.deduplicate(invalid);

    // ─── Pick recommended (first valid, highest confidence) ───
    const recommended = dedupedValid[0] ?? {
      value:    "",
      isValid:  false,
      strategy: "empty",
      reason:   "No valid value generated",
    };

    logger.astar(
      `DataGenerator: ${field.fieldPath} → ` +
      `${dedupedValid.length} valid, ${dedupedInvalid.length} invalid`
    );

    return {
      fieldPath:   field.fieldPath,
      fieldType:   field.type,
      mandatory:   field.mandatory,
      valid:       dedupedValid,
      invalid:     dedupedInvalid,
      recommended,
    };
  }

  // ═══════════════════════════════════════════════════════════
  // generateForAllFields
  // Generates datasets for all fields in schema
  // ═══════════════════════════════════════════════════════════
  generateForAllFields(fields: ResolvedField[]): Map<string, FieldDataSet> {
    const dataMap = new Map<string, FieldDataSet>();

    for (const field of fields) {
      dataMap.set(field.fieldPath, this.generateForField(field));
    }

    logger.info(
      `DataGenerator: generated datasets for ${dataMap.size} fields`
    );

    return dataMap;
  }

  // ═══════════════════════════════════════════════════════════
  // generateByType — core type-based generation logic
  // ═══════════════════════════════════════════════════════════
  private generateByType(field: ResolvedField): {
    valid: GeneratedValue[];
    invalid: GeneratedValue[];
  } {
    switch (field.type) {

      // ─── Email ──────────────────────────────────────────────
      case "email":
        return {
          valid: [
            this.make(`test${this.runId}@astra.com`,   "typeDefault", "Valid email with run ID"),
            this.make("user@example.com",               "typeDefault", "Standard valid email"),
            this.make("qa.test+tag@domain.co.in",       "typeDefault", "Email with plus tag"),
          ],
          invalid: [
            this.makeBad("notanemail",       "No @ symbol"),
            this.makeBad("missing@",         "No domain"),
            this.makeBad("@nodomain.com",    "No local part"),
            this.makeBad("spaces @test.com", "Space in email"),
          ],
        };

      // ─── Password ───────────────────────────────────────────
      case "password":
        return {
          valid: [
            this.make("Test@1234",    "typeDefault", "Password with upper, number, special"),
            this.make("Secure#Pass9", "typeDefault", "Strong password"),
            this.make("Astra@2024!",  "typeDefault", "Framework themed password"),
          ],
          invalid: [
            this.makeBad("weak",       "Too short, no special chars"),
            this.makeBad("12345678",   "No uppercase or special"),
            this.makeBad("password",   "Common weak password"),
            this.makeBad("NoSpecial1", "Missing special character"),
          ],
        };

      // ─── Phone ──────────────────────────────────────────────
      case "phone":
        return {
          valid: [
            this.make("9876543210", "typeDefault", "Valid Indian mobile"),
            this.make("8123456789", "typeDefault", "Valid Indian mobile"),
            this.make("7001234567", "typeDefault", "Valid Indian mobile"),
          ],
          invalid: [
            this.makeBad("12345",       "Too short"),
            this.makeBad("0123456789",  "Starts with 0 — invalid Indian mobile"),
            this.makeBad("abcdefghij",  "Non-numeric"),
            this.makeBad("99999",       "Too few digits"),
          ],
        };

      // ─── Number ─────────────────────────────────────────────
      case "number": {
        const min = field.validationRule?.min ?? 1;
        const max = field.validationRule?.max ?? 9999;
        const mid = Math.floor((min + max) / 2);
        return {
          valid: [
            this.make(String(mid),   "typeDefault", "Middle value"),
            this.make(String(min),   "boundary",    "Minimum valid value"),
            this.make(String(max),   "boundary",    "Maximum valid value"),
          ],
          invalid: [
            this.makeBad(String(min - 1), "Below minimum"),
            this.makeBad(String(max + 1), "Above maximum"),
            this.makeBad("abc",           "Non-numeric"),
            this.makeBad("-1",            "Negative value"),
          ],
        };
      }

      // ─── Date ───────────────────────────────────────────────
      case "date":
        return {
          valid: [
            this.make("1995-06-15", "typeDefault", "Valid past date"),
            this.make("2000-01-01", "typeDefault", "Y2K date"),
            this.make("1990-12-25", "typeDefault", "Valid DOB date"),
          ],
          invalid: [
            this.makeBad("32-13-2000", "Invalid day/month"),
            this.makeBad("2999-99-99", "Far future invalid date"),
            this.makeBad("notadate",   "Non-date string"),
            this.makeBad("",           "Empty date"),
          ],
        };

      // ─── Dropdown ───────────────────────────────────────────
      case "dropdown":
        if (field.validValues?.length) {
          return {
            valid: field.validValues.slice(0, 3).map((v) =>
              this.make(v, "enumValue", `Dropdown option: ${v}`)
            ),
            invalid: [
              this.makeBad("__INVALID_OPTION__", "Non-existent dropdown value"),
              this.makeBad("",                   "Empty selection"),
            ],
          };
        }
        return { valid: [], invalid: [] };

      // ─── Checkbox ───────────────────────────────────────────
      case "checkbox":
        return {
          valid: [
            this.make("true",  "typeDefault", "Checked state"),
          ],
          invalid: [
            this.make("false", "typeDefault", "Unchecked state"),
          ],
        };

      // ─── Textarea ───────────────────────────────────────────
      case "textarea": {
        const minLen = field.validationRule?.minLength ?? 10;
        const maxLen = field.validationRule?.maxLength ?? 500;
        return {
          valid: [
            this.make(
              "ASTRA automated test input — valid description text for testing purposes.",
              "typeDefault",
              "Standard textarea content"
            ),
            this.make("A".repeat(minLen), "boundary", `Minimum length (${minLen}) text`),
          ],
          invalid: [
            this.makeBad("A".repeat(maxLen + 1), `Exceeds max length (${maxLen})`),
            this.makeBad("",                      "Empty textarea"),
          ],
        };
      }

      // ─── URL ────────────────────────────────────────────────
      case "url":
        return {
          valid: [
            this.make("https://www.example.com",    "typeDefault", "Valid HTTPS URL"),
            this.make("https://test.astra-app.com", "typeDefault", "Valid test URL"),
          ],
          invalid: [
            this.makeBad("notaurl",       "No protocol"),
            this.makeBad("ftp://old.com", "Non-HTTP protocol"),
            this.makeBad("",             "Empty URL"),
          ],
        };

      // ─── Text (default) ─────────────────────────────────────
      case "text":
      default:
        return this.generateTextValues(field);
    }
  }

  // ═══════════════════════════════════════════════════════════
  // generateTextValues — smart text generation based on field name
  // ═══════════════════════════════════════════════════════════
  private generateTextValues(field: ResolvedField): {
    valid: GeneratedValue[];
    invalid: GeneratedValue[];
  } {
    const name    = field.name.toLowerCase();
    const minLen  = field.validationRule?.minLength ?? 2;
    const maxLen  = field.validationRule?.maxLength ?? 100;

    // ─── Name fields ──────────────────────────────────────────
    if (/first.?name|fname/i.test(name)) {
      return {
        valid: [
          this.make("Karthick",  "typeDefault", "Valid first name"),
          this.make("Priya",     "typeDefault", "Valid first name"),
          this.make("John",      "typeDefault", "Valid first name"),
        ],
        invalid: [
          this.makeBad("A",          `Too short (min ${minLen})`),
          this.makeBad("123Name",    "Starts with numbers"),
          this.makeBad("",           "Empty first name"),
        ],
      };
    }

    if (/last.?name|lname|surname/i.test(name)) {
      return {
        valid: [
          this.make("Kumar",    "typeDefault", "Valid last name"),
          this.make("Smith",    "typeDefault", "Valid last name"),
          this.make("Raj",      "typeDefault", "Valid last name"),
        ],
        invalid: [
          this.makeBad("",   "Empty last name"),
          this.makeBad("1",  "Too short / numeric"),
        ],
      };
    }

    // ─── Username ─────────────────────────────────────────────
    if (/user.?name|username/i.test(name)) {
      return {
        valid: [
          this.make(`astra_user_${this.runId}`, "unique",       "Unique username"),
          this.make("test_user_01",              "typeDefault",  "Standard username"),
          this.make("qa_runner",                 "typeDefault",  "QA username"),
        ],
        invalid: [
          this.makeBad("ab",                    `Too short (min ${minLen})`),
          this.makeBad("user name",             "Contains space"),
          this.makeBad("a".repeat(maxLen + 1),  `Exceeds max length (${maxLen})`),
          this.makeBad("",                      "Empty username"),
        ],
      };
    }

    // ─── Address / Street ─────────────────────────────────────
    if (/street|address|addr/i.test(name)) {
      return {
        valid: [
          this.make("12 Main Street",      "typeDefault", "Valid street address"),
          this.make("45 Gandhi Road",      "typeDefault", "Valid street address"),
          this.make("Plot 7, Lake View",   "typeDefault", "Valid plot address"),
        ],
        invalid: [
          this.makeBad("",  "Empty address"),
          this.makeBad("A", `Too short (min ${minLen})`),
        ],
      };
    }

    // ─── City ─────────────────────────────────────────────────
    if (/city|town/i.test(name)) {
      return {
        valid: [
          this.make("Chennai",   "typeDefault", "Valid city"),
          this.make("Bangalore", "typeDefault", "Valid city"),
          this.make("Mumbai",    "typeDefault", "Valid city"),
        ],
        invalid: [
          this.makeBad("",      "Empty city"),
          this.makeBad("12345", "Numeric city name"),
        ],
      };
    }

    // ─── Pincode / Zipcode ────────────────────────────────────
    if (/pin.?code|zip.?code|postal/i.test(name)) {
      return {
        valid: [
          this.make("600001", "typeDefault", "Valid Chennai pincode"),
          this.make("560001", "typeDefault", "Valid Bangalore pincode"),
          this.make("400001", "typeDefault", "Valid Mumbai pincode"),
        ],
        invalid: [
          this.makeBad("12345",   "5-digit — too short for India"),
          this.makeBad("0000000", "All zeros"),
          this.makeBad("abcdef",  "Non-numeric pincode"),
          this.makeBad("",        "Empty pincode"),
        ],
      };
    }

    // ─── Generic text fallback ────────────────────────────────
    return {
      valid: [
        this.make("TestValue001",          "typeDefault", "Generic valid text"),
        this.make("SampleInput_ASTRA",     "typeDefault", "Generic valid text"),
        this.make("A".repeat(minLen + 1),  "boundary",    `Just above minimum (${minLen})`),
      ],
      invalid: [
        this.makeBad("",                      "Empty value"),
        this.makeBad("A".repeat(maxLen + 1),  `Exceeds max length (${maxLen})`),
      ],
    };
  }

  // ═══════════════════════════════════════════════════════════
  // generateBoundaryValues — min/max boundary test cases
  // ═══════════════════════════════════════════════════════════
  private generateBoundaryValues(
    rule?: ValidationRule,
    type?: FieldType
  ): { valid: GeneratedValue[]; invalid: GeneratedValue[] } {
    if (!rule) return { valid: [], invalid: [] };

    const valid:   GeneratedValue[] = [];
    const invalid: GeneratedValue[] = [];

    // ─── String length boundaries ─────────────────────────────
    if (rule.minLength !== undefined) {
      valid.push(
        this.make(
          "A".repeat(rule.minLength),
          "boundary",
          `Exact minimum length (${rule.minLength})`
        )
      );
      if (rule.minLength > 1) {
        invalid.push(
          this.makeBad(
            "A".repeat(rule.minLength - 1),
            `One below minimum length (${rule.minLength - 1})`
          )
        );
      }
    }

    if (rule.maxLength !== undefined) {
      valid.push(
        this.make(
          "A".repeat(rule.maxLength),
          "boundary",
          `Exact maximum length (${rule.maxLength})`
        )
      );
      invalid.push(
        this.makeBad(
          "A".repeat(rule.maxLength + 1),
          `One above maximum length (${rule.maxLength + 1})`
        )
      );
    }

    return { valid, invalid };
  }

  // ═══════════════════════════════════════════════════════════
  // generateUniqueValue — UUID-based unique value
  // ═══════════════════════════════════════════════════════════
  private generateUniqueValue(field: ResolvedField): GeneratedValue {
    const uniqueVal = `${field.name}_${this.runId}_${Date.now()}`;
    return {
      value:    uniqueVal,
      isValid:  true,
      strategy: "unique",
      reason:   `Unique value for run ${this.runId}`,
    };
  }

  // ═══════════════════════════════════════════════════════════
  // Factories
  // ═══════════════════════════════════════════════════════════
  private make(
    value:    string,
    strategy: GenerationStrategy,
    reason:   string
  ): GeneratedValue {
    return { value, isValid: true, strategy, reason };
  }

  private makeBad(value: string, reason: string): GeneratedValue {
    return { value, isValid: false, strategy: "invalidSample", reason };
  }

  // ═══════════════════════════════════════════════════════════
  // deduplicate — removes duplicate values
  // ═══════════════════════════════════════════════════════════
  private deduplicate(values: GeneratedValue[]): GeneratedValue[] {
    const seen = new Set<string>();
    return values.filter((v) => {
      if (seen.has(v.value)) return false;
      seen.add(v.value);
      return true;
    });
  }
}