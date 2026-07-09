<div align="center">
  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1200 400" width="100%" style="background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #311042 100%); border-radius: 12px; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;">
    <path d="M0 50 h1200 M0 100 h1200 M0 150 h1200 M0 200 h1200 M0 250 h1200 M0 300 h1200 M0 350 h1200" stroke="rgba(99, 102, 241, 0.05)" stroke-width="1" />
    <path d="M100 0 v400 M200 0 v400 M300 0 v400 M400 0 v400 M500 0 v400 M600 0 v400 M700 0 v400 M800 0 v400 M900 0 v400 M1000 0 v400 M1100 0 v400" stroke="rgba(99, 102, 241, 0.05)" stroke-width="1" />
    
    <circle cx="250" cy="200" r="40" fill="url(#fuzzyGrad)" opacity="0.8" filter="url(#glow)"/>
    <text x="250" y="205" font-size="14" font-weight="bold" fill="#ffffff" text-anchor="middle">"NLP"</text>
    
    <circle cx="950" cy="200" r="40" fill="url(#rigidGrad)" opacity="0.8" filter="url(#glow)"/>
    <text x="950" y="205" font-size="14" font-weight="bold" fill="#ffffff" text-anchor="middle">Z3 SMT</text>
    
    <path d="M 290 200 L 420 200" stroke="url(#lineGrad)" stroke-width="3" stroke-dasharray="8 4" />
    <path d="M 780 200 L 910 200" stroke="url(#lineGrad)" stroke-width="3" />
    
    <rect x="420" y="130" width="360" height="140" rx="16" fill="rgba(15, 23, 42, 0.8)" stroke="#6366f1" stroke-width="2" filter="url(#glow)"/>
    
    <text x="600" y="200" font-size="52" font-weight="900" letter-spacing="4" fill="#ffffff" text-anchor="middle">SYMBOLYNX</text>
    <text x="600" y="235" font-size="14" font-weight="600" letter-spacing="6" fill="#a5b4fc" text-anchor="middle">NEURO-SYMBOLIC CORE</text>
    
    <text x="450" y="165" font-size="12" font-family="monospace" fill="#38bdf8" opacity="0.4">λ text_to_ir()</text>
    <text x="670" y="250" font-size="12" font-family="monospace" fill="#34d399" opacity="0.4">assert SAT == True</text>
    
    <g transform="translate(50, 40)">
      <rect width="110" height="28" rx="14" fill="rgba(52, 211, 153, 0.1)" stroke="#34d399" stroke-width="1"/>
      <circle cx="16" cy="14" r="4" fill="#34d399"/>
      <text x="28" y="19" font-size="11" font-weight="bold" fill="#34d399">PROVABLY SAT</text>
    </g>
    
    <g transform="translate(1020, 40)">
      <rect width="130" height="28" rx="14" fill="rgba(248, 113, 113, 0.1)" stroke="#f87171" stroke-width="1"/>
      <circle cx="16" cy="14" r="4" fill="#f87171"/>
      <text x="28" y="19" font-size="11" font-weight="bold" fill="#f87171">MINIMAL CORE</text>
    </g>

    <defs>
      <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
        <feGaussianBlur stdDeviation="12" result="blur" />
        <feComposite in="SourceGraphic" in2="blur" operator="over" />
      </filter>
      <linearGradient id="fuzzyGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#38bdf8" />
        <stop offset="100%" stop-color="#818cf8" />
      </linearGradient>
      <linearGradient id="rigidGrad" x1="0%" y1="0%" x2="100%" y2="100%">
        <stop offset="0%" stop-color="#ec4899" />
        <stop offset="100%" stop-color="#8b5cf6" />
      </linearGradient>
      <linearGradient id="lineGrad" x1="0%" y1="0%" x2="100%" y2="0%">
        <stop offset="0%" stop-color="#38bdf8" />
        <stop offset="50%" stop-color="#6366f1" />
        <stop offset="100%" stop-color="#ec4899" />
      </linearGradient>
    </defs>
  </svg>
</div>

<br />

# SymboLynx

### Conversational Constraint Solving with Minimal Conflict Isolation and Repair

SymboLynx allows users to state complex planning, budgeting, or scheduling requirements in plain English and receive mathematically verified answers. If the specified constraints are impossible to satisfy, SymboLynx does not guess—it isolates the exact, absolute subset-minimal conflict down to the sentences typed and computes precise, solver-verified mathematical repairs.

Unlike traditional "AI planning" configurations that rely blindly on Large Language Models (LLMs) to reason—a process fundamentally prone to hallucinations—SymboLynx splits the problem in two: a **fuzzy layer** for parsing text and a **rigid layer** for proving the math. 

---

## 🏗️ Architecture & Philosophy

Most conversational systems reason about constraints entirely within the natural language space, treating pattern completion as theorem proving. SymboLynx enforces a strict neuro-symbolic separation of concerns:

1. **Deterministic Extraction:** Natural language is converted into a structured, typed Intermediate Representation (IR) via deterministic pattern matching. If a phrasing is unrecognized, it fails safely and transparently rather than guessing.
2. **Formal Verification Core:** The structured IR is compiled into mathematical terms and fed directly to **Z3** (an SMT Solver used in hardware and compiler verification). Every SAT/UNSAT verdict is a mathematical certainty.
```
Natural language input
      │
      ▼
Deterministic extraction (regex/rules, no LLM)
      │
      ▼
Typed Constraint IR (Pydantic) ──── provenance: turn, source text
      │
      ▼
Constraint Store ──── lifecycle: active / superseded / retracted
      │                          (persisted to SQLite per conversation)
      ▼
Z3 Compiler ──── Expression tree → Z3 arithmetic terms
      │
      ▼
Tracked Solver ──── SAT/UNSAT check
      │
      ├── SAT ──► satisfying model returned
      │
      └── UNSAT ──► raw unsat core (Z3, not guaranteed minimal)
                        │
                        ▼
                   Deletion-based shrinking
                        │
                        ▼
                   Subset-minimal conflict (independently verified)
                        │
                        ▼
                   Z3-optimization repair engine
                   (tightest fix per constraint, verified by re-solving)
```
### Key Technical Pillars

* **Double-Verified Minimality:** Z3's raw `unsat_core` is not guaranteed to be minimal. SymboLynx passes the core through a secondary deletion-based shrinking algorithm to achieve a *subset-minimal* conflict. This boundary is then independently re-verified from scratch to ensure an algorithmic bug never yields a false minimal claim.
* **Optimization-Driven Repairs:** Instead of generating conversational suggestions, the repair engine uses Z3's optimizer to solve a linear program: *holding all other constraints fixed, what is the tightest possible relaxation to this specific bound to restore satisfiability?* The computed delta is then verified by injecting it back into a fresh instance of the solver.
* **Full Audit Trail:** Constraints are never destructively erased. Retractions and revisions update a constraint's lifecycle state (`active`, `superseded`, `retracted`) inside an immutable-history store, tracking provenance back to the precise conversation turn.

---

## 📂 Project Structure

The repository is structured around a decoupled, pure-Python reasoning core with zero web framework dependencies:

```text
constrainai/          # Core reasoning engine (SymboLynx Core)
  ├── expressions.py  # Typed arithmetic expression trees (Var, Const, Sum, Diff)
  ├── constraints.py  # Constraint IR: schemas, provenance, hardness, and status
  ├── store.py        # In-memory constraint store and lifecycle state transitions
  ├── compiler.py     # Translation layer: Expression/Constraint IR -> Z3 terms
  ├── solver.py       # Tracked SAT/UNSAT checking management
  ├── unsat_core.py   # Raw Z3 UNSAT core extraction 
  ├── shrink.py       # Deletion-based subset-minimal core shrinking + verification
  ├── repair.py       # Z3-optimization-based, solver-verified repair calculations
  ├── extraction.py   # Deterministic natural language parsing rules
  └── persistence.py  # SQLite storage manager using SQLAlchemy
api/                  # FastAPI production service layer
frontend/             # Next.js SPA UI (Chat interface, constraint sidebar, conflict graph)
evaluation/           # Evaluation harness for precision, recall, and accuracy metrics
tests/                # 82 automated integration tests (Zero mocks; real Z3 & DB paths)
demo.py               # E2E Command-line interactive walkthrough
```
## Tech stack
 
| Layer | Technology |
|---|---|
| Constraint IR | Python, Pydantic |
| Solving | Z3 (SMT solver) |
| API | FastAPI |
| Persistence | SQLite via SQLAlchemy |
| Frontend | Next.js, TypeScript, React |
| Testing | pytest (82 tests), Next.js production build |

## Running it
 
**Backend:**
```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 -m pytest                  # 82 tests
uvicorn api.main:app --reload --port 8000
```
 
**Frontend** (separate terminal):
```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev
```
Open `http://localhost:3000`.
 
**CLI demo** (no server needed):
```bash
python3 demo.py
```
 
**Evaluation harness:**
```bash
python3 -m evaluation.runner
```
## Example walkthrough
 
State four constraints in the chat:
```
Budget must stay under ₹20k
GPU costs at least ₹14k
RAM costs at least ₹8k
Reserve ₹2k for storage
```
Then tie them together with the relation form (`gpu_cost, ram_cost,
storage_cost` ≤ `budget`). The system detects UNSAT, identifies that all
five statements are jointly necessary for the conflict (removing any one
resolves it), and proposes four independently-verified repairs — each
closing the same ₹4,000 shortfall from a different direction.
 
Retract the RAM requirement ("Ignore my previous RAM requirement") or
revise the budget upward ("Actually increase budget to ₹27k") and the
system re-solves to SAT, live.
 
## Evaluation results
 
Run against 23 extraction turns and 6 conflict scenarios spanning
budgeting, scheduling, and hardware-configuration domains:
 
| Metric | Result |
|---|---|
| Extraction precision / recall | 100% / 100% |
| SAT/UNSAT accuracy | 100% |
| Exact conflict-set match rate | 100% |
| Repair validity (solver-verified) | 100% |
| Solver latency @ 500 constraints | ~57ms |

 ## License
 
MIT.
 
