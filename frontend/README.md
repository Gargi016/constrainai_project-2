# ConstrainAI Frontend

Next.js + TypeScript chat UI for the ConstrainAI reasoning core: a
conversation panel, a live constraint sidebar, a conflict graph
visualization, and solver-verified repair suggestions.

Talks to the FastAPI backend in `../api` over HTTP — this app has **no
solving logic of its own**. It renders exactly what the backend computed
(SAT/UNSAT, the verified subset-minimal conflict core, repair candidates).

## Running it

**1. Start the backend first** (from the project root):

```bash
pip install -r requirements.txt --break-system-packages
uvicorn api.main:app --reload --port 8000
```

**2. Then the frontend:**

```bash
cd frontend
npm install
cp .env.local.example .env.local   # defaults to http://localhost:8000
npm run dev
```

Open http://localhost:3000. Type a planning constraint (e.g. "Budget must
stay under ₹20k") and press Send. Add a few more to trigger a conflict, and
watch the sidebar, graph, and repair panel update.

**Verified in this environment:** `npm install`, `tsc --noEmit`, and
`npm run build` all complete cleanly (real Next.js production build, zero
errors) — see the project's top-level README for details on what else was
verified vs. not (a live `next dev`/`uvicorn` server pair couldn't be kept
running end-to-end inside the sandbox that built this, since background
processes there don't persist between tool calls; the build/type-check
results above are real, though, not simulated).

## Structure

```
app/
  layout.tsx      root layout, metadata
  page.tsx        orchestrator: conversation state, fetches, wires panels together
  globals.css     design tokens + all styling (no CSS framework dependency)
components/
  ChatPanel.tsx          turn input + per-turn outcome log
  ConstraintSidebar.tsx  live constraint list, status-colored, manual retract button
  ConflictGraph.tsx      bipartite variable/constraint "traced circuit" diagram
  RepairPanel.tsx        solver-verified repair candidates
  StatusBadge.tsx        SAT / UNSAT / UNKNOWN badge
lib/
  types.ts        TypeScript mirror of the backend Constraint/Expression IR
  api.ts          typed fetch wrapper for every backend endpoint
```

## Design notes

Token system (see `app/globals.css`):
- **Color**: slate-ink background, parchment text, three semantic accents —
  sage (SAT), brick (UNSAT), amber (load-bearing / conflict-core) — rather
  than a single generic accent color.
- **Type**: monospace as the *display* face (headers, ids, constraint
  expressions), sans as the body face. Inverted from the usual hierarchy
  deliberately, since this tool's actual content is symbolic notation.
  System font stacks only — no external font fetch, so nothing can break in
  an offline or restricted-network environment.
- **Signature element**: the conflict graph renders constraints and
  variables as a literal bipartite circuit (variable "terminals", constraint
  "gates", connecting "wires"), with wires touching the verified
  subset-minimal conflict core drawn in amber. It's a plain hand-computed
  SVG layout (no charting library) so it stays dependency-light.

## Known gaps

- No dedicated UI yet for adding a cross-variable `RELATION` constraint
  directly (only NL-extractable `BOUND` constraints, plus the "before/after"
  scheduling relation pattern, go through the chat input). A form for
  typed-IR constraint entry would be a natural next addition.
- `npm audit` still reports a handful of Next.js 14→advisories tied to
  Server Components / Middleware / Image Optimizer edge cases (see
  `npm audit` output) that this app doesn't exercise (no `next/image`, no
  middleware, no i18n). Left on the 14.2.x line intentionally rather than
  jumping to a Next 16 major version without the chance to fully re-verify
  the App Router surface against it; worth revisiting before any real
  deployment.
- No auth — same caveat as the backend API.
