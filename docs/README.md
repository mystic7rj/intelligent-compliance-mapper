# Compliance Mapper

## Project overview

Compliance Mapper is a Python-based CLI platform for mapping, gap analysis, analytics, reporting, and cross-framework comparison across enterprise compliance frameworks.

## Features

- Framework loading, listing, and inspection commands.
- Gap analysis and risk scoring workflows.
- Analytics summary, trend, top-risk, and improvement reporting.
- Batch report execution with queue status commands.
- Cross-framework semantic comparison and equivalence mapping.
- Security controls for path handling and input sanitization.

## Documentation index

- `docs/README.md`: Overview, setup, and command quick reference.
- `docs/ARCHITECTURE.md`: Layered architecture and dependency mapping.
- `docs/API_REFERENCE.md`: CLI/API command and class reference.
- `docs/SECURITY.md`: Security controls, scanning, and reporting process.
- `docs/DEPLOYMENT.md`: Container deployment and production checklist.

## Quick start

Run these 3 commands from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt && python -m src.api.cli --help
```

## Requirements

- Python 3.11+
- `pip`
- Optional: Docker and Docker Compose for containerized execution

## Installation steps

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
```

## CLI commands and examples

### Global help

```bash
python -m src.api.cli --help
```

### Analyze

```bash
python -m src.api.cli analyze run --framework NIST_CSF --controls data/controls.txt
```

### Framework

```bash
python -m src.api.cli framework list
python -m src.api.cli framework load --path data/frameworks/nist_csf.json
python -m src.api.cli framework show --name NIST_CSF
```

### Report

```bash
python -m src.api.cli report generate --framework NIST_CSF --controls data/controls.txt --format html --output-dir output
```

### Batch

```bash
python -m src.api.cli batch run --framework NIST_CSF --controls data/controls.txt --format html
python -m src.api.cli batch run-all --jobs-file data/jobs.json
python -m src.api.cli batch list-jobs
python -m src.api.cli batch status --job-id <job-id>
```

### Analytics

```bash
python -m src.api.cli analytics summary --framework NIST_CSF --controls data/controls.txt
python -m src.api.cli analytics trend --framework NIST_CSF
python -m src.api.cli analytics top-risks --framework NIST_CSF --controls data/controls.txt --limit 5
python -m src.api.cli analytics improvement --framework NIST_CSF
```

### Compare

```bash
python -m src.api.cli compare frameworks --source nist_csf --target iso_27001
python -m src.api.cli compare all-pairs
python -m src.api.cli compare equivalence --source nist_csf --target soc2
```
