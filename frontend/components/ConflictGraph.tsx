"use client";

import { Constraint, constraintToString, constraintVariables } from "@/lib/types";

interface Props {
  constraints: Constraint[];
  coreIds: Set<string>;
}

const VAR_Y = 46;
const CONSTRAINT_Y = 200;
const NODE_SPACING = 92;
const MARGIN = 56;

export default function ConflictGraph({ constraints, coreIds }: Props) {
  const variableNames = Array.from(
    constraints.reduce((set, c) => {
      constraintVariables(c).forEach((v) => set.add(v));
      return set;
    }, new Set<string>())
  ).sort();

  const width = Math.max(
    480,
    MARGIN * 2 + NODE_SPACING * Math.max(variableNames.length, constraints.length, 1)
  );
  const height = 240;

  const varX = (i: number) =>
    MARGIN + (i + 0.5) * ((width - MARGIN * 2) / Math.max(variableNames.length, 1));
  const constraintX = (i: number) =>
    MARGIN + (i + 0.5) * ((width - MARGIN * 2) / Math.max(constraints.length, 1));

  const varIndex = new Map(variableNames.map((v, i) => [v, i]));
  const variablesTouchedByCore = new Set<string>();
  constraints
    .filter((c) => coreIds.has(c.id))
    .forEach((c) => constraintVariables(c).forEach((v) => variablesTouchedByCore.add(v)));

  return (
    <div className="graph-wrap">
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" role="img" aria-label="Constraint conflict graph">
        {/* wires, drawn first so nodes sit on top */}
        {constraints.map((c, ci) => {
          const inCore = coreIds.has(c.id);
          const cx = constraintX(ci);
          const cy = CONSTRAINT_Y;
          return Array.from(constraintVariables(c)).map((vname) => {
            const vi = varIndex.get(vname)!;
            const vx = varX(vi);
            const vy = VAR_Y;
            return (
              <line
                key={`${c.id}-${vname}`}
                x1={vx}
                y1={vy + 16}
                x2={cx}
                y2={cy - 16}
                stroke={inCore ? "var(--accent-core)" : "var(--border)"}
                strokeWidth={inCore ? 2 : 1}
                strokeDasharray={inCore ? "0" : "0"}
              />
            );
          });
        })}

        {/* variable terminals (circles) */}
        {variableNames.map((vname, i) => {
          const x = varX(i);
          const highlighted = variablesTouchedByCore.has(vname);
          return (
            <g key={vname}>
              <circle
                cx={x}
                cy={VAR_Y}
                r={16}
                fill="var(--bg-panel-raised)"
                stroke={highlighted ? "var(--accent-core)" : "var(--text-muted)"}
                strokeWidth={highlighted ? 2 : 1}
              />
              <text
                x={x}
                y={VAR_Y + 34}
                textAnchor="middle"
                fontFamily="var(--font-display)"
                fontSize="10.5"
                fill="var(--text-muted)"
              >
                {vname.length > 10 ? vname.slice(0, 9) + "…" : vname}
              </text>
            </g>
          );
        })}

        {/* constraint gates (diamonds) */}
        {constraints.map((c, i) => {
          const x = constraintX(i);
          const y = CONSTRAINT_Y;
          const inCore = coreIds.has(c.id);
          const size = 15;
          const points = [
            [x, y - size],
            [x + size, y],
            [x, y + size],
            [x - size, y],
          ]
            .map((p) => p.join(","))
            .join(" ");
          return (
            <g key={c.id}>
              <polygon
                points={points}
                fill={inCore ? "rgba(217,164,65,0.18)" : "var(--bg-panel-raised)"}
                stroke={inCore ? "var(--accent-core)" : "var(--text-muted)"}
                strokeWidth={inCore ? 2 : 1}
              />
              <text
                x={x}
                y={y - size - 8}
                textAnchor="middle"
                fontFamily="var(--font-display)"
                fontSize="10"
                fill="var(--text-muted)"
              >
                {c.id}
              </text>
            </g>
          );
        })}
      </svg>
      <div className="graph-legend">
        <span>
          <span className="legend-swatch" style={{ background: "var(--bg-panel-raised)", border: "1px solid var(--text-muted)" }} />
          variable
        </span>
        <span>
          <span className="legend-swatch" style={{ background: "var(--bg-panel-raised)", border: "1px solid var(--text-muted)" }} />
          constraint
        </span>
        <span>
          <span className="legend-swatch" style={{ background: "rgba(217,164,65,0.3)", border: "1px solid var(--accent-core)" }} />
          in conflict core
        </span>
      </div>
    </div>
  );
}
