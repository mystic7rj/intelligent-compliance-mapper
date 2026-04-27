# API Reference

## CLI command reference

### Root command

- Usage: `python -m src.api.cli [OPTIONS] COMMAND [ARGS]...`
- Options:
  - `--verbose`: Enable debug-level logging.

### `analyze`

- `analyze run`
  - Usage: `python -m src.api.cli analyze run --framework <NAME> --controls <PATH> [--output-format table|json]`
  - Options:
    - `--framework` (required)
    - `--controls` (required path)
    - `--output-format` (optional)
  - Example:
    - `python -m src.api.cli analyze run --framework NIST_CSF --controls data/controls.txt`
  - Expected output:
    - Rich summary panel or JSON payload with gap and risk details.

### `framework`

- `framework list`
  - Usage: `python -m src.api.cli framework list`
  - Expected output:
    - Loaded frameworks table or no-frameworks panel.

- `framework load`
  - Usage: `python -m src.api.cli framework load --path <FRAMEWORK_JSON_PATH>`
  - Expected output:
    - Success panel with framework name, version, and control count.

- `framework show`
  - Usage: `python -m src.api.cli framework show --name <FRAMEWORK>`
  - Expected output:
    - Controls table or framework-not-found panel.

### `report`

- `report generate`
  - Usage: `python -m src.api.cli report generate --framework <NAME> --controls <PATH> --format html|excel|pdf --output-dir <PATH>`
  - Expected output:
    - Success panel containing generated report path.

### `batch`

- `batch run`
  - Usage: `python -m src.api.cli batch run --framework <NAME> --controls <PATH> --format html|excel|pdf --output-dir <PATH>`
- `batch run-all`
  - Usage: `python -m src.api.cli batch run-all --jobs-file <JOBS_JSON_PATH>`
- `batch list-jobs`
  - Usage: `python -m src.api.cli batch list-jobs`
- `batch status`
  - Usage: `python -m src.api.cli batch status --job-id <JOB_ID>`

### `analytics`

- `analytics summary`
  - Usage: `python -m src.api.cli analytics summary --framework <NAME> --controls <PATH>`
- `analytics trend`
  - Usage: `python -m src.api.cli analytics trend --framework <NAME>`
- `analytics top-risks`
  - Usage: `python -m src.api.cli analytics top-risks --framework <NAME> --controls <PATH> --limit <N>`
- `analytics improvement`
  - Usage: `python -m src.api.cli analytics improvement --framework <NAME>`

### `compare`

- `compare frameworks`
  - Usage: `python -m src.api.cli compare frameworks --source <FRAMEWORK> --target <FRAMEWORK> [--output-format table|json]`
- `compare all-pairs`
  - Usage: `python -m src.api.cli compare all-pairs [--output-format table|json]`
- `compare equivalence`
  - Usage: `python -m src.api.cli compare equivalence --source <FRAMEWORK> --target <FRAMEWORK>`

## Core class reference

### `src.core.gap_analyzer.GapAnalyzer`

- Constructor:
  - `GapAnalyzer(repository: FrameworkRepositoryProtocol) -> None`
- Public methods:
  - `analyze(framework_name: str, implemented_control_ids: list[str]) -> GapAnalysisResult`

### `src.core.risk_scorer.RiskScorer`

- Constructor:
  - `RiskScorer() -> None`
- Public methods:
  - `score(gap_result: GapAnalysisResult) -> RiskReport`

### `src.core.analytics.AnalyticsEngine`

- Constructor:
  - `AnalyticsEngine(maturity_model: MaturityModel) -> None`
- Public methods:
  - `summarize(gap_result: GapAnalysisResult, risk_report: RiskReport) -> AnalyticsSummary`
  - `compare_summaries(a: AnalyticsSummary, b: AnalyticsSummary) -> dict[str, float | str]`
  - `top_priority_controls(risk_report: RiskReport, limit: int = 10) -> list[RiskFinding]`

### `src.core.cross_framework_analyzer.CrossFrameworkAnalyzer`

- Constructor:
  - `CrossFrameworkAnalyzer(matcher: ControlMatcher, registry: FrameworkRegistry) -> None`
- Public methods:
  - `analyze(source: str, target: str) -> CrossFrameworkResult`
  - `analyze_all_pairs() -> list[CrossFrameworkResult]`
  - `get_equivalence_map(source: str, target: str) -> dict[str, list[str]]`

### `src.ml.embeddings.EmbeddingGenerator`

- Constructor:
  - `EmbeddingGenerator(config: EmbeddingConfig) -> None`
- Public methods:
  - `generate(texts: list[str]) -> np.ndarray`
  - `generate_single(text: str) -> np.ndarray`
  - `get_embedding_dim() -> int`

### `src.data.database`

- `get_engine(url: str | None = None) -> Engine`
- `get_session(engine: Engine) -> Generator[Session, None, None]`
- `dispose_engine(engine: Engine) -> None`
