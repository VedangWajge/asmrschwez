# Wind Forecast Intelligence Dashboard

An enterprise energy analytics web application for a UK electricity utility to evaluate national wind generation actuals and day-ahead forecasts from the Elexon BMRS API, supporting wholesale power procurement decisions for January 2026.

> AI tools (Google Antigravity / Claude / Gemini) were used to assist with development of this application.

---

## Technology Stack

| Layer     | Technology                                    |
|-----------|-----------------------------------------------|
| Frontend  | React 18, TypeScript, Vite (Vanilla CSS)      |
| Backend   | Python 3.11, FastAPI, Uvicorn, HTTPX          |
| Testing   | Pytest, Pytest-Asyncio, HTTPX MockTransport   |
| Data      | Elexon BMRS API (`FUELHH`, `WINDFOR` streams) |
| Container | Docker, Docker Compose                        |

---

## Dashboard Functionality

1. **Header & Procurement Controls**:
   - **Delivery Date Picker**: Restricted to January 1–31, 2026 with previous/next day quick steppers.
   - **D-1 Decision Cutoff Selector**: Configurable cutoff time (default: `12:00 UTC`, with options from 08:00 to 17:00 UTC) reflecting the power purchase deadline on the day before delivery.
   - **Live Reload & Status**: Immediate updates with loading and error/retry states.

2. **Executive KPI Cards**:
   - **Day-Ahead Forecast Energy**: Total predicted energy in MWh/GWh ($\sum \text{MW} \times 0.5\text{ h}$) with average power (MW).
   - **Actual Delivered Energy**: Total delivered wind energy in MWh/GWh ($\sum \text{MW} \times 0.5\text{h}$) with average power (MW).
   - **Forecast Coverage**: Matched settlement periods out of 48 expected half-hour periods (e.g., 48/48, 100%).
   - **Mean Absolute Error (MAE)**: Average magnitude of forecast deviation in MW.
   - **Root Mean Square Error (RMSE)**: Error metric penalizing large forecast swings in MW.
   - **Forecast Bias (Mean Error)**: Average signed error in MW ($\text{Forecast} - \text{Actual}$). Positive indicates over-forecasting (procurement risk); negative indicates under-forecasting (system imbalance risk).

3. **Generation Profile Chart**:
   - Interactive, lightweight SVG time-series chart showing Actual generation (Forest Green) versus Day-Ahead Forecast (Cobalt Blue dashed line) across all 48 half-hour settlement periods (00:00 to 23:30 GMT).
   - Crosshair hover tracker displaying Settlement Period (SP 1–48), target GMT time, Actual MW, Forecast MW, Error MW, and the exact forecast publication timestamp.
   - Visual handling of missing periods without fabricating zero or interpolated values.

4. **Settlement Period Publication Audit Table**:
   - Full 48-period audit displaying target delivery time, the selected forecast's original `publishTime`, forecast generation, actual generation, and signed forecast error.
   - Quick filters: All Periods, Large Errors ($|\text{Error}| \ge 500\text{ MW}$), and Missing Data.

---

## Domain & Market Design

### Delivery Period vs. Publication Window
- **Delivery Window**: January 1, 2026 to January 31, 2026 (target `startTime` from `2026-01-01T00:00:00Z` to `2026-01-31T23:30:00Z`, 1,488 half-hour settlement periods). All timestamps are timezone-aware and displayed in UK local time (`Europe/London` / GMT, UTC+0 in January).
- **Publication Window**: For delivery day $D$, day-ahead power purchase decisions are made on $D-1$. To evaluate January 1 delivery decisions, forecasts published starting on **December 31, 2025** are retrieved. Forecasts published in late January targeting February delivery are excluded from the January analysis.

### Day-Ahead Decision Cutoff
- **Default Assumption**: The assignment specifies that purchasing decisions must be made one day before the delivery day ($D-1$), without stating a statutory hour. By default, the cutoff is set to **12:00 UTC (midday) on D-1**, reflecting common UK day-ahead wholesale power auction gate closures (e.g., EPEX SPOT GB Day-Ahead 30-min auction).
- **Configurability**: The cutoff hour is fully configurable per request via the API and the UI control. It is documented as an explicit operational assumption rather than a regulatory mandate.

### Forecast Selection & Alignment
- Forecasts and actuals are matched strictly by target settlement period `startTime`.
- For each target period, the system selects the latest forecast published on or before the $D-1$ cutoff.
- Any forecast published after the cutoff is excluded from day-ahead decision metrics.
- Missing values for either actuals or forecasts remain `null` without fabricated or interpolated data.

### Metric Definitions
- **Settlement Energy (MWh)**: Calculated from instantaneous 30-minute power readings:
  $$\text{Energy (MWh)} = \sum_{i} \left(\text{Generation}_i \text{ (MW)} \times 0.5\text{ h}\right)$$
- **Mean Absolute Error (MAE)**:
  $$\text{MAE} = \frac{1}{n} \sum_{i=1}^{n} |\text{Forecast}_i - \text{Actual}_i|$$
- **Root Mean Square Error (RMSE)**:
  $$\text{RMSE} = \sqrt{\frac{1}{n} \sum_{i=1}^{n} (\text{Forecast}_i - \text{Actual}_i)^2}$$
- **Forecast Bias (Mean Error)**:
  $$\text{Bias} = \frac{1}{n} \sum_{i=1}^{n} (\text{Forecast}_i - \text{Actual}_i)$$
*All metrics are calculated strictly over matched settlement periods $n$ where both actual and forecast observations exist.*

---

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/day-ahead` | GET | Matched delivery periods, error metrics, and selected forecasts for a delivery date range and cutoff hour. |
| `/api/actuals` | GET | Raw half-hourly wind actuals from Elexon `FUELHH`. |
| `/api/forecasts` | GET | Raw wind generation forecasts from Elexon `WINDFOR` preserving full publication history. |
| `/health` | GET | Backend health check. |
| `/docs` | GET | Interactive OpenAPI / Swagger documentation. |

---

## Local Setup

### Prerequisites

- Node.js ≥ 20
- Python ≥ 3.11
- Docker and Docker Compose (for containerised run)

### 1. Backend Setup

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
pip install -r requirements-dev.txt

# Run automated tests
pytest -v

# Start development server
uvicorn app.main:app --reload --port 8000
```

### 2. Frontend Setup

```bash
cd frontend
npm install

# Run TypeScript type check
npm run typecheck

# Build production bundle
npm run build

# Start Vite development server
npm run dev
```

Visit [http://localhost:5173](http://localhost:5173) in your browser.

---

## Docker Compose

To build and run both frontend and backend in isolated containers:

```bash
docker compose up --build
```

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend API: [http://localhost:8000](http://localhost:8000)

---

## Known Limitations

1. **Elexon API Filter Granularity**:
   - `/datasets/WINDFOR/stream` filters by `publishDateTime`, not target `startTime`. The backend fetches the required publication history and filters target dates in memory.
2. **Day-Ahead Auction Rules**:
   - While 12:00 UTC D-1 represents the EPEX SPOT Day-Ahead 30-min auction gate closure, individual procurement desks may trade at 11:00 UTC (Hourly auction) or adjust intra-day. The dashboard supports this via the configurable cutoff selector.
