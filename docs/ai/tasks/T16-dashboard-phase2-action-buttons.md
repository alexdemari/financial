# Task T16: Dashboard Phase 2 — Action Buttons (disparar `just` commands pelo browser)

**Status:** Planned
**Skill:** add-feature
**Scope:** `src/web/runner.py` (new), `src/web/routers/jobs.py` (new), frontend action buttons
**Effort:** M
**Depends on:** T12 (dashboard Phase 1 running), T13/T14/T15 (all tabs implemented)

---

## Context

The dashboard (T12) is read-only: the user must open a terminal, remember the
correct command, and run it manually to update any data. Phase 2 adds action
buttons that trigger `just` commands directly from the browser.

The backend runs each command as a subprocess, streams its output to a job log,
and reports status (running / done / error) via polling. The frontend shows a
button per action, a spinner while running, and the last run timestamp + exit
status when done.

This is a **local-only trusted environment** — no authentication, no rate
limiting, no sandboxing beyond what the OS provides.

---

## Goal

Add a `POST /api/jobs/{command}` endpoint that spawns a `just` command as a
background subprocess, and a `GET /api/jobs/{job_id}` endpoint that returns
its status and output. The frontend shows action buttons in the dashboard
header and in each relevant tab, with live status feedback.

---

## Outcome spec

When done, the following must be true:

1. The dashboard header shows four primary action buttons:
   - **▶ Atualizar IBKR** → `just ibkr-positions`
   - **▶ Daily** → `just daily`
   - **▶ Relatório LLM** → `just daily-report-llm`
   - **▶ BTG Parse** → `just btg-parse`
2. Each button is disabled while its command is running (no duplicate spawns).
3. While running: button shows spinner + "Rodando…" label.
4. When done: button shows ✓ and the timestamp of last successful run.
5. When failed: button shows ✗ in red; clicking it opens a log modal.
6. `GET /api/jobs/status` returns the current state of all known commands
   (last run time, last exit code, currently running or not).
7. `POST /api/jobs/{command}` spawns the command and returns a `job_id`.
8. `GET /api/jobs/{job_id}` returns `{status, exit_code, output, started_at, ended_at}`.
9. Only one instance of each command runs at a time. A second POST to the
   same command while it is running returns `409 Conflict`.
10. Job output (stdout + stderr merged) is kept in memory for the current
    server session only — not persisted to disk.
11. `POST /api/jobs/ibkr-positions` triggers auto-refresh of all dashboard
    panels 3 seconds after the job completes (frontend polls `/api/jobs/{id}`
    and triggers a data refetch when status changes to `done`).
12. `uv run pytest tests/web/test_runner.py` passes (≥ 6 tests).

---

## Constraints

- **No persistent job store.** Jobs live in an in-memory dict keyed by
  `job_id` (UUID). Server restart clears all job history. This is fine
  for a local dashboard.
- **No job queue.** Each command runs directly via `subprocess.Popen`.
  Concurrency per command is limited to 1 (enforced by the running flag).
- **Allowed commands are hardcoded** in a whitelist — the endpoint does NOT
  accept arbitrary shell strings. This is the only security boundary needed
  for a local tool.
- `just` must be on `PATH` when the FastAPI server starts. The server
  inherits the shell environment from `just web`.
- stdout and stderr are merged (`stderr=subprocess.STDOUT`) into a single
  output string. Max captured output: 50,000 characters (truncate oldest if
  exceeded — circular buffer).
- No WebSocket. Frontend polls `GET /api/jobs/{job_id}` every 2 seconds
  while a job is running. Polling stops when status is `done` or `error`.
- Commands that require IB Gateway (`ibkr-positions`, `ibkr-trades-daily`)
  may fail if Gateway is not running. The error is surfaced via exit code
  and output log — no special handling needed.

---

## Allowed commands whitelist

```python
# src/web/runner.py

ALLOWED_COMMANDS: dict[str, list[str]] = {
    "ibkr-positions":    ["just", "ibkr-positions"],
    "ibkr-trades-daily": ["just", "ibkr-trades-daily"],
    "daily":             ["just", "daily"],
    "daily-report-llm":  ["just", "daily-report-llm"],
    "dividends-ibkr":    ["just", "dividends-ibkr"],
    "btg-parse":         ["just", "btg-parse"],
    "weekly":            ["just", "weekly"],
}

# Human-readable labels for the frontend
COMMAND_LABELS: dict[str, str] = {
    "ibkr-positions":    "Atualizar IBKR",
    "ibkr-trades-daily": "Sync Trades",
    "daily":             "Daily Scanner",
    "daily-report-llm":  "Relatório LLM",
    "dividends-ibkr":    "Dividendos",
    "btg-parse":         "BTG Parse",
    "weekly":            "Backtest Semanal",
}
```

---

## Key design

### `src/web/runner.py`

```python
import subprocess
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

JobStatus = Literal["running", "done", "error"]

@dataclass
class Job:
    job_id: str
    command: str
    status: JobStatus
    started_at: str
    ended_at: str | None = None
    exit_code: int | None = None
    output: str = ""
    _proc: subprocess.Popen | None = field(default=None, repr=False)

# In-memory store: command_name → current Job (one per command)
_jobs: dict[str, Job] = {}
_lock = threading.Lock()


def spawn(command: str) -> Job:
    """
    Spawns a just command as a background subprocess.
    Raises ValueError if command not in whitelist.
    Raises RuntimeError if command is already running.
    """
    if command not in ALLOWED_COMMANDS:
        raise ValueError(f"Command not allowed: {command}")

    with _lock:
        existing = _jobs.get(command)
        if existing and existing.status == "running":
            raise RuntimeError(f"Command already running: {command}")

        job = Job(
            job_id=str(uuid.uuid4()),
            command=command,
            status="running",
            started_at=datetime.now().isoformat(),
        )
        _jobs[command] = job

    def _run():
        try:
            proc = subprocess.Popen(
                ALLOWED_COMMANDS[command],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )
            job._proc = proc
            output_lines = []
            for line in proc.stdout:
                output_lines.append(line)
                if sum(len(l) for l in output_lines) > 50_000:
                    output_lines.pop(0)  # circular: drop oldest
            proc.wait()
            job.output    = "".join(output_lines)
            job.exit_code = proc.returncode
            job.status    = "done" if proc.returncode == 0 else "error"
        except Exception as e:
            job.output    = str(e)
            job.exit_code = -1
            job.status    = "error"
        finally:
            job.ended_at  = datetime.now().isoformat()

    threading.Thread(target=_run, daemon=True).start()
    return job


def get_job(command: str) -> Job | None:
    return _jobs.get(command)


def all_statuses() -> dict[str, dict]:
    return {
        cmd: {
            "job_id":     job.job_id,
            "status":     job.status,
            "started_at": job.started_at,
            "ended_at":   job.ended_at,
            "exit_code":  job.exit_code,
            "label":      COMMAND_LABELS.get(cmd, cmd),
        }
        for cmd, job in _jobs.items()
    }
```

### `src/web/routers/jobs.py`

```python
from fastapi import APIRouter, HTTPException
from web.runner import spawn, get_job, all_statuses, ALLOWED_COMMANDS, COMMAND_LABELS

router = APIRouter(prefix="/api/jobs")

@router.post("/{command}")
def run_command(command: str):
    if command not in ALLOWED_COMMANDS:
        raise HTTPException(404, f"Unknown command: {command}")
    try:
        job = spawn(command)
    except RuntimeError as e:
        raise HTTPException(409, str(e))
    return {"job_id": job.job_id, "command": command, "status": job.status}

@router.get("/status")
def get_all_statuses():
    # Also include commands that have never run (for the button list)
    result = all_statuses()
    for cmd, label in COMMAND_LABELS.items():
        if cmd not in result:
            result[cmd] = {"status": "idle", "label": label, "job_id": None,
                           "started_at": None, "ended_at": None, "exit_code": None}
    return result

@router.get("/{command}")
def get_command_status(command: str):
    job = get_job(command)
    if job is None:
        return {"status": "idle", "command": command}
    return {
        "job_id":     job.job_id,
        "command":    job.command,
        "status":     job.status,
        "started_at": job.started_at,
        "ended_at":   job.ended_at,
        "exit_code":  job.exit_code,
        "output":     job.output,
    }
```

Register in `src/web/server.py`:
```python
from web.routers import jobs
app.include_router(jobs.router)
```

---

## Frontend design

### Action buttons in dashboard header

```jsx
// frontend/src/components/ActionBar.jsx

const PRIMARY_ACTIONS = [
  { command: "ibkr-positions",   label: "▶ Atualizar IBKR",  refreshAll: true },
  { command: "daily",            label: "▶ Daily Scanner",   refreshAll: false },
  { command: "daily-report-llm", label: "▶ Relatório LLM",   refreshAll: false },
  { command: "btg-parse",        label: "▶ BTG Parse",       refreshAll: true  },
];

function ActionButton({ command, label, refreshAll, onComplete }) {
  const [status, setStatus] = useState("idle");
  const [lastRun, setLastRun] = useState(null);
  const [jobId, setJobId] = useState(null);

  const run = async () => {
    const res = await fetch(`/api/jobs/${command}`, { method: "POST" });
    if (res.status === 409) { alert("Já está rodando."); return; }
    const data = await res.json();
    setJobId(data.job_id);
    setStatus("running");
    poll(command);
  };

  const poll = (cmd) => {
    const id = setInterval(async () => {
      const r = await fetch(`/api/jobs/${cmd}`);
      const d = await r.json();
      if (d.status !== "running") {
        clearInterval(id);
        setStatus(d.status);
        setLastRun(d.ended_at);
        if (d.status === "done" && refreshAll) {
          setTimeout(() => onComplete(), 3000); // trigger data refetch
        }
      }
    }, 2000);
  };

  const icon = status === "running" ? "⏳"
             : status === "done"    ? "✓"
             : status === "error"   ? "✗"
             : "";

  return (
    <button
      onClick={run}
      disabled={status === "running"}
      className={`action-btn ${status}`}
      title={lastRun ? `Último: ${new Date(lastRun).toLocaleTimeString()}` : ""}
    >
      {icon} {label}
    </button>
  );
}
```

### Log modal (on error or on demand)

Clicking a failed button (✗) or an "Ver log" link opens a modal with the
full job output (monospace, scrollable, max-height 60vh).

```jsx
function LogModal({ command, onClose }) {
  const [output, setOutput] = useState("");
  useEffect(() => {
    fetch(`/api/jobs/${command}`)
      .then(r => r.json())
      .then(d => setOutput(d.output || "(sem output)"));
  }, [command]);
  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal" onClick={e => e.stopPropagation()}>
        <h3>Log: just {command}</h3>
        <pre className="log-output">{output}</pre>
        <button onClick={onClose}>Fechar</button>
      </div>
    </div>
  );
}
```

### Auto-refresh after job completes

When `ibkr-positions` or `btg-parse` finishes, all dashboard panels
refetch their data automatically (3-second delay to let files settle):

```jsx
// In App.jsx — pass a refresh trigger to all data hooks
const [refreshKey, setRefreshKey] = useState(0);
const triggerRefresh = () => setRefreshKey(k => k + 1);

// Each useApi hook includes refreshKey in its dependency array
useEffect(() => { fetch_(url).then(...) }, [url, refreshKey]);
```

---

## Files to create/modify

```
src/web/runner.py                          ← NEW
src/web/routers/jobs.py                    ← NEW
src/web/server.py                          ← register jobs router
frontend/src/components/ActionBar.jsx      ← NEW
frontend/src/components/LogModal.jsx       ← NEW
frontend/src/App.jsx                       ← add ActionBar, refreshKey pattern
frontend/src/hooks/useApi.js               ← add refreshKey to dependency array
tests/web/test_runner.py                   ← NEW
```

---

## Tests (minimum 6)

```python
# tests/web/test_runner.py

def test_spawn_returns_job_with_running_status()
# spawn("daily") → Job with status="running", job_id set

def test_spawn_unknown_command_raises_value_error()
# spawn("rm -rf /") → ValueError (not in whitelist)

def test_spawn_duplicate_raises_runtime_error(monkeypatch)
# spawn("daily") while already running → RuntimeError

def test_job_completes_with_exit_code(monkeypatch)
# Mock subprocess to exit 0 → job.status="done", exit_code=0

def test_job_error_on_nonzero_exit(monkeypatch)
# Mock subprocess to exit 1 → job.status="error", exit_code=1

def test_all_statuses_includes_idle_commands()
# No jobs run yet → all_statuses() includes all ALLOWED_COMMANDS with status="idle"

# FastAPI integration tests (TestClient)
def test_post_job_returns_job_id(client)
# POST /api/jobs/daily → 200, body has job_id

def test_post_duplicate_job_returns_409(client, monkeypatch)
# POST /api/jobs/daily twice while running → second returns 409

def test_get_status_returns_all_commands(client)
# GET /api/jobs/status → all 7 commands present in response
```

---

## Verification

```bash
# 1. Tests
uv run pytest tests/web/test_runner.py -v

# 2. Start dashboard
just web

# 3. Open http://localhost:8000
# Expected: 4 action buttons visible in header
# (▶ Atualizar IBKR, ▶ Daily Scanner, ▶ Relatório LLM, ▶ BTG Parse)

# 4. Click "▶ Atualizar IBKR" (IB Gateway must be running)
# Expected:
# - Button shows ⏳ "Rodando…" immediately
# - Button disabled (no double-click)
# - After ~30s: button shows ✓ with timestamp
# - Dashboard cards auto-refresh 3s after completion

# 5. Click "▶ Daily Scanner" (no Gateway needed)
# Expected: same flow, ~60s for full data download + scan

# 6. Simulate failure — stop IB Gateway, click "▶ Atualizar IBKR"
# Expected: button shows ✗ in red after timeout
# Click ✗ → log modal shows connection error from ib_insync

# 7. Double-click while running
# Expected: alert "Já está rodando." — no second process spawned

# 8. Verify via API
curl http://localhost:8000/api/jobs/status | python -m json.tool
# Expected: all 7 commands listed, status idle/done/error/running

# 9. Lint
uv run ruff check src/web/runner.py src/web/routers/jobs.py tests/web/test_runner.py
```

---

## Known limitations / follow-up

- **No persistent job history.** Restarting `just web` clears all job
  status. Last-run timestamps are lost. A future enhancement could write
  a `data/web/job_history.jsonl` to persist across restarts.
- **No cancellation.** There is no `DELETE /api/jobs/{command}` to kill a
  running process. If `just daily` hangs, the user must restart the server.
  A `proc.terminate()` endpoint is a future enhancement.
- **No progress reporting.** The output buffer fills as the process runs
  but the frontend only shows output after the job completes (log modal).
  Streaming output via SSE (Server-Sent Events) is a natural Phase 3.
- **`just btg-parse` requires files in `data/btg/uploads/`**. If the
  directory is empty, the command exits with a clear error message that
  surfaces in the log modal.
- **`just daily-report-llm` requires `ANTHROPIC_API_KEY`** in `.env`. If
  missing, the command fails with a clear error. The button shows ✗ and
  the log modal shows the missing key message.
- **WSL2 PATH**: `just` must be accessible from the Python subprocess.
  If `just web` is launched from within WSL2 and `just` is in PATH, this
  works automatically. If it fails, add `which just` output to the
  troubleshooting section of the runbook.
