"use client";

import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { CheckResponse, Constraint, RepairCandidate } from "@/lib/types";
import ChatPanel, { LoggedTurn } from "@/components/ChatPanel";
import ConstraintSidebar from "@/components/ConstraintSidebar";
import ConflictGraph from "@/components/ConflictGraph";
import RepairPanel from "@/components/RepairPanel";
import StatusBadge from "@/components/StatusBadge";
import AddRelationForm from "@/components/AddRelationForm";
import { constraintVariables } from "@/lib/types";

export default function Page() {
  const [conversationId, setConversationId] = useState("default");
  const [log, setLog] = useState<LoggedTurn[]>([]);
  const [constraints, setConstraints] = useState<Constraint[]>([]);
  const [check, setCheck] = useState<CheckResponse | null>(null);
  const [repairs, setRepairs] = useState<RepairCandidate[]>([]);
  const [retracting, setRetracting] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async (convId: string) => {
    try {
      const [activeConstraints, checkResult] = await Promise.all([
        api.getConstraints(convId, "active"),
        api.getCheck(convId),
      ]);
      setConstraints(activeConstraints);
      setCheck(checkResult);

      if (checkResult.result === "unsat") {
        const repairResult = await api.getRepairs(convId);
        setRepairs(repairResult.repairs);
      } else {
        setRepairs([]);
      }
      setError(null);
    } catch (e) {
      setError(
        e instanceof Error
          ? `${e.message} — is the ConstrainAI API running at ${
              process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"
            }?`
          : "Unknown error contacting the API."
      );
    }
  }, []);

  useEffect(() => {
    refresh(conversationId);
    setLog([]);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [conversationId]);

  async function handleTurn(text: string) {
    const result = await api.postTurn(conversationId, text);
    setLog((prev) => [...prev, { text, outcome: result.outcome }]);
    await refresh(conversationId);
  }

  async function handleRetract(constraintId: string) {
    setRetracting(constraintId);
    try {
      await api.retractConstraint(conversationId, constraintId);
      await refresh(conversationId);
    } finally {
      setRetracting(null);
    }
  }

  async function handleAddRelation(lhs: string[], operator: "<=" | ">=", rhs: string[]) {
    await api.addRelation(conversationId, lhs, operator, rhs);
    await refresh(conversationId);
  }

  const knownVariables = Array.from(
    constraints.reduce((set, c) => {
      constraintVariables(c).forEach((v) => set.add(v));
      return set;
    }, new Set<string>())
  ).sort();

  const coreIds = new Set(
    check?.result === "unsat" ? (check.minimal_core || []).map((c) => c.id) : []
  );

  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="app-title">
          ConstrainAI
          <small>minimal conflict isolation &amp; repair</small>
        </div>
        <div className="conversation-select">
          <label htmlFor="conv-id" style={{ fontSize: 12, color: "var(--text-muted)" }}>
            conversation
          </label>
          <input
            id="conv-id"
            value={conversationId}
            onChange={(e) => setConversationId(e.target.value || "default")}
          />
          {check && <StatusBadge result={check.result} />}
        </div>
      </header>

      {error && (
        <div style={{ padding: "10px 24px", color: "var(--accent-unsat)", fontSize: 13 }}>
          {error}
        </div>
      )}

      <div className="app-body">
        <section className="panel">
          <ChatPanel log={log} onSubmit={handleTurn} />
          <div style={{ height: 24 }} />
          <AddRelationForm availableVariables={knownVariables} onSubmit={handleAddRelation} />
        </section>

        <section className="panel">
          <ConstraintSidebar
            constraints={constraints}
            coreIds={coreIds}
            onRetract={handleRetract}
            retracting={retracting}
          />

          <div style={{ height: 24 }} />

          <p className="panel-label">Conflict graph</p>
          <ConflictGraph constraints={constraints} coreIds={coreIds} />

          <div style={{ height: 24 }} />

          <RepairPanel repairs={repairs} />
        </section>
      </div>
    </div>
  );
}
