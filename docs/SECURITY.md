# Security

## Implemented security controls

- Path traversal prevention:
  - `safe_path()` rejects `..`, null bytes, encoded traversal strings, and unicode slash traversal variants.
- Input and payload validation:
  - Structured validation errors are raised for malformed required JSON payloads.
- SQL injection risk reduction:
  - SQLAlchemy ORM and parameterized SQL usage avoid string-concatenated SQL execution.
- Output sanitization:
  - `sanitize_cell_value()` strips formula injection prefixes (`=`, `+`, `-`, `@`), HTML tags, and null bytes.
  - `sanitize_filename()` strips separators and unsafe characters, allowing only `[A-Za-z0-9._-]`.
- Least privilege in container runtime:
  - Docker image runs as non-root `appuser`.

## Vulnerability reporting

If you discover a vulnerability:

1. Do not disclose it publicly in issues or pull requests.
2. Share a private report with reproduction steps and impact.
3. Include affected version, attack path, and mitigation proposal.
4. Wait for coordinated fix and disclosure guidance.

## Security scan instructions

### Local static scan

```bash
bandit -r src/ -ll
```

### Local dependency scan

```bash
pip install safety
safety check
```

### CI security workflows

- `.github/workflows/security.yml` runs:
  - Bandit on push to `main`
  - Safety on push to `main`
  - Scheduled weekly scan
