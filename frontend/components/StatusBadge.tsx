"use client";

interface Props {
  result: "sat" | "unsat" | "unknown";
}

export default function StatusBadge({ result }: Props) {
  const label = result === "sat" ? "SAT" : result === "unsat" ? "UNSAT" : "UNKNOWN";
  return <span className={`status-badge ${result}`}>{label}</span>;
}
