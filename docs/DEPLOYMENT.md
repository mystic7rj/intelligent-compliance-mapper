# Deployment

## Docker deployment steps

1. Build the image:

```bash
docker build -t compliance-mapper:latest .
```

2. Run CLI help from container:

```bash
docker run --rm compliance-mapper:latest
```

3. Run with mounted data and output directories:

```bash
docker run --rm -v "$(pwd)/data:/app/data" -v "$(pwd)/output:/app/output" compliance-mapper:latest python -m src.api.cli framework list
```

4. Use Docker Compose:

```bash
docker compose run --rm compliance-mapper python -m src.api.cli --help
```

## Environment variables reference

- `DATABASE_URL`: SQLAlchemy database URL.
- `APP_ENV`: Runtime mode (`development`, `production`).
- Any additional tool-specific variables from `.env` as needed by integrations.

## Production checklist

- Use non-root container runtime user (`appuser`).
- Never bake secrets into container image or repository.
- Ensure `.env` is excluded via `.dockerignore`.
- Enforce CI coverage gate (`--cov-fail-under=85`).
- Enforce static security scans (Bandit and Safety).
- Keep dependency versions updated and patched.
- Rotate and protect credentials in secret manager.
- Verify output/data volume permissions are least-privilege.
