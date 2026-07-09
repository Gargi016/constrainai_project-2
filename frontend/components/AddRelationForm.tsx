"use client";

import { FormEvent, useState } from "react";

interface Props {
  availableVariables: string[];
  onSubmit: (lhs: string[], operator: "<=" | ">=", rhs: string[]) => Promise<void>;
  disabled?: boolean;
}

function parseVariableList(raw: string): string[] {
  return raw
    .split(/[,+]/)
    .map((s) => s.trim())
    .filter(Boolean);
}

export default function AddRelationForm({ availableVariables, onSubmit, disabled }: Props) {
  const [lhsRaw, setLhsRaw] = useState("");
  const [operator, setOperator] = useState<"<=" | ">=">("<=");
  const [rhsRaw, setRhsRaw] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const lhs = parseVariableList(lhsRaw);
    const rhs = parseVariableList(rhsRaw);
    if (lhs.length === 0 || rhs.length === 0) {
      setError("Enter at least one variable on each side.");
      return;
    }
    setSending(true);
    setError(null);
    try {
      await onSubmit(lhs, operator, rhs);
      setLhsRaw("");
      setRhsRaw("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to add relation.");
    } finally {
      setSending(false);
    }
  }

  return (
    <div>
      <p className="panel-label">Add relation constraint</p>
      {availableVariables.length > 0 && (
        <p className="empty-state" style={{ marginBottom: 8 }}>
          Known variables: {availableVariables.join(", ")}
        </p>
      )}
      <form className="relation-form" onSubmit={handleSubmit}>
        <input
          value={lhsRaw}
          onChange={(e) => setLhsRaw(e.target.value)}
          placeholder="gpu_cost, ram_cost, storage_cost"
          disabled={disabled || sending}
          aria-label="Left-hand side variables"
        />
        <select
          value={operator}
          onChange={(e) => setOperator(e.target.value as "<=" | ">=")}
          disabled={disabled || sending}
          aria-label="Operator"
        >
          <option value="<=">{"<="}</option>
          <option value=">=">{">="}</option>
        </select>
        <input
          value={rhsRaw}
          onChange={(e) => setRhsRaw(e.target.value)}
          placeholder="budget"
          disabled={disabled || sending}
          aria-label="Right-hand side variables"
        />
        <button type="submit" disabled={disabled || sending || !lhsRaw.trim() || !rhsRaw.trim()}>
          {sending ? "Adding…" : "Add"}
        </button>
      </form>
      {error && (
        <p style={{ color: "var(--accent-unsat)", fontSize: 12, marginTop: 6 }}>{error}</p>
      )}
      <p className="empty-state" style={{ marginTop: 6 }}>
        Comma-separate multiple variables on one side to sum them, e.g.
        &ldquo;gpu_cost, ram_cost, storage_cost&rdquo; ≤ &ldquo;budget&rdquo;.
      </p>
    </div>
  );
}
