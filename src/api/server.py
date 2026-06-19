# -*- coding: utf-8 -*-
"""FastAPI server wrapping CLI logic into REST API endpoints.

Provides REST endpoints for compliance analysis, framework management,
and report generation. All business logic is delegated to existing
service classes (GapAnalyzer, RiskScorer, CrossFrameworkAnalyzer, etc.).
"""

from __future__ import annotations

from collections.abc import Generator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from src.core.analytics import AnalyticsSummary, AnalyticsEngine
from src.core.cross_framework_analyzer import CrossFrameworkAnalyzer, CrossFrameworkResult
from src.core.framework_registry import FrameworkRegistry, SUPPORTED_FRAMEWORKS
from src.core.gap_analyzer import GapAnalyzer, GapAnalysisResult
from src.core.maturity_model import MaturityModel
from src.core.risk_scorer import RiskReport, RiskScorer
from src.data.database import get_engine, get_session
from src.data.repositories.framework_repository import FrameworkRepository
from src.data.repositories.control_repository import ControlRepository
from src.ml.control_matcher import ControlMatcher
from src.ml.embeddings import EmbeddingConfig, EmbeddingGenerator
from src.ml.similarity import SimilarityCalculator, SimilarityConfig
from src.reports.html_reporter import HTMLReporter
from src.reports.excel_reporter import ExcelReporter
from src.reports.pdf_reporter import PDFReporter
from src.utils.logger import get_logger
from src.utils.security import safe_path

logger = get_logger(__name__)


# =============================================================================
# Request/Response Models
# =============================================================================


class FrameworkInfo(BaseModel):
    """Information about a loaded framework."""

    name: str
    version: str
    total_controls: int
    loaded_at: datetime


class AnalyzeRequest(BaseModel):
    """Request body for compliance gap analysis."""

    framework: str = Field(..., description="Framework code (NIST_CSF, ISO_27001, CIS_V8, SOC2)")
    controls: list[str] = Field(..., description="List of implemented control IDs")


class AnalyzeResponse(BaseModel):
    """Response from compliance analysis."""

    framework: str
    total_controls: int
    implemented: int
    compliance_pct: float
    risk_level: str
    risk_score: float
    gaps: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime


class CompareRequest(BaseModel):
    """Request body for cross-framework comparison."""

    source: str = Field(..., description="Source framework (NIST_CSF, ISO_27001, CIS_V8, SOC2)")
    target: str = Field(..., description="Target framework (NIST_CSF, ISO_27001, CIS_V8, SOC2)")


class CompareResponse(BaseModel):
    """Response from cross-framework comparison."""

    source: str
    target: str
    total_source_controls: int
    mapped_controls: int
    mapping_percentage: float
    matches: list[dict[str, Any]] = Field(default_factory=list)
    generated_at: datetime


class AnalyticsResponse(BaseModel):
    """Response from analytics summary endpoint."""

    framework: str
    compliance_percentage: float
    risk_score: float
    maturity_level: str
    total_controls: int
    critical_gaps: int
    high_gaps: int
    medium_gaps: int
    low_gaps: int
    generated_at: datetime


class ReportRequest(BaseModel):
    """Request body for report generation."""

    framework: str = Field(..., description="Framework code")
    controls: list[str] = Field(..., description="List of implemented control IDs")
    format: str = Field(default="html", description="Report format (html, pdf, excel)")


class ReportResponse(BaseModel):
    """Response from report generation."""

    filename: str
    format: str
    size_bytes: int
    download_url: str
    generated_at: datetime


# =============================================================================
# FastAPI App Setup
# =============================================================================

app = FastAPI(
    title="Compliance Mapper API",
    description="REST API for compliance framework analysis and gap management",
    version="1.0.0",
)

# NOTE: allow_origins=["*"] with allow_credentials=True is rejected by browsers
# and is a security smell. The dashboard is served from this same origin and sends
# no credentials, so we keep the wildcard but disable credentialed requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup static file serving
static_dir = Path(__file__).parent.parent / "static"
static_dir.mkdir(exist_ok=True)
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def root() -> FileResponse:
    """Serve the main dashboard HTML file."""
    return FileResponse(str(static_dir / "index.html"))


# =============================================================================
# Helper Functions
# =============================================================================


# Create the engine once at import time and reuse its connection pool across
# requests. Creating a new engine per request (as the old code did) leaked a
# fresh connection pool on every call.
_engine = get_engine()


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that yields a DB session and always closes it.

    Using ``get_session`` as a context manager guarantees commit / rollback /
    close, even when the endpoint raises — fixing the per-request session leak.
    """
    with get_session(_engine) as session:
        yield session


def _get_gap_analyzer(session: Session) -> tuple[GapAnalyzer, FrameworkRepository]:
    """Create a gap analyzer bound to the given session."""
    repo = FrameworkRepository(session)
    analyzer = GapAnalyzer(repo)
    return analyzer, repo


def _get_cross_framework_analyzer(session: Session) -> CrossFrameworkAnalyzer:
    """Create a cross-framework analyzer bound to the given session."""
    framework_repo = FrameworkRepository(session)
    control_repo = ControlRepository(session)

    # Initialize ML components
    embedding_gen = EmbeddingGenerator(config=EmbeddingConfig())
    similarity_calc = SimilarityCalculator(config=SimilarityConfig(threshold=0.3, top_k=5))

    # Initialize control matcher
    matcher = ControlMatcher(
        embedding_generator=embedding_gen,
        similarity_calculator=similarity_calc,
        control_repository=control_repo,
        framework_repository=framework_repo,
    )

    registry = FrameworkRegistry(Path("data"))

    return CrossFrameworkAnalyzer(matcher, registry)


def _format_gap_result(gap_result: GapAnalysisResult, risk_report: RiskReport) -> AnalyzeResponse:
    """Convert gap analysis and risk result to API response format."""
    gaps_data = []
    for finding in risk_report.findings:
        gaps_data.append({
            "control_id": finding.control_id,
            "title": finding.control_name,
            "severity": finding.severity,
            "likelihood": finding.likelihood,
            "impact": finding.impact,
            "risk_score": finding.risk_score,
        })

    return AnalyzeResponse(
        framework=gap_result.framework_name,
        total_controls=gap_result.total_controls,
        implemented=gap_result.implemented_count,
        compliance_pct=gap_result.compliance_percentage,
        risk_level=risk_report.overall_risk_level,
        risk_score=risk_report.risk_score,
        gaps=gaps_data,
        generated_at=gap_result.analyzed_at,
    )


# =============================================================================
# API Endpoints
# =============================================================================


@app.get("/api/health")
async def health_check() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": datetime.now(UTC).isoformat()}


@app.get("/api/frameworks", response_model=list[FrameworkInfo])
async def list_frameworks(session: Session = Depends(get_db)) -> list[FrameworkInfo]:
    """
    Get list of all loaded compliance frameworks.

    Returns:
        List of framework information objects with control counts.

    Raises:
        HTTPException: If frameworks cannot be loaded.
    """
    try:
        repo = FrameworkRepository(session)
        frameworks = repo.get_all()

        return [
            FrameworkInfo(
                name=fw.name,
                version=fw.version,
                total_controls=sum(len(f.controls) for f in fw.families),
                loaded_at=fw.created_at or datetime.now(UTC),
            )
            for fw in frameworks
        ]
    except Exception as e:
        logger.error("Failed to list frameworks", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Failed to list frameworks: {str(e)}")


@app.post("/api/analyze", response_model=AnalyzeResponse)
async def analyze_compliance(
    request: AnalyzeRequest, session: Session = Depends(get_db)
) -> AnalyzeResponse:
    """
    Analyze compliance gaps for implemented controls against a framework.

    Args:
        request: Framework code and list of implemented control IDs.

    Returns:
        Compliance analysis with gap details and risk scoring.

    Raises:
        HTTPException: For validation errors (422) or not found (404).
    """
    try:
        analyzer, _ = _get_gap_analyzer(session)

        # Run gap analysis
        gap_result = analyzer.analyze(request.framework, request.controls)

        # Score the gaps
        scorer = RiskScorer()
        risk_report = scorer.score(gap_result)

        logger.info(
            "Compliance analysis completed",
            extra={
                "framework": request.framework,
                "controls_analyzed": len(request.controls),
                "compliance_pct": gap_result.compliance_percentage,
            },
        )

        return _format_gap_result(gap_result, risk_report)

    except ValueError as e:
        logger.warning("Analysis validation error", extra={"error": str(e)})
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Analysis failed", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Analysis failed: {str(e)}")


@app.post("/api/compare", response_model=CompareResponse)
async def compare_frameworks(
    request: CompareRequest, session: Session = Depends(get_db)
) -> CompareResponse:
    """
    Compare two compliance frameworks and identify control mappings.

    Args:
        request: Source and target framework codes.

    Returns:
        Cross-framework mapping results with similarity scores.

    Raises:
        HTTPException: For validation errors (422) or not found (404).
    """
    try:
        analyzer = _get_cross_framework_analyzer(session)

        # Run cross-framework analysis
        result = analyzer.analyze(request.source, request.target)

        # Convert matches to response format
        matches_data = []
        for match in result.matches:
            matches_data.append({
                "source_control_id": match.source_control_id,
                "target_control_id": match.matched_control_id,
                "similarity_score": match.similarity_score,
                "confidence": match.confidence,
            })

        response = CompareResponse(
            source=result.source_framework,
            target=result.target_framework,
            total_source_controls=result.total_source_controls,
            mapped_controls=result.mapped_controls,
            mapping_percentage=result.mapping_percentage,
            matches=matches_data,
            generated_at=result.analyzed_at,
        )

        logger.info(
            "Framework comparison completed",
            extra={
                "source": request.source,
                "target": request.target,
                "matches": len(matches_data),
            },
        )

        return response

    except ValueError as e:
        logger.warning("Comparison validation error", extra={"error": str(e)})
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Comparison failed", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Comparison failed: {str(e)}")


@app.get("/api/analytics/summary", response_model=AnalyticsResponse)
async def get_analytics_summary(
    framework: str = Query(..., description="Framework code"),
    controls: str = Query(..., description="Comma-separated list of control IDs"),
    session: Session = Depends(get_db),
) -> AnalyticsResponse:
    """
    Get analytics summary including maturity level and compliance metrics.

    Args:
        framework: Framework code (NIST_CSF, ISO_27001, CIS_V8, SOC2).
        controls: Comma-separated list of implemented control IDs.

    Returns:
        Analytics summary with compliance percentage, risk score, and maturity level.

    Raises:
        HTTPException: For validation errors or processing failures.
    """
    try:
        control_list = [c.strip() for c in controls.split(",") if c.strip()]

        analyzer, _ = _get_gap_analyzer(session)

        # Run gap analysis
        gap_result = analyzer.analyze(framework, control_list)

        # Score the gaps
        scorer = RiskScorer()
        risk_report = scorer.score(gap_result)

        # Generate analytics summary
        maturity_model = MaturityModel()
        analytics = AnalyticsEngine(maturity_model)
        summary = analytics.summarize(gap_result, risk_report)

        response = AnalyticsResponse(
            framework=summary.framework_name,
            compliance_percentage=summary.compliance_percentage,
            risk_score=summary.risk_score,
            maturity_level=summary.maturity_level,
            total_controls=summary.total_controls,
            critical_gaps=summary.critical_gaps,
            high_gaps=summary.high_gaps,
            medium_gaps=summary.medium_gaps,
            low_gaps=summary.low_gaps,
            generated_at=summary.generated_at,
        )

        logger.info(
            "Analytics summary generated",
            extra={
                "framework": framework,
                "maturity_level": summary.maturity_level,
                "compliance_pct": summary.compliance_percentage,
            },
        )

        return response

    except ValueError as e:
        logger.warning("Analytics validation error", extra={"error": str(e)})
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Analytics summary failed", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Analytics failed: {str(e)}")


@app.post("/api/reports/generate", response_model=ReportResponse)
async def generate_report(
    request: ReportRequest, session: Session = Depends(get_db)
) -> ReportResponse:
    """
    Generate a compliance report in the specified format.

    Args:
        request: Framework code, control list, and report format (html, pdf, excel).

    Returns:
        Report metadata including download URL.

    Raises:
        HTTPException: For validation errors or generation failures.
    """
    try:
        if request.format not in ["html", "pdf", "excel"]:
            raise ValueError(f"Unsupported report format: {request.format}")

        analyzer, _ = _get_gap_analyzer(session)

        # Run gap analysis
        gap_result = analyzer.analyze(request.framework, request.controls)

        # Score the gaps
        scorer = RiskScorer()
        risk_report = scorer.score(gap_result)

        # Generate report file
        output_dir = Path(__file__).parent.parent.parent / "reports"
        output_dir.mkdir(exist_ok=True)

        template_dir = Path(__file__).parent.parent.parent / "templates"

        if request.format == "html":
            reporter = HTMLReporter(template_dir=template_dir)
        elif request.format == "pdf":
            reporter = PDFReporter(template_dir=template_dir)
        else:  # excel
            reporter = ExcelReporter(template_dir=template_dir)

        report_path = reporter.generate(gap_result, risk_report, output_dir)
        filename = report_path.name

        file_size = report_path.stat().st_size if report_path.exists() else 0

        response = ReportResponse(
            filename=filename,
            format=request.format,
            size_bytes=file_size,
            download_url=f"/api/reports/download/{filename}",
            generated_at=datetime.now(UTC),
        )

        logger.info(
            "Report generated",
            extra={
                "framework": request.framework,
                "format": request.format,
                "report_filename": filename,
                "size_bytes": file_size,
            },
        )

        return response

    except ValueError as e:
        logger.warning("Report generation validation error", extra={"error": str(e)})
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error("Report generation failed", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Report generation failed: {str(e)}")


@app.get("/api/reports/download/{filename}")
async def download_report(filename: str) -> FileResponse:
    """
    Download a previously generated report file.

    Args:
        filename: The report filename to download.

    Returns:
        File stream of the report.

    Raises:
        HTTPException: If file not found (404) or access denied (403).
    """
    try:
        # Security check: prevent directory traversal
        reports_dir = Path(__file__).parent.parent.parent / "reports"
        safe_file_path = safe_path(reports_dir, filename)

        if not safe_file_path.exists():
            logger.warning("Report not found", extra={"report_filename": filename})
            raise HTTPException(status_code=404, detail=f"Report not found: {filename}")

        logger.info("Report downloaded", extra={"report_filename": filename})

        return FileResponse(
            str(safe_file_path),
            filename=filename,
            media_type="application/octet-stream",
        )

    except HTTPException:
        # Don't let the 404 (or any deliberate HTTP error) get rewrapped as a 500.
        raise
    except Exception as e:
        logger.error("Report download failed", extra={"error": str(e)})
        raise HTTPException(status_code=500, detail=f"Download failed: {str(e)}")


# =============================================================================
# Error Handlers
# =============================================================================


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Any, exc: HTTPException) -> JSONResponse:
    """Handle HTTP exceptions with structured error responses.

    Must return a Response (here, JSONResponse) — returning a plain dict makes
    Starlette try to call it as an ASGI app and crash, so every raised
    HTTPException would otherwise turn into an unhandled 500.
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.now(UTC).isoformat(),
        },
    )


# =============================================================================
# Main Entry Point
# =============================================================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
