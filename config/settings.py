"""
config/settings.py
------------------
Central configuration and constants for the Conjoint & MaxDiff Design Engine.
Edit this file to change app-wide defaults without touching core logic.
"""

# ── App metadata ──────────────────────────────────────────────────────────────
APP_TITLE = "Conjoint & MaxDiff Design Engine"
APP_ICON = "🔬"
APP_VERSION = "1.0.0"
APP_LAYOUT = "wide"

# ── Design generation defaults ─────────────────────────────────────────────────
CBC_DEFAULTS = {
    "n_tasks": 10,
    "n_alternatives": 3,
    "n_blocks": 4,
    "n_holdout": 2,
    "sample_size": 300,
    "include_none": True,
    "include_holdout": True,
    "dual_none": False,
    "bayesian": True,
    "prior_variance": 1.0,
    "fatigue_opt": True,
    "max_iter": 500,
    "n_starts": 20,
    "n_monte_carlo": 200,
}

MAXDIFF_DEFAULTS = {
    "n_per_set": 4,
    "target_appearances": 3,
    "n_blocks": 2,
    "position_balance": True,
    "pair_optimization": True,
    "anchored": False,
    "max_iter": 300,
}

# ── Statistical thresholds ─────────────────────────────────────────────────────
D_EFFICIENCY_GOOD = 80.0       # % — green badge
D_EFFICIENCY_WARN = 65.0       # % — yellow badge; below this is red
BALANCE_CHI2_ALPHA = 0.05      # significance level for balance test
MAX_ATTR_CORRELATION = 0.10    # Spearman ρ threshold for independence
OVERLAP_WARN_PCT = 30.0        # % task overlap before warning

# ── Sample attribute presets ───────────────────────────────────────────────────
PRESET_ATTRIBUTES = {
    "TV / Consumer Electronics": [
        {"name": "Brand",       "levels": ["Sony", "Samsung", "LG", "Apple"],     "is_price": False},
        {"name": "Screen Size", "levels": ['43"', '55"', '65"', '75"'],           "is_price": False},
        {"name": "Resolution",  "levels": ["4K UHD", "8K", "1080p"],             "is_price": False},
        {"name": "Price",       "levels": ["$499", "$799", "$1,199", "$1,699"],   "is_price": True},
    ],
    "Coffee Shop": [
        {"name": "Brand",       "levels": ["Starbucks", "Peet's", "Local"],       "is_price": False},
        {"name": "Size",        "levels": ["Small", "Medium", "Large"],           "is_price": False},
        {"name": "Milk",        "levels": ["Whole", "Oat", "Almond", "None"],     "is_price": False},
        {"name": "Price",       "levels": ["$3.50", "$4.50", "$5.50", "$6.50"],   "is_price": True},
    ],
    "Subscription Service": [
        {"name": "Provider",    "levels": ["Netflix", "Disney+", "Apple TV+"],    "is_price": False},
        {"name": "Plan",        "levels": ["Basic", "Standard", "Premium"],       "is_price": False},
        {"name": "Screens",     "levels": ["1 screen", "2 screens", "4 screens"], "is_price": False},
        {"name": "Price/month", "levels": ["$8", "$13", "$18", "$23"],            "is_price": True},
    ],
    "Custom": [],
}

PRESET_MAXDIFF_ITEMS = {
    "Brand Attributes": [
        "Innovative product design", "Strong brand reputation", "Competitive pricing",
        "Excellent customer service", "Wide product range", "Sustainability practices",
        "Fast delivery", "Easy returns policy", "Loyalty rewards", "Technical support",
        "Mobile app experience", "Store locations",
    ],
    "Job Factors": [
        "Salary & compensation", "Work-life balance", "Career growth opportunities",
        "Company culture", "Remote work flexibility", "Interesting projects",
        "Job security", "Benefits package", "Team collaboration", "Company mission",
        "Recognition & feedback", "Learning & development",
    ],
    "Custom": [],
}

# ── Export settings ────────────────────────────────────────────────────────────
EXPORT_FORMATS = ["CSV", "Excel", "JSON", "Qualtrics (CSV)", "Sawtooth (CSV)"]

# ── Color palette for charts ───────────────────────────────────────────────────
CHART_COLORS = {
    "primary":   "#4B6BFB",
    "success":   "#22C55E",
    "warning":   "#F59E0B",
    "danger":    "#EF4444",
    "neutral":   "#6B7280",
    "light":     "#E5E7EB",
}
