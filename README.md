# okapi

Point `okapi` at a git repo, a package inside one, or a single file, and it
uses the [Claude Agent SDK](https://platform.claude.com/docs/en/agent-sdk/overview)
to reverse-engineer the code — reading it, tracing entry points, services,
data models, and workflows — and writes what it learns as a folder of markdown
files conforming to Google's [Open Knowledge Format (OKF v0.1)](https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md).

## Install

### Standalone binary — no Python required (recommended)

Single-file executables for macOS (Apple Silicon + Intel), Windows, and Linux
are attached to every [release](https://github.com/oussamachaabounii/okapi/releases).
They need [Claude Code](https://claude.com/claude-code) installed and logged
in on the machine (or `ANTHROPIC_API_KEY` set) — that's it.

**macOS / Linux:**

```sh
curl -fsSL https://raw.githubusercontent.com/oussamachaabounii/okapi/main/install.sh | sh
```

**Windows (PowerShell):**

```powershell
mkdir -Force "$env:LOCALAPPDATA\okapi" | Out-Null
irm https://github.com/oussamachaabounii/okapi/releases/latest/download/okapi-windows-x64.exe -OutFile "$env:LOCALAPPDATA\okapi\okapi.exe"
# then add $env:LOCALAPPDATA\okapi to your PATH
```

Then from any folder:

```sh
okapi --version
```

**Upgrade:** just run `okapi update` — it detects how okapi was installed
(standalone binary, pipx, or pip), fetches the latest release from GitHub,
and updates itself in place. `okapi update --check` only reports whether a
newer version exists (exit code 3 when one does, handy for scripts).

### Python install (alternative)

With Python 3.10+ and [pipx](https://pipx.pypa.io) — this route is fully
self-contained (the Agent SDK ships a bundled Claude Code runtime, so not
even Claude Code is needed, only a login or API key):

```sh
pipx install git+https://github.com/oussamachaabounii/okapi          # latest
pipx install git+https://github.com/oussamachaabounii/okapi@v0.4.1   # pinned
```

**For development** (from a clone): `pip install -e ".[dev]"`.

## Auth

okapi works out of the box with a **local Claude Code login** — if you already
use the `claude` CLI (subscription or otherwise), there is nothing to
configure; the Agent SDK reuses that session.

To bill through the **Anthropic API** instead, export a key — it takes
precedence over the local login when set:

```sh
export ANTHROPIC_API_KEY=sk-ant-...   # optional; see .env.example
```

`okapi analyze` prints which credential source it detected before running,
and fails fast with setup guidance if it finds neither.

## Usage

```sh
# From inside a repo: analyze it — writes ./okf-knowledge/
cd ~/code/my-service && okapi analyze

# Or point it at a path explicitly
okapi analyze ~/code/my-service

# A single file (the bundle still lands at the repo root)
okapi analyze ~/code/my-service/src/billing.py

# Narrow the scope
okapi analyze ~/code/my-service --focus "the payment flow"

# Exhaustive pass (quick | standard | deep)
okapi analyze ~/code/my-service --depth deep

# Pick the model: an alias (sonnet, opus, haiku) or any full model id
okapi analyze ~/code/my-service --model opus
okapi analyze ~/code/my-service --model claude-sonnet-4-6

# Check a bundle (defaults to ./okf-knowledge)
okapi validate

# Explore it visually — interactive knowledge graph in your browser
okapi visualize --open

# Update okapi itself to the latest release
okapi update
```

Options for `analyze`: `-o/--output` (default `<repo_root>/okf-knowledge` — must
be inside the target repo, the agent's file tools are sandboxed to it),
`--include-tests/--no-include-tests` (default off), `--model` (default
`sonnet` → `claude-sonnet-5`; aliases: `sonnet`, `opus`, `haiku`; anything
else is passed to the SDK as-is).

Exit codes: `0` success, `1` user/config error or agent failure, `2` the bundle
failed OKF validation (offending files are listed; nothing is deleted).

## What the output looks like

```
okf-knowledge/
├── index.md            # entry point: linked sections, no frontmatter
├── log.md              # dated changelog, no frontmatter
├── overview.md         # type: System
├── entrypoints/
│   ├── index.md
│   └── cli.md
├── services/
│   ├── index.md
│   └── billing.md
└── workflows/
    ├── index.md
    └── invoice-lifecycle.md
```

Every concept file has YAML frontmatter in the style of [Google's OKF
examples](https://cloud.google.com/blog/products/data-analytics/how-the-open-knowledge-format-can-improve-data-sharing):
`type` is required (a Title Case category like `Module` or `Entry Point`);
`title`, `description`, `tags`, `resource`, and `timestamp` (ISO 8601) are
always emitted — `resource` points back at the real source path. Bodies are
scannable sections that prefer markdown tables for anything enumerable
(schemas, signatures, CLI options), and relationships are plain markdown
links in the prose. After each run, `okapi analyze` automatically validates
the bundle and prints a pass/fail summary.

## Visualize

`okapi visualize BUNDLE_DIR` renders the whole wiki as **one self-contained
HTML file** (`okf-viewer.html`, no network access needed — ship it with the
bundle):

- an interactive **force-directed knowledge graph** — nodes are concepts,
  colored by type and sized by connectedness; edges are the markdown links
  between them; drag, pan, zoom, click to inspect
- a **searchable sidebar** grouped by concept type, with per-type show/hide
- a **detail panel** rendering each concept's markdown (tables, code blocks)
  plus its metadata, tags, and "links to / linked from" lists — every
  cross-link navigates in-app
- the bundle's root `index.md` as the landing page

Use `-o out.html` to control the output path and `--open` to launch your
browser.

## Extending

- **New concept types** — add an entry to `CONCEPT_TYPES` in
  `src/okapi/okf_schema.py`. It's a flat dict on purpose: the validator only
  warns on unknown types, so nothing else needs touching.
- **Analysis behavior** — tune the prompts in `src/okapi/prompts.py`:
  `build_system_prompt()` encodes the OKF rules, `build_task_prompt()`
  describes a run, `DEPTH_PRESETS` controls scope and turn budgets.
- **Validation rules** — `src/okapi/validator.py`, tested against the
  fixtures in `tests/fixtures/tiny_bundle/`.

## Known limitations (v0.1)

- **Single-pass only** — every run regenerates the bundle from scratch; there
  is no incremental `--update` yet (the prompt builder already accepts an
  `existing_bundle` argument to support it later).
- No MCP server mode yet.
- The validator checks structure and frontmatter, not whether the prose is
  accurate — skim the bundle after a run.

## Development

```sh
pip install -e ".[dev]"
pytest
```
