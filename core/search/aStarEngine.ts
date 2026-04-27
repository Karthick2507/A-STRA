// ═══════════════════════════════════════════════════════════════
// core/search/aStarEngine.ts
// ASTRA Framework — A* Search Engine
// The crown jewel — navigates form field space using A* algorithm
// Finds optimal path through mandatory fields to reach goal
// ═══════════════════════════════════════════════════════════════
//The crown jewel is complete. Here's the full algorithm flow:
// SEED open set with dependency-free mandatory fields
//           ↓
// LOOP: pop lowest fScore node from priority queue
//           ↓
//       Skip if already in closed set
//           ↓
//       Mark visited → add to path → assign value
//           ↓
//       GOAL CHECK → all mandatory fields filled?
//         YES → sweep optional (if enabled) → return result
//         NO  → expand neighbours (unfilled mandatory ranked by scorer)
//           ↓
//       For each neighbour: tentativeG < existingG? → enqueue
//           ↓
// UNTIL: goal reached OR max iterations
// Key engineering highlights:
//
// PriorityQueue — custom min-heap by fScore — O(log n) enqueue/dequeue — no library dependency
// getStartCandidates() — seeds open set with dependency-free fields first — natural form order preserved
// expandNeighbours() — uses HeuristicScorer.rankCandidates() — mandatory always ranked above optional
// sweepOptional() — fills optional fields after goal — hScore=0 since goal already reached
// 3 convenience wrappers: searchNegative(), searchWithOptional(), searchFull() — used directly by code generators
// getSearchSummary() — pretty-prints the winning path with f-scores for each step

import { ENV }              from "../../utils/envLoader";
import { logger }           from "../../utils/logger";
import {
  FieldSchema,
  ResolvedField,
  flattenSchema,
  getMandatoryFields,
}                            from "../../schemas/fieldSchema.interface";
import { HeuristicScorer, FieldScore }   from "../scorer/heuristicScorer";
import { DataGenerator, FieldDataSet }   from "../generator/dataGenerator";

// ═══════════════════════════════════════════════════════════════
// Interfaces
// ═══════════════════════════════════════════════════════════════
export interface AStarNode {
  fieldPath:    string;
  field:        ResolvedField;
  gScore:       number;
  hScore:       number;
  fScore:       number;
  value:        string;           // Data value assigned to this field
  parent:       AStarNode | null; // Previous node in path
  depth:        number;           // Depth in search tree
}

export interface AStarResult {
  success:       boolean;
  path:          AStarNode[];     // Ordered field fill sequence
  filledValues:  Map<string, string>; // fieldPath → value
  iterations:    number;
  goalReached:   boolean;
  skippedFields: string[];
  executionMs:   number;
  dataMap:       Map<string, FieldDataSet>;
}

export interface AStarSearchOptions {
  includeOptional?: boolean;      // Also fill optional fields
  negativeMode?:    boolean;      // Use invalid values (negative test)
  stepByStep?:      boolean;      // Pause between steps (debug)
}

// ═══════════════════════════════════════════════════════════════
// Priority Queue — min-heap by fScore
// ═══════════════════════════════════════════════════════════════
class PriorityQueue {
  private readonly heap: AStarNode[] = [];

  enqueue(node: AStarNode): void {
    this.heap.push(node);
    this.bubbleUp(this.heap.length - 1);
  }

  dequeue(): AStarNode | undefined {
    if (this.heap.length === 0) return undefined;
    const min  = this.heap[0];
    const last = this.heap.pop()!;
    if (this.heap.length > 0) {
      this.heap[0] = last;
      this.sinkDown(0);
    }
    return min;
  }

  get size(): number { return this.heap.length; }
  isEmpty():  boolean { return this.heap.length === 0; }

  private bubbleUp(i: number): void {
    while (i > 0) {
      const parent = Math.floor((i - 1) / 2);
      if (this.heap[parent].fScore <= this.heap[i].fScore) break;
      [this.heap[parent], this.heap[i]] = [this.heap[i], this.heap[parent]];
      i = parent;
    }
  }

  private sinkDown(i: number): void {
    const n = this.heap.length;
    while (true) {
      let smallest = i;
      const left   = 2 * i + 1;
      const right  = 2 * i + 2;
      if (left  < n && this.heap[left].fScore  < this.heap[smallest].fScore) smallest = left;
      if (right < n && this.heap[right].fScore < this.heap[smallest].fScore) smallest = right;
      if (smallest === i) break;
      [this.heap[smallest], this.heap[i]] = [this.heap[i], this.heap[smallest]];
      i = smallest;
    }
  }
}

// ═══════════════════════════════════════════════════════════════
// AStarEngine
// ═══════════════════════════════════════════════════════════════
export class AStarEngine {

  private readonly schema:          FieldSchema;
  private readonly allFields:       ResolvedField[];
  private readonly mandatoryFields: ResolvedField[];
  private readonly scorer:          HeuristicScorer;
  private readonly generator:       DataGenerator;
  private readonly maxIterations:   number;

  constructor(schema: FieldSchema) {
    this.schema          = schema;
    this.allFields       = flattenSchema(schema);
    this.mandatoryFields = getMandatoryFields(schema);
    this.scorer          = new HeuristicScorer(this.allFields);
    this.generator       = new DataGenerator();
    this.maxIterations   = schema.astarConfig?.maxIterations ?? ENV.ASTAR_MAX_ITERATIONS;

    logger.divider("A* Engine Initialized");
    logger.astar(`Schema: ${schema.schemaId} | Target: ${schema.target}`);
    logger.astar(`Total fields: ${this.allFields.length} | Mandatory: ${this.mandatoryFields.length}`);
    logger.astar(`Max iterations: ${this.maxIterations}`);
  }

  // ═══════════════════════════════════════════════════════════
  // search — main A* algorithm
  // Returns optimal ordered path through fields to reach goal
  // ═══════════════════════════════════════════════════════════
  search(options: AStarSearchOptions = {}): AStarResult {
    const startTime = Date.now();
    const {
      includeOptional = false,
      negativeMode    = false,
    } = options;

    logger.divider(`A* Search — ${negativeMode ? "NEGATIVE" : "POSITIVE"} mode`);

    // ─── Pre-generate data for all fields ─────────────────────
    const dataMap = this.generator.generateForAllFields(this.allFields);

    // ─── A* State ─────────────────────────────────────────────
    const openSet:      PriorityQueue          = new PriorityQueue();
    const closedSet:    Set<string>            = new Set();
    const filledFields: Set<string>            = new Set();
    const filledValues: Map<string, string>    = new Map();
    const gScoreMap:    Map<string, number>    = new Map();
    const finalPath:    AStarNode[]            = [];
    let   iterations = 0;

    // ─── Seed open set with dependency-free mandatory fields ──
    const startCandidates = this.getStartCandidates(dataMap, negativeMode);
    for (const node of startCandidates) {
      openSet.enqueue(node);
      gScoreMap.set(node.fieldPath, node.gScore);
    }

    logger.astar(`Open set seeded with ${openSet.size} start candidates`);

    // ═══════════════════════════════════════════════════════════
    // A* Main Loop
    // ═══════════════════════════════════════════════════════════
    while (!openSet.isEmpty() && iterations < this.maxIterations) {
      iterations++;

      // ─── Pop lowest fScore ───────────────────────────────
      const current = openSet.dequeue()!;

      // ─── Already visited? skip ───────────────────────────
      if (closedSet.has(current.fieldPath)) {
        logger.astar(`[${iterations}] Already closed: ${current.fieldPath} — skip`);
        continue;
      }

      // ─── Visit node ──────────────────────────────────────
      closedSet.add(current.fieldPath);
      filledFields.add(current.fieldPath);
      filledValues.set(current.fieldPath, current.value);
      finalPath.push(current);

      logger.astarStep(
        iterations,
        current.fieldPath,
        current.gScore,
        current.hScore,
        current.fScore
      );
      logger.astar(
        `  ↳ value="${current.value}" | depth=${current.depth} | mandatory=${current.field.mandatory}`
      );

      // ─── Goal check ──────────────────────────────────────
      if (this.scorer.isGoalReached(filledFields)) {

        // Optionally sweep up optional fields
        if (includeOptional) {
          this.sweepOptional(
            finalPath, filledFields, filledValues, dataMap, negativeMode
          );
        }

        const result = this.buildResult(
          true, finalPath, filledValues, iterations, startTime, dataMap
        );
        logger.goalReached(finalPath.map((n) => n.fieldPath), iterations);
        return result;
      }

      // ─── Expand neighbours ───────────────────────────────
      const neighbours = this.expandNeighbours(
        current, filledFields, filledValues, dataMap, negativeMode
      );

      for (const nb of neighbours) {
        if (closedSet.has(nb.fieldPath)) continue;

        const tentativeG = current.gScore + 1;
        const existingG  = gScoreMap.get(nb.fieldPath) ?? Infinity;

        if (tentativeG < existingG) {
          gScoreMap.set(nb.fieldPath, tentativeG);
          openSet.enqueue({ ...nb, gScore: tentativeG, parent: current });
        }
      }
    }

    // ─── Max iterations — return partial ─────────────────────
    logger.warn(`A* max iterations (${this.maxIterations}) reached — partial result`);
    return this.buildResult(
      false, finalPath, filledValues, iterations, startTime, dataMap
    );
  }

  // ═══════════════════════════════════════════════════════════
  // Convenience wrappers
  // ═══════════════════════════════════════════════════════════
  searchNegative():    AStarResult { return this.search({ negativeMode: true }); }
  searchWithOptional():AStarResult { return this.search({ includeOptional: true }); }
  searchFull():        AStarResult { return this.search({ includeOptional: true, negativeMode: false }); }

  // ═══════════════════════════════════════════════════════════
  // getStartCandidates
  // Seeds open set — mandatory fields with no dependencies first
  // ═══════════════════════════════════════════════════════════
  private getStartCandidates(
    dataMap:      Map<string, FieldDataSet>,
    negativeMode: boolean
  ): AStarNode[] {
    const noDep = this.mandatoryFields.filter(
      (f) => !f.dependencies || f.dependencies.length === 0
    );
    const seeds = noDep.length > 0 ? noDep : this.mandatoryFields.slice(0, 3);

    return seeds.map((field) => {
      const dataset = dataMap.get(field.fieldPath);
      const value   = this.pickValue(dataset, negativeMode);
      const scored  = this.scorer.scoreField(field, new Set());

      return {
        fieldPath: field.fieldPath,
        field,
        gScore:    scored.gScore,
        hScore:    scored.hScore,
        fScore:    scored.fScore,
        value,
        parent:    null,
        depth:     0,
      };
    });
  }

  // ═══════════════════════════════════════════════════════════
  // expandNeighbours
  // Returns scored neighbour nodes from current position
  // ═══════════════════════════════════════════════════════════
  private expandNeighbours(
    current:      AStarNode,
    filledFields: Set<string>,
    filledValues: Map<string, string>,
    dataMap:      Map<string, FieldDataSet>,
    negativeMode: boolean
  ): AStarNode[] {
    const unfilled = this.scorer.getUnfilledMandatory(filledFields);
    const ranked   = this.scorer.rankCandidates(unfilled, filledFields);

    return ranked.map((scored: FieldScore) => {
      const field   = this.allFields.find((f) => f.fieldPath === scored.fieldPath)!;
      const dataset = dataMap.get(field.fieldPath);
      const value   = this.pickValue(dataset, negativeMode);

      return {
        fieldPath: field.fieldPath,
        field,
        gScore:    scored.gScore,
        hScore:    scored.hScore,
        fScore:    scored.fScore,
        value,
        parent:    current,
        depth:     current.depth + 1,
      };
    });
  }

  // ═══════════════════════════════════════════════════════════
  // sweepOptional — fills optional fields post-goal
  // ═══════════════════════════════════════════════════════════
  private sweepOptional(
    path:         AStarNode[],
    filledFields: Set<string>,
    filledValues: Map<string, string>,
    dataMap:      Map<string, FieldDataSet>,
    negativeMode: boolean
  ): void {
    const eligible = this.scorer.getEligibleOptional(filledFields, filledValues);
    logger.astar(`Optional sweep: ${eligible.length} eligible fields`);

    for (const field of eligible) {
      const dataset = dataMap.get(field.fieldPath);
      const value   = this.pickValue(dataset, negativeMode);
      const scored  = this.scorer.scoreField(field, filledFields);

      path.push({
        fieldPath: field.fieldPath,
        field,
        gScore:    scored.gScore,
        hScore:    0,
        fScore:    scored.fScore,
        value,
        parent:    path[path.length - 1] ?? null,
        depth:     path.length,
      });

      filledFields.add(field.fieldPath);
      filledValues.set(field.fieldPath, value);
    }
  }

  // ═══════════════════════════════════════════════════════════
  // pickValue
  // ═══════════════════════════════════════════════════════════
  private pickValue(
    dataset:      FieldDataSet | undefined,
    negativeMode: boolean
  ): string {
    if (!dataset) return "";
    if (negativeMode && dataset.invalid.length > 0) {
      return dataset.invalid[Math.floor(Math.random() * dataset.invalid.length)].value;
    }
    return dataset.recommended.value;
  }

  // ═══════════════════════════════════════════════════════════
  // buildResult
  // ═══════════════════════════════════════════════════════════
  private buildResult(
    success:      boolean,
    path:         AStarNode[],
    filledValues: Map<string, string>,
    iterations:   number,
    startTime:    number,
    dataMap:      Map<string, FieldDataSet>
  ): AStarResult {
    const filledPaths   = new Set(path.map((n) => n.fieldPath));
    const skippedFields = this.allFields
      .filter((f) => !filledPaths.has(f.fieldPath))
      .map((f) => f.fieldPath);

    const executionMs = Date.now() - startTime;
    logger.astar(
      `Result: success=${success} | iter=${iterations} | path=${path.length} | skip=${skippedFields.length} | ${executionMs}ms`
    );

    return { success, path, filledValues, iterations, goalReached: success, skippedFields, executionMs, dataMap };
  }

  // ═══════════════════════════════════════════════════════════
  // getSearchSummary — readable summary string
  // ═══════════════════════════════════════════════════════════
  getSearchSummary(result: AStarResult): string {
    return [
      `─── A* Search Summary ───────────────────`,
      `  Goal Reached  : ${result.goalReached ? "✅ YES" : "❌ NO"}`,
      `  Iterations    : ${result.iterations}`,
      `  Path Length   : ${result.path.length} fields`,
      `  Skipped       : ${result.skippedFields.length} fields`,
      `  Execution     : ${result.executionMs}ms`,
      `  Path          :`,
      ...result.path.map((n, i) =>
        `    ${i + 1}. ${n.fieldPath.padEnd(30)} = "${n.value}" [f=${n.fScore.toFixed(1)}]`
      ),
      `─────────────────────────────────────────`,
    ].join("\n");
  }
}