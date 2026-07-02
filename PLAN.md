# Okapi — Build Plan

**Read this whole file before writing code.** It's the spec for a Python CLI
tool. Two source files already exist (`src/okapi/okf_schema.py` and
`src/okapi/prompts.py`) — read them first, they're not placeholders, they're
the agreed-on prompt design. Reuse and extend them rather than rewriting from
scratch unless you find a real problem with them.

## 1. What we're building

`okapi` is a Mac/Linux terminal command. You point it at a target — a git
repo, a package/directory inside one, or a single file — and it uses the
**Claude Agent SDK** to reverse-engineer that code (read it, trace how it
fits together, understand entry points/services/data models/workflows) and
writes the result as a folder of markdown files conforming to Google's
**Open Knowledge Format (OKF v0.1)**.

```
okapi analyze ~/code/my-service
# -> writes ~/code/my-service/okf-knowledge/*.md
```

The person driving this (Oussama) is a senior backend engineer and intends
to keep extending this tool after the first working version ships. Optimize
for a clean, obviously-extensible structure over cleverness.

## 2. Background you need

### Open Knowledge Format (OKF v0.1)
Published by Google Cloud, June 12, 2026. Spec:
https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md

Key rules (also encoded in `prompts.py::build_system_prompt`, keep both in
sync if you change one):
- A **bundle** is a directory tree. Each **concept** is one markdown file.
- Every concept file has a YAML frontmatter block (`---` delimited). The
  only *required* field is `type`. We also always emit `title`,
  `description`, `tags`, `resource` (path back to the real source), and
  `updated`.
- Concept id = file path minus `.md` (e.g. `services/billing.md` →
  `services/billing`).
- `index.md` and `log.md` are reserved filenames at any directory level —
  never used as concept names. `index.md` has no frontmatter, just linked
  sections for progressive disclosure. `log.md` has no frontmatter, just a
  dated changelog.
- Relationships are plain markdown links inside concept body prose, not a
  special field. Links to not-yet-written concepts are valid.
- No fixed directory taxonomy — structure should fit what's actually found.

### Claude Agent SDK (Python)
Docs: https://platform.claude.com/docs/en/agent-sdk/overview
Package: `claude-agent-sdk` (PyPI), needs Python 3.10+.

```python
import asyncio
from claude_agent_sdk import query, ClaudeAgentOptions

async def main():
    async for message in query(
        prompt="...",
        options=ClaudeAgentOptions(
            cwd="/path/to/target",
            allowed_tools=["Read", "Glob", "Grep", "Write", "Bash"],
            permission_mode="acceptEdits",
            system_prompt="...",
            model="claude-sonnet-4-6",
        ),
    ):
        print(message)

asyncio.run(main())
```

- `query()` returns an async iterator of messages: assistant text, tool use,
  tool results, and a final `ResultMessage` (has cost/usage info, capture it).
- The agent's file tools are sandboxed to `cwd` and below by default — this
  is why the output directory must live inside the target path (or a parent
  we explicitly pass as `cwd`), not somewhere arbitrary on disk.
- Auth: `ANTHROPIC_API_KEY` env var. Fail fast with a clear message if unset.

## 3. Repo layout (target state)

```
okapi/
├── pyproject.toml                 # done — console_script entry point "okapi"
├── README.md                      # TODO — install + usage docs
├── .env.example                   # TODO — ANTHROPIC_API_KEY=
├── src/okapi/
│   ├── __init__.py                # done
│   ├── okf_schema.py              # done — concept type vocab, reserved names, layout hint
│   ├── prompts.py                 # done — system + task prompt builders, depth presets
│   ├── agent.py                   # TODO — orchestrates the Agent SDK call
│   ├── cli.py                     # TODO — click CLI, entry point
│   └── validator.py               # TODO — post-hoc OKF conformance checker
└── tests/
    ├── test_validator.py          # TODO
    └── fixtures/
        └── tiny_bundle/           # TODO — a minimal valid + invalid OKF bundle for tests
```

## 4. Component specs

### 4.1 `agent.py`
- `async def run_analysis(target: Path, output_dir: Path, *, depth: str,
  focus: str | None, include_tests: bool, model: str) -> AnalysisResult`
- Resolve `cwd` for the SDK call: if `target` is a file, `cwd` = its parent
  repo root (walk up to find `.git`, fall back to the file's directory);
  if `target` is a directory, `cwd` = that directory (or its repo root).
- `output_dir` must resolve to a path under `cwd` — if the user passes an
  absolute path outside `cwd`, either re-root it or error out with a clear
  message (don't silently fail on a permission error).
- Build prompts via `prompts.build_system_prompt()` and
  `prompts.build_task_prompt(...)`.
- Stream messages through a `rich.console.Console` — show a live status
  line (tool being called, files touched) rather than dumping raw message
  objects. Use `rich.status` or `Progress`, nothing fancy required.
- On the final `ResultMessage`, print a short summary: turns used, concept
  files written (cross-check with `validator.py` after the run), cost if
  available.
- Return a small `AnalysisResult` dataclass (target, output_dir, summary
  text, message count, success bool) — `cli.py` decides how to present it.
- Respect `depth`'s `max_turns` from `prompts.DEPTH_PRESETS` by passing it
  into `ClaudeAgentOptions`.

### 4.2 `cli.py`
Use `click`. Commands:

- `okapi analyze TARGET [OPTIONS]`
  - `TARGET`: path to repo/dir/file (required, must exist).
  - `-o, --output PATH`: default `<repo_root>/okf-knowledge`.
  - `--depth [quick|standard|deep]`: default `standard`.
  - `--focus TEXT`: optional narrower scope, e.g. a module name or
    "the payment flow" — passed straight into the task prompt.
  - `--include-tests / --no-include-tests`: default `--no-include-tests`.
  - `--model TEXT`: default `claude-sonnet-4-6` (verify current default
    model id against docs at build time — don't hardcode blindly).
  - Validates `ANTHROPIC_API_KEY` is set before doing anything else.
  - After the run, auto-invokes the validator on `output_dir` and prints
    a pass/fail summary; on failure, list the offending files but don't
    delete anything.
- `okapi validate BUNDLE_DIR`
  - Runs `validator.py` standalone against an existing OKF bundle
    (useful once bundles get hand-edited or extended later).
- `okapi --version`.
- Exit codes: 0 success, 1 user/config error (bad path, missing API key),
  2 validation failure.

### 4.3 `validator.py`
- `def validate_bundle(path: Path) -> ValidationReport` — walks the tree,
  for every `.md` file not named `index.md`/`log.md`:
  - parse frontmatter with `pyyaml` (`---\n...\n---` block at file start)
  - fail if missing frontmatter entirely
  - fail if missing the required `type` field
  - warn (not fail) if missing recommended fields from
    `okf_schema.RECOMMENDED_FIELDS`
  - fail if a reserved filename (`okf_schema.RESERVED_FILENAMES`) is used
    for a directory-non-index/log file in a way that has frontmatter
    (i.e. someone put concept content into `index.md`)
- Also check: every directory has an `index.md` (warn if not — OKF marks
  this optional, but for this tool's output it should be the norm).
- `ValidationReport`: lists of `errors: list[str]`, `warnings: list[str]`,
  `concept_count: int`. `cli.py` renders this with `rich`.
- Keep parsing dependency-light — don't pull in a full markdown parser,
  just split on the frontmatter delimiter and `yaml.safe_load` the middle.

### 4.4 `README.md`
Cover: what this is (one paragraph, link to OKF spec + Agent SDK docs),
install (`pipx install .` or `pip install -e .` from repo root — this
becomes a real `okapi` command on PATH once installed), required env var,
usage examples (whole repo, single file, `--focus`, `--depth deep`),
what the output looks like (small tree example), how to extend (point at
`okf_schema.py` for adding concept types, `prompts.py` for tuning analysis
behavior), and known limitations (single-pass, no incremental re-run yet —
see Section 6).

## 5. Milestones (do them in order, keep it runnable at each step)

1. **Scaffolding** — repo layout above exists, `pip install -e .` works,
   `okapi --version` runs. (pyproject.toml already supports this.)
2. **Validator first** — build `validator.py` + tests against small
   hand-written fixture bundles (one valid, one with a missing `type`, one
   with content wrongly in `index.md`). This doesn't depend on the SDK or
   API key, so it's the fastest thing to get green and CI-able.
3. **Agent core** — `agent.py` wired to `query()`, tested manually against
   a small local repo (e.g. this very repo) with `--depth quick`.
4. **CLI** — `cli.py` wraps agent + validator with the UX described above.
5. **README + `.env.example`** — so a fresh clone is usable in under 5
   minutes.
6. **Smoke test** — run `okapi analyze` on 2-3 real repos of different
   languages/sizes, confirm the bundle is genuinely useful (not just
   spec-conformant), and open `validator` output looks clean.

## 6. Explicit extension points (don't build now, but don't block them either)

- **Incremental re-runs**: diff against existing `log.md` / concept files
  instead of regenerating the whole bundle — design `agent.py`'s prompt
  builder so a future `--update` flag can pass "existing bundle at X,
  update rather than overwrite" into the task prompt.
- **Visualizer**: Google's reference OKF implementation includes a static
  HTML graph viewer (single self-contained file). A `okapi visualize
  BUNDLE_DIR` command could reuse that pattern later — not in scope now.
- **MCP server mode**: expose `okapi analyze` as an MCP tool so other
  agents (e.g. Claude Code itself, or Claude Desktop) can trigger it.
- **Multi-language concept detection tuning**: `okf_schema.CONCEPT_TYPES`
  is intentionally a flat dict, not an enum, so new types can be added
  without touching validator logic.
- **CI integration**: a GitHub Action that runs `okapi validate` on PRs
  that touch an existing `okf-knowledge/` bundle, to keep it from going
  stale.

None of these need scaffolding today beyond "don't paint yourself into a
corner" — e.g. keep `AnalysisResult` and the task-prompt builder's
signature easy to extend with new optional args.

## 7. Definition of done for v0.1

- `pip install -e .` then `okapi analyze <some real repo>` produces a
  bundle that passes `okapi validate` with zero errors.
- Bundle root has `index.md` and `log.md`.
- At least the entry points, top-level modules, and one workflow are
  documented as distinct, cross-linked concepts.
- Every concept file's `resource` field points at a real path in the
  target repo.
- README lets a stranger get from clone to first bundle in under 5 minutes.
