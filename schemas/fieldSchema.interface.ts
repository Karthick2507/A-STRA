// ═══════════════════════════════════════════════════════════════
// schemas/fieldSchema.interface.ts
// ASTRA Framework — Core Schema Interface
// Defines the complete type contract for all schemas
// consumed by A* engine, data generator, and code generator
// ═══════════════════════════════════════════════════════════════
//Key highlights:
//
// DataHints added — validSamples, invalidSamples, format, locale, unique — feeds data generator directly
// AStarConfig per schema — allows individual schemas to override .env A* settings
// GoalCondition covers both targets cleanly — UI uses successSelector/successText/urlContains, API uses successCodes
// ResolvedField — the flattened node the A* engine operates on — no nesting, all inheritance resolved
// flattenSchema() — core utility — flattens hierarchical schema into flat node graph with fieldPath like address.street
// resolveField() + resolveChild() both apply combined weight = field.weight + section.weight — section importance amplifies field importance
// getMandatoryFields(), getOptionalFields(), getFieldByPath() — utility exports used by A* engine and generators
// ═══════════════════════════════════════════════════════════════
// Field Types
// ═══════════════════════════════════════════════════════════════
export type FieldType =
  | "text"
  | "number"
  | "email"
  | "password"
  | "dropdown"
  | "date"
  | "checkbox"
  | "phone"
  | "textarea"
  | "radio"
  | "file"
  | "url"
  | "search";

// ═══════════════════════════════════════════════════════════════
// Schema Target
// ═══════════════════════════════════════════════════════════════
export type SchemaTarget = "ui" | "api";

// ═══════════════════════════════════════════════════════════════
// Validation Rule
// ═══════════════════════════════════════════════════════════════
export interface ValidationRule {
  pattern?:      string;
  minLength?:    number;
  maxLength?:    number;
  min?:          number;
  max?:          number;
  errorMessage?: string;
  customFn?:     string;
}

// ═══════════════════════════════════════════════════════════════
// Field Dependency
// ═══════════════════════════════════════════════════════════════
export interface FieldDependency {
  dependsOn:  string;
  whenValue:  string | boolean | number;
  operator?:  "equals" | "notEquals" | "contains" | "greaterThan" | "lessThan";
}

// ═══════════════════════════════════════════════════════════════
// Data Generation Hints
// ═══════════════════════════════════════════════════════════════
export interface DataHints {
  validSamples?:   string[];
  invalidSamples?: string[];
  format?:         string;
  locale?:         string;
  unique?:         boolean;
}

// ═══════════════════════════════════════════════════════════════
// Child Field — inherits mandatory from parent Section
// ═══════════════════════════════════════════════════════════════
export interface ChildField {
  name:             string;
  type:             FieldType;
  weight:           number;
  label?:           string;
  placeholder?:     string;
  validValues?:     string[];
  validationRule?:  ValidationRule;
  dependencies?:    FieldDependency[];
  dataHints?:       DataHints;
  apiKey?:          string;
  selector?:        string;
}

// ═══════════════════════════════════════════════════════════════
// Field — top-level field, can have children
// ═══════════════════════════════════════════════════════════════
export interface Field extends ChildField {
  children?: ChildField[];
}

// ═══════════════════════════════════════════════════════════════
// Section — mandatory drives ALL children
// ═══════════════════════════════════════════════════════════════
export interface Section {
  sectionName:  string;
  mandatory:    boolean;
  weight:       number;
  label?:       string;
  description?: string;
  fields:       Field[];
  stepIndex?:   number;
}

// ═══════════════════════════════════════════════════════════════
// Goal Condition
// ═══════════════════════════════════════════════════════════════
export interface GoalCondition {
  ui?: {
    successSelector?:  string;
    successText?:      string;
    urlContains?:      string;
    waitForSelector?:  string;
  };
  api?: {
    successCodes:      number[];
    responseContains?: string;
  };
}

// ═══════════════════════════════════════════════════════════════
// A* Config — per-schema overrides
// ═══════════════════════════════════════════════════════════════
export interface AStarConfig {
  maxIterations?:    number;
  heuristicWeight?:  number;
  goalTimeout?:      number;
  allowPartialGoal?: boolean;
}

// ═══════════════════════════════════════════════════════════════
// Root FieldSchema
// ═══════════════════════════════════════════════════════════════
export interface FieldSchema {
  schemaId:      string;
  version:       string;
  target:        SchemaTarget;
  description?:  string;
  baseUrl?:      string;
  endpoint?:     string;
  method?:       string;
  goalCondition: GoalCondition;
  astarConfig?:  AStarConfig;
  sections:      Section[];
}

// ═══════════════════════════════════════════════════════════════
// Resolved Field — flattened for A* engine consumption
// All inheritance resolved, no nesting
// ═══════════════════════════════════════════════════════════════
export interface ResolvedField {
  sectionName:     string;
  fieldPath:       string;           // e.g "address.street"
  name:            string;
  type:            FieldType;
  mandatory:       boolean;          // Resolved from parent section
  weight:          number;           // Combined field + section weight
  label?:          string;
  placeholder?:    string;
  validValues?:    string[];
  validationRule?: ValidationRule;
  dependencies?:   FieldDependency[];
  dataHints?:      DataHints;
  apiKey?:         string;
  selector?:       string;
  stepIndex?:      number;
}

// ═══════════════════════════════════════════════════════════════
// Schema Resolution Utilities
// ═══════════════════════════════════════════════════════════════

/**
 * flattenSchema
 * Resolves all sections → fields → children into flat ResolvedField[]
 * Applies mandatory inheritance from Section to all children
 * Used by A* engine as its node graph
 */
export function flattenSchema(schema: FieldSchema): ResolvedField[] {
  const resolved: ResolvedField[] = [];

  for (const section of schema.sections) {
    for (const field of section.fields) {
      if (!field.children || field.children.length === 0) {
        // ─── Simple top-level field ────────────────────────────
        resolved.push(resolveField(field, section));
      } else {
        // ─── Parent with children — push children directly ────
        for (const child of field.children) {
          resolved.push(resolveChild(child, field.name, section));
        }
      }
    }
  }

  return resolved;
}

function resolveField(field: Field, section: Section): ResolvedField {
  return {
    sectionName:    section.sectionName,
    fieldPath:      field.name,
    name:           field.name,
    type:           field.type,
    mandatory:      section.mandatory,
    weight:         field.weight + section.weight,
    label:          field.label,
    placeholder:    field.placeholder,
    validValues:    field.validValues,
    validationRule: field.validationRule,
    dependencies:   field.dependencies,
    dataHints:      field.dataHints,
    apiKey:         field.apiKey,
    selector:       field.selector,
    stepIndex:      section.stepIndex,
  };
}

function resolveChild(
  child:      ChildField,
  parentName: string,
  section:    Section
): ResolvedField {
  return {
    sectionName:    section.sectionName,
    fieldPath:      `${parentName}.${child.name}`,
    name:           child.name,
    type:           child.type,
    mandatory:      section.mandatory,
    weight:         child.weight + section.weight,
    label:          child.label,
    placeholder:    child.placeholder,
    validValues:    child.validValues,
    validationRule: child.validationRule,
    dependencies:   child.dependencies,
    dataHints:      child.dataHints,
    apiKey:         child.apiKey,
    selector:       child.selector,
    stepIndex:      section.stepIndex,
  };
}

/** getMandatoryFields — A* must visit all of these */
export function getMandatoryFields(schema: FieldSchema): ResolvedField[] {
  return flattenSchema(schema).filter((f) => f.mandatory);
}

/** getOptionalFields — A* visits these based on heuristic score */
export function getOptionalFields(schema: FieldSchema): ResolvedField[] {
  return flattenSchema(schema).filter((f) => !f.mandatory);
}

/** getFieldByPath — finds resolved field by fieldPath */
export function getFieldByPath(
  schema:    FieldSchema,
  fieldPath: string
): ResolvedField | undefined {
  return flattenSchema(schema).find((f) => f.fieldPath === fieldPath);
}