"use client";

import { FormEvent, useState } from "react";
import { TurnOutcome } from "@/lib/types";

export interface LoggedTurn {
  text: string;
  outcome: TurnOutcome;
}

interface Props {
  log: LoggedTurn[];
  onSubmit: (text: string) => Promise<void>;
  disabled?: boolean;
}

export default function ChatPanel({ log, onSubmit, disabled }: Props) {
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    const trimmed = text.trim();
    if (!trimmed || sending) return;
    setSending(true);
    try {
      await onSubmit(trimmed);
      setText("");
    } finally {
      setSending(false);
    }
  }

  return (
    <div>
      <p className="panel-label">Conversation</p>
      <div className="chat-log">
        {log.length === 0 && (
          <p className="empty-state">
            State a planning constraint, e.g. &ldquo;Budget must stay under
            ₹20k&rdquo;.
          </p>
        )}
        {log.map((turn, i) => (
          <div key={i} className={`chat-turn ${turn.outcome.kind}`}>
            <div className="turn-text">{turn.text}</div>
            <div className="turn-outcome">
              {turn.outcome.kind} — {turn.outcome.message}
            </div>
          </div>
        ))}
      </div>
      <form className="chat-input-row" onSubmit={handleSubmit}>
        <input
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="Type a constraint or revision..."
          disabled={disabled || sending}
          aria-label="New constraint statement"
        />
        <button type="submit" disabled={disabled || sending || !text.trim()}>
          {sending ? "Sending…" : "Send"}
        </button>
      </form>
    </div>
  );
}
