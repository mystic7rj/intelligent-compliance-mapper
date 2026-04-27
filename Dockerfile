# Use a minimal Python base image to reduce attack surface.
FROM python:3.11-slim

# Disable bytecode writes and force unbuffered output for deterministic logs.
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Set the application working directory inside the container.
WORKDIR /app

# Create a non-root runtime user for least-privilege execution.
RUN useradd --create-home --shell /usr/sbin/nologin appuser

# Copy only dependency manifest first to maximize build cache reuse.
COPY requirements.txt /app/requirements.txt

# Install Python dependencies from pinned requirements.
RUN pip install --no-cache-dir --upgrade pip && pip install --no-cache-dir -r /app/requirements.txt

# Copy only required runtime source directories (excluding tests/secrets by design).
COPY src /app/src
COPY data /app/data
COPY templates /app/templates
COPY pyproject.toml /app/pyproject.toml

# Ensure application files are owned by the non-root runtime user.
RUN chown -R appuser:appuser /app

# Drop privileges for all remaining container operations.
USER appuser

# Run CLI help by default because this image is for command-line usage.
CMD ["python", "-m", "src.api.cli", "--help"]
