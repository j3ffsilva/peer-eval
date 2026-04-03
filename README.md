# Peer-Eval: Contribution Factor Model v3.0

Automated evaluation of student contributions in collaborative projects using GitLab merge requests, code analysis, and survival metrics.

## Features

- 🔗 **Real GitLab Integration**: Collects data directly from GitLab.com or self-hosted instances
- 📊 **Quantitative Metrics**: Analyzes effort (X), survival (S), and CI quality (Q)
- 👥 **Auto-Member Detection**: Automatically extracts contributors from MR authors and reviewers
- 📁 **Repository Organization**: Organizes output by project for multi-repo evaluation
- 🔄 **Fixture Support**: Cycle 1 mode with fixture-based evaluation for validation
- 🚀 **CLI Tool**: Easy-to-use command-line interface

## Installation

### From Source (Development)

```bash
git clone https://github.com/inteli-perf-eng/peer-eval.git
cd peer-eval

# Install in development mode
pip install -e .
```

### From PyPI (When Published)

```bash
pip install peer-eval
```

## Quick Start

### Step 1: Configure `.env`

Copy the template and fill in your GitLab credentials:

```bash
cp .env.example .env
```

Edit `.env` with your values:

```dotenv
GITLAB_URL=https://git.inteli.edu.br
GITLAB_TOKEN=glpat-your-token-here
GITLAB_PROJECT=namespace/project
REPO_PATH=/path/to/cloned/repo
GITLAB_SSL_VERIFY=true
```

### Step 2: Run Evaluation

```bash
# Evaluate a range of merge requests
peer-eval --since 2026-03-16 \
          --until 2026-03-27 \
          --deadline 2026-03-27T23:59:00Z
```

That's it! Members are auto-extracted and reports are saved to `output/[repo-name]/`.

## Usage

### With Real GitLab Data (Cycle 2)

```bash
peer-eval --since 2026-03-16 \
          --until 2026-03-27 \
          --deadline 2026-03-27T23:59:00Z \
          --output-dir output/
```

Credentials loaded automatically from `.env`.

### With Fixture (Cycle 1)

```bash
peer-eval --fixture fixtures/scenarios/set1_s1_so_review.json \
          --deadline 2026-03-27T23:59:00Z
```

### Override Member List

If you need to specify members instead of auto-extraction:

```bash
peer-eval --since 2026-03-16 \
          --until 2026-03-27 \
          --members alice bob charlie \
          --deadline 2026-03-27T23:59:00Z
```

### Advanced Options

```bash
peer-eval --help
```

## Output

Reports are saved to `output/[repo-name]/`:

- `mr_artifacts.json` — Collected MR data with quantitative metrics
- `mr_llm_estimates.json` — LLM component estimates (Cycle 2+)
- `full_report.json` — Complete evaluation report
- Terminal summary table with scores per member

## Architecture

### Cycles

- **Cycle 1**: Fixture-based validation with heuristic models
- **Cycle 2**: Real GitLab data collection with survival analysis
- **Cycle 3**: LLM-powered quality estimation (future)

### Stages

1. **Stage 0**: Load artifacts (fixture or GitLab)
2. **Stage 1**: Extract quantitative metrics
3. **Stage 2a**: LLM component estimation
4. **Stage 2b**: Cross-MR pattern detection
5. **Stage 3**: Compute per-member scores
6. **Stage 4**: Generate reports

## Configuration

### Environment Variables

```dotenv
# GitLab Instance
GITLAB_URL=https://gitlab.com

# Credentials
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
GITLAB_PROJECT=namespace/project

# Local Repository
REPO_PATH=/absolute/path/to/repo

# SSL (for self-signed certificates)
GITLAB_SSL_VERIFY=true  # false to disable
```

### Command-Line Arguments

See `peer-eval --help` for all options.

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

## Troubleshooting

### "SSL: CERTIFICATE_VERIFY_FAILED"

For self-hosted GitLab with self-signed certificates:

```bash
peer-eval --no-ssl-verify ...
# or in .env
GITLAB_SSL_VERIFY=false
```

### "Project not found"

Check that `GITLAB_PROJECT` is correct (format: `namespace/project` or numeric ID).

### "Repository not found"

Ensure `REPO_PATH` is an absolute path to the cloned repository.

## License

MIT License — see LICENSE file for details.

## Author

Jefferson Silva — [silva.o.jefferson@gmail.com](mailto:silva.o.jefferson@gmail.com)

## Contributing

Contributions welcome! Please fork and submit pull requests.
