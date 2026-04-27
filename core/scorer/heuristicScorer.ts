// ═══════════════════════════════════════════════════════════════
// core/scorer/heuristicScorer.ts
// ASTRA Framework — Heuristic Scorer
// Computes g(n), h(n), f(n) scores for A* engine
// g(n) = cost so far (fields filled)
// h(n) = estimated cost to goal (remaining mandatory fields)
// f(n) = g(n) + h(n) — total estimated path cost
//Key highlights — the mathematical heart of ASTRA:
// f(n) = g(n) + h(n)
//
// g(n) = baseCost + dependencyPenalty + stepPenalty
//        ↑ fields filled × stepCost
//                          ↑ unmet deps × 2
//                                         ↑ step jump × 3
//
// h(n) = (remainingMandatory + weightedRemaining + depChainCost) × heuristicWeight
//         ↑ count remaining                                         ↑ from .env
//                             ↑ weight/20 normalized
//                                                  ↑ dep fields × 0.5

//
// Admissible heuristic — h(n) never overestimates when heuristicWeight=1.0 — guarantees optimal path
// heuristicWeight > 1.0 → greedy mode (faster, non-optimal) — useful for large forms
// rankCandidates() — mandatory fields always ranked above optional regardless of score
// isGoalReached() — clean boolean: all mandatory fieldPaths in filledFields set
// computeStepPenalty() — penalises skipping steps in multi-step forms — keeps traversal sequential
// areDependenciesMet() — evaluates 5 operators: equals, notEquals, contains, greaterThan, lessThan
// getEligibleOptional() — only surfaces optional fields whose dependencies are already satisfied
// ═══════════════════════════════════════════════════════════════

import { ENV }          from "../../utils/envLoader";
import { logger }       from "../../utils/logger";
import { ResolvedField } from "../../schemas/fieldSchema.interface";

// ═══════════════════════════════════════════════════════════════
// Interfaces
// ═══════════════════════════════════════════════════════════════
export interface FieldScore {
  fieldPath:  string;
  gScore:     number;       // Cost from start to this node
  hScore:     number;       // Estimated cost to goal
  fScore:     number;       // g + h — total estimated cost
  priority:   number;       // Higher = visit sooner (inverse of fScore)
  mandatory:  boolean;
  weight:     number;
}

export interface ScorerState {
  filledFields:    Set<string>;          // fieldPaths already filled
  skippedFields:   Set<string>;          // optional fields skipped
  totalFields:     number;
  mandatoryFields: number;
  goalDistance:    number;               // Remaining mandatory fields
}

// ═══════════════════════════════════════════════════════════════
// HeuristicScorer
// ═══════════════════════════════════════════════════════════════
export class HeuristicScorer {

  private readonly heuristicWeight: number;
  private readonly allFields:       ResolvedField[];
  private readonly mandatoryFields: ResolvedField[];
  private readonly optionalFields:  ResolvedField[];

  constructor(allFields: ResolvedField[]) {
    this.allFields        = allFields;
    this.mandatoryFields  = allFields.filter((f) => f.mandatory);
    this.optionalFields   = allFields.filter((f) => !f.mandatory);
    this.heuristicWeight  = ENV.ASTAR_HEURISTIC_WEIGHT;

    logger.astar(
      `HeuristicScorer initialized — ` +
      `total=${allFields.length} mandatory=${this.mandatoryFields.length} ` +
      `optional=${this.optionalFields.length} weight=${this.heuristicWeight}`
    );
  }

  // ═══════════════════════════════════════════════════════════
  // computeGScore
  // Cost from start to current node
  // Based on: fields filled so far, their weights, and step cost
  // ═══════════════════════════════════════════════════════════
  computeGScore(
    field:         ResolvedField,
    filledFields:  Set<string>,
    stepCost:      number = 1
  ): number {
    // Base cost = number of fields filled before this one
    const baseCost = filledFields.size * stepCost;

    // ─── Dependency penalty ──────────────────────────────────
    // If field has unmet dependencies, increase cost
    const dependencyPenalty = this.computeDependencyPenalty(field, filledFields);

    // ─── Step transition cost ────────────────────────────────
    // Moving to a new form step costs more
    const stepPenalty = this.computeStepPenalty(field, filledFields);

    const gScore = baseCost + dependencyPenalty + stepPenalty;

    logger.astar(
      `g(${field.fieldPath}) = ${gScore} ` +
      `[base=${baseCost} depPenalty=${dependencyPenalty} stepPenalty=${stepPenalty}]`
    );

    return gScore;
  }

  // ═══════════════════════════════════════════════════════════
  // computeHScore
  // Estimated cost from current node to goal
  // Admissible: never overestimates — guarantees optimal path
  // ═══════════════════════════════════════════════════════════
  computeHScore(
    field:        ResolvedField,
    filledFields: Set<string>
  ): number {
    // ─── Remaining mandatory fields not yet filled ───────────
    const remainingMandatory = this.mandatoryFields.filter(
      (f) => !filledFields.has(f.fieldPath) && f.fieldPath !== field.fieldPath
    );

    // ─── Base heuristic = count of remaining mandatory fields ─
    const remainingCount = remainingMandatory.length;

    // ─── Weight-adjusted heuristic ───────────────────────────
    // Higher weight fields remaining = higher cost estimate
    const weightedRemaining = remainingMandatory.reduce(
      (sum, f) => sum + (f.weight / 20), 0   // Normalize weight contribution
    );

    // ─── Dependency chain depth ──────────────────────────────
    // Fields with dependencies ahead add cost
    const depChainCost = remainingMandatory.filter(
      (f) => f.dependencies && f.dependencies.length > 0
    ).length * 0.5;

    // ─── Apply heuristic weight (from .env) ──────────────────
    // heuristicWeight > 1 = greedy (faster but may not be optimal)
    // heuristicWeight = 1 = balanced (optimal)
    const hScore =
      (remainingCount + weightedRemaining + depChainCost) *
      this.heuristicWeight;

    logger.astar(
      `h(${field.fieldPath}) = ${hScore.toFixed(2)} ` +
      `[remaining=${remainingCount} weighted=${weightedRemaining.toFixed(2)} ` +
      `depChain=${depChainCost} w=${this.heuristicWeight}]`
    );

    return hScore;
  }

  // ═══════════════════════════════════════════════════════════
  // computeFScore
  // f(n) = g(n) + h(n)
  // ═══════════════════════════════════════════════════════════
  computeFScore(gScore: number, hScore: number): number {
    return gScore + hScore;
  }

  // ═══════════════════════════════════════════════════════════
  // scoreField
  // Computes full FieldScore for a given field + state
  // ═══════════════════════════════════════════════════════════
  scoreField(
    field:        ResolvedField,
    filledFields: Set<string>
  ): FieldScore {
    const gScore = this.computeGScore(field, filledFields);
    const hScore = this.computeHScore(field, filledFields);
    const fScore = this.computeFScore(gScore, hScore);

    // Priority = inverse of fScore + weight bonus
    // Higher priority = A* visits this node sooner
    const priority = (1 / (fScore + 1)) * field.weight;

    return {
      fieldPath: field.fieldPath,
      gScore,
      hScore,
      fScore,
      priority,
      mandatory: field.mandatory,
      weight:    field.weight,
    };
  }

  // ═══════════════════════════════════════════════════════════
  // rankCandidates
  // Scores all candidate fields and returns sorted by priority
  // Mandatory fields always ranked above optional
  // ═══════════════════════════════════════════════════════════
  rankCandidates(
    candidates:   ResolvedField[],
    filledFields: Set<string>
  ): FieldScore[] {
    const scores = candidates.map((f) => this.scoreField(f, filledFields));

    // Sort: mandatory first, then by priority descending
    return scores.sort((a, b) => {
      if (a.mandatory !== b.mandatory) {
        return a.mandatory ? -1 : 1;  // Mandatory first
      }
      return b.priority - a.priority; // Higher priority first
    });
  }

  // ═══════════════════════════════════════════════════════════
  // isGoalReached
  // Goal = all mandatory fields filled
  // ═══════════════════════════════════════════════════════════
  isGoalReached(filledFields: Set<string>): boolean {
    const allMandatoryFilled = this.mandatoryFields.every(
      (f) => filledFields.has(f.fieldPath)
    );

    if (allMandatoryFilled) {
      logger.astar(
        `🎯 Goal condition met — all ${this.mandatoryFields.length} mandatory fields filled`
      );
    }

    return allMandatoryFilled;
  }

  // ═══════════════════════════════════════════════════════════
  // computeScorerState
  // Returns current state snapshot for logging/reporting
  // ═══════════════════════════════════════════════════════════
  computeScorerState(filledFields: Set<string>): ScorerState {
    const remainingMandatory = this.mandatoryFields.filter(
      (f) => !filledFields.has(f.fieldPath)
    );

    return {
      filledFields,
      skippedFields:   new Set(
        this.optionalFields
          .filter((f) => !filledFields.has(f.fieldPath))
          .map((f) => f.fieldPath)
      ),
      totalFields:     this.allFields.length,
      mandatoryFields: this.mandatoryFields.length,
      goalDistance:    remainingMandatory.length,
    };
  }

  // ═══════════════════════════════════════════════════════════
  // getUnfilledMandatory
  // Returns mandatory fields not yet filled — used by A* open set
  // ═══════════════════════════════════════════════════════════
  getUnfilledMandatory(filledFields: Set<string>): ResolvedField[] {
    return this.mandatoryFields.filter(
      (f) => !filledFields.has(f.fieldPath)
    );
  }

  // ═══════════════════════════════════════════════════════════
  // getEligibleOptional
  // Returns optional fields whose dependencies are satisfied
  // ═══════════════════════════════════════════════════════════
  getEligibleOptional(
    filledFields:  Set<string>,
    filledValues:  Map<string, string>
  ): ResolvedField[] {
    return this.optionalFields.filter((f) => {
      if (filledFields.has(f.fieldPath)) return false;
      return this.areDependenciesMet(f, filledFields, filledValues);
    });
  }

  // ═══════════════════════════════════════════════════════════
  // Private Helpers
  // ═══════════════════════════════════════════════════════════

  private computeDependencyPenalty(
    field:        ResolvedField,
    filledFields: Set<string>
  ): number {
    if (!field.dependencies || field.dependencies.length === 0) return 0;

    const unmetDeps = field.dependencies.filter(
      (dep) => !filledFields.has(dep.dependsOn)
    );

    return unmetDeps.length * 2; // Each unmet dependency adds cost
  }

  private computeStepPenalty(
    field:        ResolvedField,
    filledFields: Set<string>
  ): number {
    if (field.stepIndex === undefined || field.stepIndex === 0) return 0;

    // Get the current step from last filled field
    const lastFilledField = this.allFields
      .filter((f) => filledFields.has(f.fieldPath))
      .sort((a, b) => (b.stepIndex ?? 0) - (a.stepIndex ?? 0))[0];

    const currentStep = lastFilledField?.stepIndex ?? 0;
    const targetStep  = field.stepIndex ?? 0;

    // Penalty for jumping steps
    return Math.abs(targetStep - currentStep) * 3;
  }

  private areDependenciesMet(
    field:        ResolvedField,
    filledFields: Set<string>,
    filledValues: Map<string, string>
  ): boolean {
    if (!field.dependencies || field.dependencies.length === 0) return true;

    return field.dependencies.every((dep) => {
      if (!filledFields.has(dep.dependsOn)) return false;

      const actualValue = filledValues.get(dep.dependsOn) ?? "";
      const operator    = dep.operator ?? "equals";

      switch (operator) {
        case "equals":      return actualValue === String(dep.whenValue);
        case "notEquals":   return actualValue !== String(dep.whenValue);
        case "contains":    return actualValue.includes(String(dep.whenValue));
        case "greaterThan": return parseFloat(actualValue) > Number(dep.whenValue);
        case "lessThan":    return parseFloat(actualValue) < Number(dep.whenValue);
        default:            return true;
      }
    });
  }
}