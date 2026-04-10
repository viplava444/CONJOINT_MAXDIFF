# Conjoint & MaxDiff Design Engine

A production-ready Streamlit application for generating statistically efficient
survey designs for **Choice-Based Conjoint (CBC)** analysis and **MaxDiff
(Best-Worst Scaling)** studies.

---

## Features

| Feature | Details |
|---------|---------|
| **CBC Design** | Coordinate Exchange algorithm, Bayesian D-efficiency |
| **MaxDiff Design** | Near-BIBD with swap optimization, position balance |
| **Diagnostics** | D-efficiency gauge, level balance, correlation matrix |
| **Preview** | Pixel-faithful respondent view per block |
| **Export** | CSV, Excel (multi-sheet), JSON, Qualtrics, Sawtooth SSI |
| **Advanced** | Blocking, holdout tasks, fatigue optimization, prohibitions |

---

## Project Structure

```
conjoint_app/
│
├── app.py                      ← Streamlit entry point
├── requirements.txt
├── .streamlit/
│   └── config.toml             ← Theme & server settings
│
├── config/
│   ├── __init__.py
│   └── settings.py             ← All constants and defaults
│
├── core/                       ← Pure Python — no Streamlit dependency
│   ├── __init__.py
│   ├── models.py               ← Dataclasses (Attribute, CBCInput, etc.)
│   ├── cbc_generator.py        ← Coordinate Exchange + blocking
│   ├── maxdiff_generator.py    ← Near-BIBD + swap optimisation
│   └── validator.py            ← Statistical diagnostics
│
├── ui/                         ← Streamlit panel components
│   ├── __init__.py
│   ├── config_panel.py         ← Step 1: Configure
│   ├── generate_panel.py       ← Step 2: Generate
│   ├── preview_panel.py        ← Step 3: Preview
│   ├── diagnostics_panel.py    ← Step 4: Diagnostics
│   └── export_panel.py         ← Step 5: Export
│
├── exports/
│   ├── __init__.py
│   └── exporters.py            ← CSV / Excel / JSON / Qualtrics / Sawtooth
│
├── utils/
│   ├── __init__.py
│   ├── helpers.py              ← Session state, input builders, formatting
│   └── charts.py              ← Plotly chart builders
│
└── tests/
    ├── __init__.py
    ├── test_cbc_generator.py
    ├── test_maxdiff_generator.py
    └── test_validator_and_exports.py
```

---

## Quick Start

### 1. Clone / download the project

```bash
git clone <repo-url>
cd conjoint_app
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv .venv
source .venv/bin/activate        # macOS / Linux
.venv\Scripts\activate           # Windows
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
streamlit run app.py
```

The app opens at **http://localhost:8501** in your browser.

---

## Usage walkthrough

### Step 1 — Configure

- **CBC:** Add attributes and their levels (comma-separated). Mark the price
  attribute. Set tasks per respondent, alternatives per task, number of
  survey blocks, and optional prohibitions.
- **MaxDiff:** Add items (minimum 4). Set items per set, target appearances,
  and whether to use position balance and pair-coverage optimization.
- Load a **preset** (TV, Coffee Shop, Subscription Service, Brand Attributes,
  Job Factors) to get started instantly.

### Step 2 — Generate

- Click **Generate design**. The coordinate exchange runs 20 random starts
  and keeps the global best.
- Typical generation time: 5–30 seconds depending on design size.
- The design matrix is shown in a paginated table by block.

### Step 3 — Preview

- See the survey exactly as respondents will see it, block by block.
- Holdout tasks are labelled.
- Price attribute values are highlighted in blue.

### Step 4 — Diagnostics

- **D-efficiency gauge**: 80%+ is excellent; 65–80% is marginal.
- **Level balance**: chi-squared test per attribute; deviations >20% flagged.
- **Attribute correlation**: Spearman heatmap; max ρ should be < 0.10.
- **Task complexity**: distribution of cognitive load across tasks.
- Actionable **warnings and recommendations** for any issues detected.

### Step 5 — Export

| Format | Use case |
|--------|----------|
| CSV | Import into any analysis tool |
| Excel | Multi-sheet workbook with design + diagnostics + codebook |
| JSON | Programmatic / API use |
| Qualtrics CSV | Embedded data variables for loop & merge |
| Sawtooth CSV | Numeric level codes for Lighthouse Studio |

---

## Running tests

```bash
pip install pytest
pytest tests/ -v
```

Expected output: **~30 tests passing** in < 60 seconds.

---

## Configuration

Edit `config/settings.py` to change:

- Default values for all design parameters
- D-efficiency thresholds (good/warn)
- Preset attribute sets and item lists
- Chart color palette
- Algorithm hyperparameters (n_starts, max_iter, n_monte_carlo)

---

## Design methodology

### CBC — Coordinate Exchange

The generator uses the **Coordinate Exchange** algorithm (Meyer & Nachtsheim,
1995) with **Bayesian D-efficiency** criterion (Kessels et al., 2006).

1. Initialize a random feasible design matrix
2. For each cell (task × alternative × attribute), try every other level;
   keep the swap if it improves Bayesian D-efficiency
3. Repeat until no improvement found (local optimum)
4. Multi-start with 20 random initializations; keep global best

**D-efficiency** is computed via Monte Carlo integration over a Normal prior
on β, approximating the expected Fisher information matrix.

**Effects coding** (not dummy coding) ensures the information matrix is
non-singular even with correlated attribute patterns.

### MaxDiff — Near-BIBD

1. **Greedy initialization**: always select items with the lowest current
   appearance count (breaking ties by pair co-occurrence)
2. **Swap optimization**: iteratively swap items between sets to minimize
   variance of both appearance counts and pair co-occurrence
3. **Position balance**: permute item order within sets to equalize positional
   frequency
4. **Blocking**: distribute sets across survey versions

When a perfect BIBD (λ integer) is not achievable for the chosen (v, k, r),
the generator produces a **near-BIBD** where every item appears r or r+1 times.

---

## Future enhancements

1. **Adaptive CBC**: update Bayesian priors after each respondent's responses
   and select the most informative task dynamically.

2. **HB estimation pipeline**: add a full MCMC-based Hierarchical Bayes
   estimator so designs and analysis live in one system.

3. **Simulation-based sample size planner**: given a target SE for key
   utilities, simulate synthetic datasets and report empirical power curves.

4. **Qualtrics / Decipher live sync**: bidirectional API sync — design changes
   propagate to the live survey; collected data streams back for real-time
   estimation updates.

5. **Natural language design specification**: "I need a conjoint for a
   streaming service with 4 brands and 3 price points" → auto-extract
   attributes and suggest levels.

6. **Partial profile designs**: for 10+ attribute studies, show only a subset
   of attributes per task to reduce cognitive load.

7. **Alternative-specific attributes**: support attributes that only apply to
   specific alternatives (e.g., "fuel type" only for non-EV options).

8. **Design version control**: save, name, and compare multiple design versions
   within a session.

9. **Collaboration**: multi-user session sharing via a simple link.

10. **R / Python analysis templates**: auto-generate analysis scripts (mlogit,
    bayesm, Apollo) pre-wired for the exported design.

---

## References

- Louviere, J., Hensher, D., & Swait, J. (2000). *Stated Choice Methods*.
  Cambridge University Press.
- Meyer, R. K., & Nachtsheim, C. J. (1995). The coordinate-exchange algorithm
  for constructing exact optimal experimental designs. *Technometrics*, 37(1).
- Kessels, R., Goos, P., & Vandebroek, M. (2006). A comparison of criteria to
  design efficient choice experiments. *Journal of Marketing Research*, 43(3).
- Cohen, S. (2003). Maximum difference scaling: Improved measures of
  importance and preference for segmentation. *Sawtooth Software Conference*.
- Sawtooth Software (2021). *CBC Technical Paper*. Sawtooth Software, Inc.
