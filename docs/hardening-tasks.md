# Hardening and quality task specifications

These are independent implementation tasks drawn from an evidence-based review of the
repository. Each task is self-contained: it states why it is needed (with concrete files,
line numbers, and numbers), the files and scope to change, verifiable acceptance criteria,
and the guardrails that must not be broken.

Each task is one pull request. Keep the recommended order unless a task is blocked.

- These tasks respect the existing direction in [`ROADMAP.md`](../ROADMAP.md),
  [`CONTRIBUTING.md`](../CONTRIBUTING.md), [`SAFETY.md`](../SAFETY.md), and
  [`README.md`](../README.md). Do not introduce changes that contradict those documents.
- TOGGLE is intentionally non-idempotent and is intentionally never retried
  (`src/transport.rs:168-183`, `server/sessions.py`). Do not change that contract.
- Do not rewrite git history. Do not force-push shared branches.
- Follow the pre-PR checklist in [`CONTRIBUTING.md`](../CONTRIBUTING.md) for every task.

## Recommended order

Start with the lower-risk test and tooling tasks so later behavioral changes land with a
safety net, then do the behavioral fixes that need hardware validation.

1. Task 3 — Bring `client/gui.py` and `server/main.py` logic under type and coverage checks.
2. Task 4 — Add a non-blocking Rust coverage report in CI.
3. Task 5 — Make command UTF-8 decoding explicit on the Pico.
4. Task 2 — Report partial results for multi-channel `operate`.
5. Task 1 — Remove head-of-line blocking in the Pico accept loop.
6. Task 6 — Revisit per-record `sync_data()` in the journal (only if measured).

---

## Task 1 — Remove head-of-line blocking in the Pico accept loop

**Labels:** `pico`, `protocol`, `safety`

### Background

`server/main.py:302-337` (`WifiServer.poll`) accepts up to 8 connections per cooperative
loop pass, but handles each connection **serially and synchronously**. `_readline`
(`server/main.py:339-368`) holds a single connection for up to
`COMMAND_READ_TIMEOUT_MS = 1000` ms (`server/settings.py:5`). A client that connects and
sends nothing occupies the only accept slot for up to 1 second; up to 8 such clients per
pass can stall the accept loop for roughly 8 seconds of wall time. The servo and LED state
machines keep ticking during the wait (`server/main.py:349-357`), but no other TCP client
is serviced in that window. There is no total wall-clock budget across the 8 iterations and
no connection-rate limit.

The existing test `test_incomplete_continuous_request_hits_deadline_without_acting`
(`tests/test_main_protocol.py`) confirms the 1000 ms per-connection cut, but no test covers
multiple contending clients. This matters for the multi-user channel sessions targeted by
`ROADMAP.md` v0.4.0 and for keeping Close/Stop safety actions responsive.

### Files and scope

- `server/main.py` — `WifiServer.poll` and `_readline` only. Keep the single cooperative
  loop (no threads, no asyncio).
- `server/settings.py` — only if a new tunable constant is introduced; document it inline.
- `tests/test_main_protocol.py` — add coverage for the contended case.

Out of scope: the session/ownership model, the servo scheduler, the discovery responder.

### Approach (non-prescriptive)

Reduce the time a single idle or slow peer can hold the accept loop. Options to evaluate:
a short initial-data timeout that returns the connection to the loop quickly, a total
per-`poll` wall-clock budget across the 8 iterations, or both. The chosen approach must
preserve the existing one-command-per-connection, newline-framed protocol and the existing
8192-byte buffer cap (`server/main.py:339`).

### Acceptance criteria

- A single peer that connects and never sends a newline cannot delay servicing of a second,
  well-behaved peer by more than a small, documented bound (state the bound; it must be well
  under the current ~1 s per idle peer and must not grow with the number of idle peers).
- Servo and LED ticks continue during any wait (existing behavior preserved).
- A new test in `tests/test_main_protocol.py` demonstrates that an idle/slow client does not
  starve a concurrent well-behaved client, using the existing `ast`/`exec` fake-socket
  harness.
- `test_incomplete_continuous_request_hits_deadline_without_acting` still passes.
- All pre-PR checks in `CONTRIBUTING.md` pass.

### Guardrails

- Keep the Pico on MicroPython and keep the single cooperative loop (`ROADMAP.md` v0.3.0:
  "Keep the Pico W on MicroPython").
- Do not change the TCP command protocol wire format or the one-command-per-connection
  contract; the Rust and Python clients depend on it (`src/transport.rs`,
  `client/transport.py`).
- Must not delay or drop Close/Stop safety actions (`SAFETY.md`, `README.md` journal
  section).
- Requires an on-device smoke test per `CONTRIBUTING.md` ("If the change affects servo motion
  or Wi-Fi startup, include the hardware used and the smallest test performed"); state the
  hardware and smallest test in the PR.

---

## Task 2 — Report partial results for multi-channel `operate`

**Labels:** `pico`, `protocol`, `safety`

### Background

`server/main.py:448-459` (`_session_operate`) iterates the requested channels and returns
`False` on the first servo that fails:

```python
for channel in channels:
    ...
    if not ok:
        return False
```

Earlier channels in the list have already been commanded to move before the failure. The
"validate ownership before moving anything" guarantee in `server/sessions.py` (`operate`)
covers **ownership**, not servo success. So a multi-channel `operate` that fails partway
returns an all-or-nothing failure (`{"ok": false, ...}`) while leaving channels in mixed
physical states. The operation journal records outcomes as `accepted`/`unresolved`
(`README.md`, "Operation journal"), so an inaccurate all-failed signal degrades provenance,
which conflicts with the safety-first stance in `CONTRIBUTING.md`.

### Files and scope

- `server/main.py` — `_session_operate` and the `SESSION` reply assembly in `_handle`.
- `server/sessions.py` — only if the response shape for `operate` must carry per-channel
  results; keep ownership validation unchanged.
- Client consumers of the response: `src/transport.rs` (`operate_many`, session reply
  handling around `transport.rs:168-232`) and `client/transport.py` — update parsing only if
  the response shape changes.
- Tests: `tests/test_main_protocol.py`, and the relevant Rust tests in `src/transport.rs`.

### Acceptance criteria

- When a multi-channel `operate` partially fails, the response distinguishes which channels
  were commanded successfully from which failed (exact shape decided in the PR and documented
  in `docs/specification.md`).
- The GUI/journal can record the accurate per-channel outcome rather than a single
  all-failed flag.
- Full servo atomicity is **not** required (it is not achievable for independent servos); the
  requirement is accurate reporting of partial success.
- New/updated tests cover a partial-failure case on the server and the client parsing of the
  new shape.
- `docs/specification.md` is updated to describe the response shape.
- All pre-PR checks pass.

### Guardrails

- Do not change the TOGGLE contract.
- Any wire-format change to the `operate` response must stay backward compatible with older
  firmware/clients, or be gated so old firmware still works and displays a safe state
  (`README.md`: "older firmware remains controllable and displays Unknown"). Prefer an
  additive field over a breaking change.
- Must not introduce blocking in the cooperative loop (see Task 1).
- Requires an on-device smoke test per `CONTRIBUTING.md`.

---

## Task 3 — Bring `client/gui.py` and `server/main.py` logic under type and coverage checks

**Labels:** `python:uv`, `maintenance`

### Background

`pyproject.toml:63` lists only four files for `mypy` (`client/protocol.py`,
`client/transport.py`, `client/cli.py`, `bindings/python/kohdalab_shutter.py`); it does
**not** include `client/gui.py` (636 lines). `pyproject.toml:68` also omits
`client/gui.py` and `server/main.py` from the `fail_under = 100` coverage gate. So 636 lines
of GUI logic are checked by neither strict typing nor coverage, and the most
branch-heavy server file (`server/main.py`) is exercised only opportunistically via the
`ast`/`exec` harness in `tests/test_main_protocol.py`. `server/main.py` additionally carries
lint ignores `B905, S104, S110` (`pyproject.toml:49`), meaning silent `except: pass` and
related patterns are tolerated there.

The Python CLI/GUI remain shipped entry points (`[project.scripts]` in `pyproject.toml`), so
regressions in them can pass CI today.

### Files and scope

- `pyproject.toml` — `[tool.mypy] files`, `[tool.coverage.run] omit`, and ruff per-file
  ignores.
- `client/gui.py` — add type annotations as needed to satisfy `mypy` (no behavior changes).
- `server/main.py` — optionally refactor pure logic into importable, testable units so it can
  be brought under coverage without importing MicroPython hardware modules. Behavior must not
  change.
- `tests/` — add tests to reach the coverage bar for any newly included source.

This task may be split into two PRs if the diff is large: (3a) `client/gui.py` typing;
(3b) `server/main.py` coverage. Keep each PR independently green.

### Acceptance criteria

- `client/gui.py` is included in the `mypy` file list and `uv run mypy` passes with
  `strict = true`.
- Coverage enforcement is extended to the newly included source without lowering
  `fail_under` below its current value for the already-covered modules.
- No runtime behavior change in `client/gui.py` or `server/main.py` (typing, refactor, and
  tests only).
- Any relaxed lint ignore removed from `pyproject.toml:49` is justified in the PR, or left in
  place with a one-line rationale.
- All pre-PR checks pass.

### Guardrails

- Pure maintenance: no change to GUI behavior, the protocol, or device ownership.
- Do not reduce existing coverage or typing strictness anywhere.
- Keep Wi-Fi credentials out of Git and keep hardware config in `server/settings.py`
  (`CONTRIBUTING.md`).

---

## Task 4 — Add a non-blocking Rust coverage report in CI

**Labels:** `rust`, `maintenance`

### Background

`.github/workflows/test.yml` runs `cargo fmt`, `cargo clippy`, `cargo test`, and
`cargo build` for the Rust client, but has no coverage measurement (no `tarpaulin`,
`llvm-cov`, or `grcov`). Python enforces `fail_under = 100` (`pyproject.toml`), but Rust has
no equivalent visibility. `src/bin/gui.rs` is a single 5262-line file that holds the
converged GUI + API command path, so untested branches there are currently invisible.

### Files and scope

- `.github/workflows/test.yml` — the `rust` job (or a new job).
- Optionally a small config file for the coverage tool.

Do not add a blocking threshold in this task.

### Acceptance criteria

- CI produces a Rust coverage report (e.g. via `cargo llvm-cov`) and uploads or prints it.
- The step is **non-blocking**: it must not fail the build on low coverage (report only).
- The report covers the workspace, including `src/bin/gui.rs`.
- Pinned, hash-referenced actions consistent with the existing workflow style
  (`.github/workflows/test.yml` pins actions by SHA).
- All existing CI jobs still pass.

### Guardrails

- Do not introduce a coverage gate that could block unrelated PRs; enforcement, if any, is a
  later decision.
- Keep action pinning and `permissions` minimal, matching the current workflow.
- Do not change test behavior or the `required` branch-protection contexts
  (`.github/workflows/test.yml` `required` job).

---

## Task 5 — Make command UTF-8 decoding explicit on the Pico

**Labels:** `pico`, `protocol`

### Background

`server/main.py:365` decodes an incoming command with `bytes(buffer).decode()`, which uses
strict UTF-8 with no error handler. A command containing invalid UTF-8 bytes raises, and the
exception is caught only by the generic handler at `server/main.py:327`, which replies
`ERROR\n`. This does not crash, but it is inconsistent with the clean `UNKNOWN`/`ERR`
replies the protocol returns elsewhere, and the branch is untested because `server/main.py`
is omitted from the coverage gate (`pyproject.toml:68`).

### Files and scope

- `server/main.py` — the decode site in `_readline` only.
- `tests/test_main_protocol.py` — add a test for a command with invalid UTF-8 bytes.

### Acceptance criteria

- A command with invalid UTF-8 bytes produces a defined, consistent protocol reply
  (decide `UNKNOWN` vs `ERR` and document it in `docs/specification.md`), not the generic
  `ERROR\n` fallback.
- A new test asserts the chosen reply for invalid UTF-8 input.
- No change to handling of valid UTF-8 commands, including the existing maximum-Unicode-label
  path already tested.
- All pre-PR checks pass.

### Guardrails

- Keep the one-command-per-connection, newline-framed protocol and the 8192-byte cap.
- Do not change the TOGGLE contract or the session protocol.
- No blocking added to the cooperative loop.

---

## Task 6 — Revisit per-record `sync_data()` in the operation journal (measure first)

**Labels:** `rust`, `enhancement`

### Background

`src/journal.rs:188-193` (`write_entry`) calls `sync_data()` on every journal record. This
is correct for durability and runs on the dedicated writer thread, so the UI thread is not
blocked (`src/journal.rs`). Under high-frequency API operation it is a per-operation fsync,
which may cost throughput. This is a low-priority optimization and the current behavior is
defensible; only pursue it if a measurement shows the fsync is a real bottleneck.

### Files and scope

- `src/journal.rs` — the writer loop and `write_entry`.
- `src/journal.rs` tests.

### Acceptance criteria

- A benchmark or measurement is included showing the per-record fsync is (or is not) a
  bottleneck under a realistic high-frequency workload. If it is not, close the task without a
  behavior change and record the measurement.
- If changed: safety-critical records (Close/Stop and the terminal `session_finished` marker)
  are still synced immediately; only non-safety records may be batched.
- The fail-stop-on-first-I/O-error semantics and the bounded `finish` handshake
  (`JOURNAL_EXIT_ACK_TIMEOUT = 250 ms`) are preserved.
- Existing journal tests still pass; new tests cover any batching boundary.
- All pre-PR checks pass.

### Guardrails

- Must not delay or risk loss of Close/Stop provenance (`README.md`: the journal "never
  delay[s] or prevent[s] Close/Stop safety actions").
- Must not weaken the "stop permanently on the first I/O failure" guarantee
  (`src/journal.rs`).
- Do not change the JSONL record format or field semantics documented in
  `README.md`/`docs/gui-api.md`.
