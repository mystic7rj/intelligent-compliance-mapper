# FastAPI REST Server

REST API wrapper for the Compliance Mapper CLI logic.

## Installation

FastAPI and Uvicorn are now included in `requirements.txt`. Install dependencies:

```bash
pip install -r requirements.txt
```

## Running the Server

Start the server on `http://localhost:8000`:

```bash
python -m src.api.server
```

Or use Uvicorn directly:

```bash
uvicorn src.api.server:app --host 0.0.0.0 --port 8000 --reload
```

## API Endpoints

### Health Check
- **GET** `/api/health` - Server health status

### Frameworks
- **GET** `/api/frameworks` - List all loaded compliance frameworks with control counts

### Compliance Analysis
- **POST** `/api/analyze` - Run gap analysis on implemented controls
  ```json
  {
    "framework": "NIST_CSF",
    "controls": ["ID.AM-01", "ID.AM-02", "PR.AC-01"]
  }
  ```
  Returns: Compliance percentage, risk score, and gap details

### Framework Comparison
- **POST** `/api/compare` - Compare two frameworks and identify mappings
  ```json
  {
    "source": "NIST_CSF",
    "target": "ISO_27001"
  }
  ```
  Returns: Control mappings with similarity scores

### Analytics
- **GET** `/api/analytics/summary?framework=NIST_CSF&controls=ID.AM-01,ID.AM-02`
  Returns: Maturity level, compliance metrics, and gap counts

### Report Generation
- **POST** `/api/reports/generate` - Generate compliance report
  ```json
  {
    "framework": "NIST_CSF",
    "controls": ["ID.AM-01", "ID.AM-02"],
    "format": "html"
  }
  ```
  Returns: Report metadata and download URL

- **GET** `/api/reports/download/{filename}` - Download generated report

## Interactive API Documentation

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

## Architecture

All endpoints reuse existing service classes:
- `GapAnalyzer` - Compliance gap analysis
- `RiskScorer` - Risk scoring (FAIR methodology)
- `CrossFrameworkAnalyzer` - ML-based control mapping
- `AnalyticsEngine` - Maturity assessment
- Repository classes - Database access
- Reporter classes - Report generation (HTML, PDF, Excel)

No business logic is duplicated; the API is a thin wrapper around existing services.

## Error Handling

HTTP Status Codes:
- `200` - Success
- `422` - Validation error (malformed request)
- `404` - Resource not found
- `500` - Server error

All errors include a timestamp and detailed message for debugging.

## CORS

CORS is enabled for all origins (`*`) to support web clients. Customize in `src/api/server.py` if needed.
