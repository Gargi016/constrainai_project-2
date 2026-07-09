"use client";

import { RepairCandidate } from "@/lib/types";

interface Props {
  repairs: RepairCandidate[];
}

export default function RepairPanel({ repairs }: Props) {
  return (
    <div>
      <p className="panel-label">Solver-verified repairs</p>
      {repairs.length === 0 ? (
        <p className="empty-state">No repairs to suggest right now.</p>
      ) : (
        <div className="repair-list">
          {repairs.map((r) => (
            <div key={r.constraint_id} className="repair-card">
              <div className="repair-headline">
                {r.direction === "increase" ? "Increase" : "Decrease"}{" "}
                {r.variable_name} threshold by {Math.abs(r.delta).toLocaleString()}
              </div>
              <div className="repair-detail">
                [{r.constraint_id}] {r.original_value.toLocaleString()} →{" "}
                {r.new_value.toLocaleString()}
              </div>
              {r.verified_sat && <div className="verified-tag">verified: restores SAT</div>}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
