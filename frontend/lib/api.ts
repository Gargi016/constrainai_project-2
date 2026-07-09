import {
  CheckResponse,
  Constraint,
  RepairsResponse,
  TurnResponse,
} from "./types";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL?.replace(/\/$/, "") || "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      // ignore -- keep statusText
    }
    throw new Error(`${res.status} ${detail}`);
  }
  return res.json();
}

export const api = {
  postTurn(conversationId: string, text: string): Promise<TurnResponse> {
    return request(`/conversations/${encodeURIComponent(conversationId)}/turns`, {
      method: "POST",
      body: JSON.stringify({ text }),
    });
  },

  getConstraints(
    conversationId: string,
    status: "active" | "all" | "superseded" | "retracted" = "active"
  ): Promise<Constraint[]> {
    return request(
      `/conversations/${encodeURIComponent(conversationId)}/constraints?status=${status}`
    );
  },

  getCheck(conversationId: string): Promise<CheckResponse> {
    return request(`/conversations/${encodeURIComponent(conversationId)}/check`);
  },

  getRepairs(conversationId: string): Promise<RepairsResponse> {
    return request(`/conversations/${encodeURIComponent(conversationId)}/repairs`);
  },

  retractConstraint(
    conversationId: string,
    constraintId: string
  ): Promise<{ retracted_constraint_id: string; active_constraint_count: number }> {
    return request(
      `/conversations/${encodeURIComponent(conversationId)}/constraints/${encodeURIComponent(
        constraintId
      )}/retract`,
      { method: "POST" }
    );
  },

  addRelation(
    conversationId: string,
    lhsVariables: string[],
    operator: "<=" | ">=",
    rhsVariables: string[]
  ): Promise<{ constraint: unknown; sat_status: { result: string } }> {
    return request(
      `/conversations/${encodeURIComponent(conversationId)}/constraints/relation`,
      {
        method: "POST",
        body: JSON.stringify({
          lhs_variables: lhsVariables,
          operator,
          rhs_variables: rhsVariables,
        }),
      }
    );
  },

  listConversations(): Promise<{ conversation_ids: string[] }> {
    return request(`/conversations`);
  },

  deleteConversation(conversationId: string): Promise<{ deleted: string }> {
    return request(`/conversations/${encodeURIComponent(conversationId)}`, {
      method: "DELETE",
    });
  },
};
