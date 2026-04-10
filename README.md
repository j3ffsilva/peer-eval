# Peer-Eval: Contribution Factor Model v3.0

Automated evaluation of student contributions in collaborative projects using GitLab merge requests, code analysis, and survival metrics.

## Features

- 🔗 **Real GitLab Integration**: Collects data directly from GitLab.com or self-hosted instances
- 📊 **Quantitative Metrics**: Analyzes effort (X), survival (S), and CI quality (Q)
- 👥 **Auto-Member Detection**: Automatically extracts contributors from MR authors and reviewers
- 📁 **Repository Organization**: Organizes output by project for multi-repo evaluation
- 🔄 **Fixture Support**: Cycle 1 mode with fixture-based evaluation for validation
- 🎯 **Subcommand CLI** (v2.0): Clearer interface with `gitlab`, `github`, `fixture` modes
- ⚙️ **Configuration File**: TOML-based config with `.peer-eval.toml` + environment variables
- 🤖 **LLM Integration**: Anthropic Claude API for advanced evaluation (Cycle 3)

## Installation

### From Source (Development)

```bash
git clone https://github.com/inteli-perf-eng/peer-eval.git
cd peer-eval

# Install in development mode
pip install -e .
```

### Build Wheel (Distribution)

To install outside a virtual environment or share with others without access to the source:

```bash
# Install build tool (once)
pip install build

# Build the wheel
python -m build

# Install from the generated wheel
pip install dist/peer_eval-*.whl
```

The wheel file (`dist/peer_eval-*.whl`) can be copied and installed on any machine with a compatible Python version.

### From PyPI (When Published)

```bash
pip install peer-eval
```

## Quick Start

### Step 1: Initialize Project Configuration

```bash
cd /path/to/your/group/project
peer-eval init
```

This creates `.peer-eval.toml` with default settings for your project.

### Step 2: Configure Credentials (`.peer-eval.env`)

Copy the template and fill in your credentials:

Create `.peer-eval.env`:

```dotenv
GITLAB_URL=https://git.inteli.edu.br
GITLAB_TOKEN=glpat-your-token-here
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxx  # Optional (for LLM modes)
```

### Step 3: Check Environment

Verify your setup:

```bash
peer-eval doctor
```

Output:
```
Peer-Eval Doctor

Environment
  Python: 3.10.0 (CPython)
  Executable: /path/to/venv/bin/python3
  Virtual env: ✓

Package
  peer-eval: 3.0.0

Configuration
  .peer-eval.toml: ✓
  env file: ✓ .peer-eval.env

Credentials
  GITLAB_TOKEN: ✓
  GITHUB_TOKEN: ✗
  ANTHROPIC_API_KEY: ✓
```

### Step 4: Run Evaluation

**Option A: Fixture mode (fastest, no API calls)**

```bash
peer-eval fixture \
  --input fixtures/scenarios/set1_s1_so_review.json \
  --deadline 2024-12-01T23:59:00Z \
  --llm skip
```

**Option B: GitLab mode (collect real data)**

```bash
peer-eval gitlab \
  --project-id 123 \
  --since 2024-09-01T00:00:00Z \
  --until 2024-12-01T23:59:59Z \
  --deadline 2024-12-01T23:59:00Z \
  --llm dry-run
```

Done! Reports are saved to `output/[project-id]/`.

If your project follows a sprint calendar, you can use the configured sprints instead of typing dates manually:

```bash
peer-eval gitlab \
  --project-id 123 \
  --sprints 1,2,3 \
  --llm dry-run
```

---

## Usage

### Main Commands

#### 1. `peer-eval init`

Initialize `.peer-eval.toml` for your project:

```bash
peer-eval init
```

Creates a template configuration file with:
- Project ID (auto-detected from directory name)
- Placeholder for deadlines and date ranges
- Sprint calendar defaults (`start_date`, `length_days`, `count`)
- Provider config sections (GitLab, GitHub)

#### 2. `peer-eval doctor`

Diagnose environment and configuration:

```bash
peer-eval doctor
```

Checks:
- Python version and virtual environment
- Package installation
- Config files found (`.peer-eval.toml`, `.peer-eval.env` or `.env`)
- Credentials available (GITLAB_TOKEN, ANTHROPIC_API_KEY)

#### 3. `peer-eval gitlab`

Collect MRs from GitLab and run evaluation:

```bash
peer-eval gitlab \
  --project-id namespace/project \
  --since 2024-09-01T00:00:00Z \
  --until 2024-12-01T23:59:59Z \
  --deadline 2024-12-01T23:59:00Z \
  --llm dry-run
```

Or use the sprint calendar from `.peer-eval.toml`:

```bash
peer-eval gitlab \
  --project-id namespace/project \
  --sprints 1,2,3 \
  --llm dry-run
```

**Arguments:**

*Required:*
- `--project-id`: GitLab project ID (numeric or `namespace/project`)
- `--deadline`: Project deadline (ISO 8601 format), unless derived from `--sprint` or `--sprints`

*Optional:*
- `--since`: Start date for MR collection (ISO 8601)
- `--until`: End date for MR collection (ISO 8601)
- `--sprint`: Select one sprint from the configured calendar (repeatable)
- `--sprints`: Select multiple sprints from the configured calendar (`1,2,3`)
- `--url`: GitLab instance URL (default: `https://gitlab.com`)
- `--token`: Personal access token (reads GITLAB_TOKEN env if omitted)
- `--repo-path`: Path to cloned repository (default: `.`)
- `--members`: Team member list (auto-extracted if omitted)
- `--output-dir`: Output directory (default: `output`)
- `--llm`: live|dry-run|skip (default: dry-run)
- `--overrides`: Path to professor overrides JSON
- `--skip-stage2b`: Skip cross-MR pattern detection
- `--direct-committers`: Members to zero out
- `--no-ssl-verify`: Disable SSL verification

**Examples:**

Simple (using `.peer-eval.env` or `.env` credentials):
```bash
peer-eval gitlab --project-id 123 --deadline 2024-12-01T23:59:00Z
```

With explicit dates:
```bash
peer-eval gitlab \
  --project-id integration-labs/g03 \
  --since 2024-09-01T00:00:00Z \
  --until 2024-12-01T23:59:59Z \
  --deadline 2024-12-01T23:59:00Z \
  --llm dry-run
```

With LLM (requires ANTHROPIC_API_KEY):
```bash
peer-eval gitlab \
  --project-id 123 \
  --deadline 2024-12-01T23:59:00Z \
  --llm live
```

With sprint calendar from `.peer-eval.toml`:
```bash
peer-eval gitlab \
  --project-id 123 \
  --sprint 4 \
  --llm dry-run
```

#### 4. `peer-eval fixture`

Evaluate using a local JSON fixture (no API calls):

```bash
peer-eval fixture \
  --input fixtures/scenarios/scenario1.json \
  --deadline 2024-12-01T23:59:00Z \
  --llm skip
```

**Arguments:**

*Required:*
- `--input`: Path to MR artifacts JSON file
- `--deadline`: Project deadline (ISO 8601), unless derived from `--sprint` or `--sprints`

*Optional:*
- `--members`: Team member list (auto-extracted if omitted)
- `--output-dir`: Output directory (default: `output`)
- `--llm`: live|dry-run|skip (default: dry-run)
- `--sprint`: Use the deadline of one configured sprint
- `--sprints`: Use the deadline of the last configured sprint in a list
- `--overrides`: Path to professor overrides JSON
- `--skip-stage2b`: Skip cross-MR pattern detection

**Examples:**

Basic fixture evaluation:
```bash
peer-eval fixture \
  --input fixtures/mr_artifacts.json \
  --deadline 2024-12-01T23:59:00Z
```

With teams and LLM:
```bash
peer-eval fixture \
  --input fixtures/scenario1.json \
  --deadline 2024-12-01T23:59:00Z \
  --members alice bob charlie \
  --llm dry-run
```

Using the configured sprint deadline:
```bash
peer-eval fixture \
  --input fixtures/scenario1.json \
  --sprint 5 \
  --llm skip
```

#### 5. `peer-eval github`

Collect PRs from GitHub (not yet implemented):

```bash
peer-eval github --repo org/repo --deadline 2024-12-01T23:59:00Z
```

Currently returns error. Use `gitlab` or `fixture` for now.

---

## LLM Modes

All evaluation commands support three LLM modes via `--llm`:

| Mode | Description | Speed | API Cost | Use Case |
|------|-------------|-------|----------|----------|
| `skip` | No LLM evaluation | Fast ⚡ | $0 | Quick tests, pure quantitative |
| `dry-run` | Mock estimates (heuristics) | Fast ⚡ | $0 | Development, default |
| `live` | Real Anthropic Claude API | Slow | $ | Production evaluation |

**Example comparing modes:**

```bash
# Fast mock (default)
peer-eval gitlab --project-id 123 --deadline ... --llm dry-run

# No LLM (quantitative only)
peer-eval gitlab --project-id 123 --deadline ... --llm skip

# Real API (requires ANTHROPIC_API_KEY)
peer-eval gitlab --project-id 123 --deadline ... --llm live
```

---

## Configuration

### `.peer-eval.toml` (Project Config)

Generated by `peer-eval init`. Customize for your project:

```toml
[project]
id = "G03"
repo_path = "."

[evaluation]
deadline = "2024-12-01T23:59:00Z"
since = "2024-09-01T00:00:00Z"
until = "2024-12-01T23:59:59Z"

[sprints]
start_date = "2024-09-01T00:00:00Z"
length_days = 15
count = 5

[llm]
mode = "dry-run"  # Options: live, dry-run, skip

[provider.gitlab]
url = "https://gitlab.com"
project_id = ""  # Override via --project-id

[provider.github]
url = "https://api.github.com"
repo = ""
```

### `.peer-eval.env` (Secrets)

Store credentials securely. You can also point to another file with `--env-file path/to/file`.

```dotenv
# GitLab
GITLAB_URL=https://git.inteli.edu.br
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx

# GitHub (optional)
GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx

# Anthropic (optional, for LLM modes)
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxxxxxx
```

### Configuration Precedence

Values are loaded in this order (later overrides earlier):

1. **CLI arguments** (highest priority)
   ```bash
   peer-eval gitlab --project-id 123 --deadline ...
   ```

2. **`.peer-eval.toml`** configuration file
   ```toml
   [evaluation]
   deadline = "2024-12-01T23:59:00Z"
   ```

3. **Environment variables** (`.peer-eval.env`, `.env`, or `--env-file`)
   ```dotenv
   GITLAB_TOKEN=...
   ANTHROPIC_API_KEY=...
   ```

4. **Hardcoded defaults** (lowest priority)
   - `--url`: https://gitlab.com
   - `--repo-path`: .
   - `--llm`: dry-run

**Example:** If you set `deadline` in both CLI and `.peer-eval.toml`, CLI wins:

```bash
# Uses CLI value (2024-12-01, overriding .toml)
peer-eval gitlab --project-id 123 --deadline 2024-12-01T23:59:00Z
```

---

## Output

Reports are saved to `output/[project-id]/`:

```
output/
├── mr_artifacts.json        # Collected MR data with quantitative metrics
├── mr_llm_estimates.json    # LLM component estimates (E, A, T_review, P)
├── group_report.json        # Cross-MR pattern analysis (Stage 2b)
├── full_report.json         # Complete evaluation report
└── cache/                   # LLM response cache (to avoid duplicate API calls)
```

**Terminal output:**

```
Stage 1: Quantitative metrics
Stage 2a: LLM component estimation
Stage 2b: Cross-MR pattern detection
Stage 3: Aggregate scores per member
Stage 4: Generate reports

╒════════════════╤═════════════╕
│ Member         │ Score       │
├════════════════╼═════════════┤
│ alice          │ 4.2 (A)     │
│ bob            │ 3.8 (B+)    │
│ charlie        │ 3.5 (B)     │
╘════════════════╧═════════════╛

Reports generated in output/123/
```

---

## Architecture

### Cycles

- **Cycle 1**: Fixture-based validation with heuristic models
- **Cycle 2**: Real GitLab data collection with survival analysis
- **Cycle 3**: LLM-powered quality estimation (Anthropic Claude API)

### Pipeline Stages

1. **Stage 0**: Load artifacts (from GitLab API, GitHub API, or JSON fixture)
2. **Stage 1**: Extract quantitative metrics (X, S, Q)
3. **Stage 2a**: LLM component estimation (E, A, T_review, P) — *optional*
4. **Stage 2b**: Cross-MR pattern detection (fragmentation, burst, padding) — *optional*
5. **Stage 3**: Compute per-member scores (attribution + weighting)
6. **Stage 4**: Generate reports (JSON + console summary)

---

## Migration from v1.x to v2.0

The CLI was redesigned in v2.0 for clarity and extensibility.

**Old syntax (v1.x):**

```bash
# GitLab mode
peer-eval --since 2024-09-01 --until 2024-12-01 \
          --deadline 2024-12-01T23:59:00Z \
          --llm dry-run

# Fixture mode
peer-eval --fixture fixtures/g03.json \
          --deadline 2024-12-01T23:59:00Z \
          --skip-llm
```

**New syntax (v2.0):**

```bash
# GitLab mode
peer-eval gitlab \
  --project-id 123 \
  --since 2024-09-01T00:00:00Z \
  --until 2024-12-01T23:59:59Z \
  --deadline 2024-12-01T23:59:00Z \
  --llm dry-run

# Fixture mode
peer-eval fixture \
  --input fixtures/g03.json \
  --deadline 2024-12-01T23:59:00Z \
  --llm skip
```

**Key differences:**

| Feature | v1.x | v2.0 |
|---------|------|------|
| Data source | Flags (`--fixture`, `--since`) | Subcommands (`gitlab`, `fixture`) |
| LLM control | Two flags (`--dry-run-llm`, `--skip-llm`) | One enum (`--llm live\|dry-run\|skip`) |
| Configuration | CLI + .env only | CLI + .toml + `.peer-eval.env` |
| Error messages | Generic | Mode-specific |
| Help | Single page | Per-subcommand |

---

## Examples

### Real-World Scenario: Evaluate Group G03

```bash
# 1. Navigate to project directory
cd ~/artefatos/es05-2026/G03

# 2. Initialize config
peer-eval init

# 3. Check environment
peer-eval doctor

# 4. Run with fixtures first (fast)
peer-eval fixture \
  --input ~/peer-eval/fixtures/mr_artifacts.json \
  --deadline 2024-12-01T23:59:00Z \
  --llm skip

# 5. Run with real GitLab data
peer-eval gitlab \
  --project-id integration-labs/g03 \
  --since 2024-09-01T00:00:00Z \
  --until 2024-12-01T23:59:59Z \
  --deadline 2024-12-01T23:59:00Z \
  --llm dry-run

# 6. View results
cat output/integration-labs-g03/full_report.json | jq .
```

### Advanced: Using LLM with Overrides

```bash
peer-eval gitlab \
  --project-id 123 \
  --deadline 2024-12-01T23:59:00Z \
  --llm live \
  --overrides professor_overrides.json \
  --skip-stage2b \
  --direct-committers alice bob
```

### Batch Evaluation Script

```bash
#!/bin/bash
for group in G01 G02 G03 G04 G05; do
  cd ~/artefatos/$group
  echo "Evaluating $group..."
  peer-eval gitlab \
    --project-id $group \
    --since 2024-09-01T00:00:00Z \
    --until 2024-12-01T23:59:59Z \
    --deadline 2024-12-01T23:59:00Z \
    --llm dry-run
done
```

---

## Development

### Install Development Dependencies

```bash
pip install -e ".[dev]"
```

### Run Tests

```bash
pytest
```

### Run Tests with Coverage

```bash
pytest --cov=peer_eval --cov-report=html
```

---

## Troubleshooting

### "ImportError: cannot import name 'cli'"

Reinstall the package:

```bash
pip install -e . --no-deps --force-reinstall
```

### "Module not found: anthropic" (for LLM modes)

Install dependencies:

```bash
pip install anthropic docstring_parser
```

### "SSL: CERTIFICATE_VERIFY_FAILED"

For self-hosted GitLab with self-signed certificates:

```bash
peer-eval gitlab --no-ssl-verify --project-id ... --deadline ...
```

Or in `.peer-eval.toml`:

```toml
[provider.gitlab]
ssl_verify = false
```

### "GitLab token not found"

Ensure `GITLAB_TOKEN` is set:

```bash
echo $GITLAB_TOKEN
# If empty:
export GITLAB_TOKEN=glpat-your-token
```

Or pass explicitly:

```bash
peer-eval gitlab --project-id 123 --token glpat-xxx --deadline ...
```

### "Virtual environment not detected"

While not required, venv is recommended for isolation:

```bash
python -m venv venv
source venv/bin/activate
pip install -e .
peer-eval doctor  # Should show "Virtual env: ✓"
```

### ".peer-eval.toml not found"

Create it with:

```bash
peer-eval init
```

---

## License

MIT License — see LICENSE file for details.

## Author

Jefferson Silva — [silva.o.jefferson@gmail.com](mailto:silva.o.jefferson@gmail.com)

## Contributing

Contributions welcome! Please fork and submit pull requests.
