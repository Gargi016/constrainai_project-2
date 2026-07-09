"use client";

import { Constraint, constraintToString } from "@/lib/types";

interface Props {
  constraints: Constraint[];
  coreIds: Set<string>;
  onRetract: (constraintId: string) => void;
  retracting?: string | null;
}

export default function ConstraintSidebar({
  constraints,
  coreIds,
  onRetract,
  retracting,
}: Props) {
  return (
    <div>
      <p className="panel-label">Constraints ({constraints.length})</p>
      {constraints.length === 0 ? (
        <p className="empty-state">No active constraints yet.</p>
      ) : (
        <div className="constraint-list">
          {constraints.map((c) => (
            <div
              key={c.id}
              className={`constraint-row ${coreIds.has(c.id) ? "in-core" : ""} ${c.status}`}
            >
              <div className="constraint-main">
                <div className="constraint-expr">
                  <span className="constraint-id">[{c.id}]</span>
                  {constraintToString(c)}
                </div>
                <div className="constraint-source">
                  turn {c.source_turn}: &ldquo;{c.source_text}&rdquo;
                </div>
              </div>
              {c.status === "active" && (
                <button
                  className="retract-btn"
                  onClick={() => onRetract(c.id)}
                  disabled={retracting === c.id}
                  aria-label={`Retract constraint ${c.id}`}
                  title="Retract this constraint"
                >
                  ✕
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
