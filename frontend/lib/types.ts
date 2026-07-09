// Mirrors constrainai/expressions.py and constrainai/constraints.py closely
// enough for display purposes. The frontend never re-implements any
// solving logic -- it only renders what the backend computed.

export type ExpressionNode =
  | { node: "var"; name: string }
  | { node: "const"; value: number }
  | { node: "neg"; operand: ExpressionNode }
  | { node: "scale"; factor: number; operand: ExpressionNode }
  | { node: "sum"; terms: ExpressionNode[] }
  | { node: "diff"; left: ExpressionNode; right: ExpressionNode };

export type ConstraintKind =
  | "bound"
  | "equality"
  | "relation"
  | "dependency"
  | "exclusion"
  | "membership";

export type Operator = "<=" | ">=" | "==" | "!=" | "requires" | "excludes" | "in";
export type Hardness = "hard" | "soft";
export type ConstraintStatus = "active" | "superseded" | "retracted";

export interface Constraint {
  id: string;
  kind: ConstraintKind;
  lhs: ExpressionNode;
  operator: Operator;
  rhs: ExpressionNode;
  source_turn: number;
  source_text: string;
  confidence: number;
  hardness: Hardness;
  priority: number;
  status: ConstraintStatus;
  supersedes: string | null;
}

export interface TurnOutcome {
  kind: "add" | "revise" | "retract" | "ambiguous" | "unrecognized";
  message: string;
  constraint_id: string | null;
  old_constraint_id: string | null;
}

export interface TurnResponse {
  outcome: TurnOutcome;
  turn_number: number;
  active_constraint_count: number;
  sat_status: SatStatus;
}

export interface SatStatus {
  result: "sat" | "unsat" | "unknown";
  model?: Record<string, number>;
}

export interface CheckResponse {
  result: "sat" | "unsat" | "unknown";
  model?: Record<string, number>;
  raw_core?: Constraint[];
  minimal_core?: Constraint[];
  minimal_core_verified?: boolean;
}

export interface RepairCandidate {
  constraint_id: string;
  variable_name: string;
  original_value: number;
  new_value: number;
  delta: number;
  direction: "increase" | "decrease";
  verified_sat: boolean;
  description: string;
}

export interface RepairsResponse {
  repairs_needed: boolean;
  repairs: RepairCandidate[];
}

// Renders an ExpressionNode as a human-readable string, mirroring
// Expression.__str__ in expressions.py.
export function exprToString(e: ExpressionNode): string {
  switch (e.node) {
    case "var":
      return e.name;
    case "const":
      return Number.isInteger(e.value) ? String(e.value) : String(e.value);
    case "neg":
      return `-(${exprToString(e.operand)})`;
    case "scale":
      return `${e.factor}*(${exprToString(e.operand)})`;
    case "sum":
      return e.terms.map(exprToString).join(" + ");
    case "diff":
      return `(${exprToString(e.left)} - ${exprToString(e.right)})`;
  }
}

// All variable names referenced by an expression, mirroring
// Expression.variables() in expressions.py.
export function exprVariables(e: ExpressionNode): Set<string> {
  switch (e.node) {
    case "var":
      return new Set([e.name]);
    case "const":
      return new Set();
    case "neg":
      return exprVariables(e.operand);
    case "scale":
      return exprVariables(e.operand);
    case "sum": {
      const out = new Set<string>();
      for (const t of e.terms) for (const v of exprVariables(t)) out.add(v);
      return out;
    }
    case "diff": {
      const out = new Set<string>();
      for (const v of exprVariables(e.left)) out.add(v);
      for (const v of exprVariables(e.right)) out.add(v);
      return out;
    }
  }
}

export function constraintVariables(c: Constraint): Set<string> {
  const out = new Set<string>();
  for (const v of exprVariables(c.lhs)) out.add(v);
  for (const v of exprVariables(c.rhs)) out.add(v);
  return out;
}

export function constraintToString(c: Constraint): string {
  return `${exprToString(c.lhs)} ${c.operator} ${exprToString(c.rhs)}`;
}
