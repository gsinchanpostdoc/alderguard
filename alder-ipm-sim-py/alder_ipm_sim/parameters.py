# Parameter sets, defaults, and calibration utilities.
from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional


@dataclass(frozen=True)
class ParamMeta:
    """Metadata for a single model parameter."""

    name: str
    symbol: str
    default: float
    min_val: float
    max_val: float
    unit: str
    description: str
    module: str  # 'within_season' or 'annual'
    category: str  # 'biotic_rate', 'mortality', 'phenology', 'control', 'threshold'

    def to_latex(self) -> str:
        """Return the parameter symbol in LaTeX notation."""
        _LATEX_MAP = {
            "β": r"\beta",
            "h": "h",
            "c_B": "c_B",
            "a_B": "a_B",
            "μ_S": r"\mu_S",
            "μ_I": r"\mu_I",
            "δ": r"\delta",
            "η": r"\eta",
            "μ_F": r"\mu_F",
            "κ": r"\kappa",
            "T": "T",
            "B_idx": "B_{\\mathrm{idx}}",
            "R_B": "R_B",
            "σ_A": r"\sigma_A",
            "σ_F": r"\sigma_F",
            "K_0": "K_0",
            "φ": r"\varphi",
            "ρ": r"\rho",
            "u_P^{max}": "u_P^{\\max}",
            "u_C^{max}": "u_C^{\\max}",
            "u_B^{max}": "u_B^{\\max}",
            "D_crit": "D_{\\mathrm{crit}}",
            "K_min": "K_{\\min}",
        }
        latex = _LATEX_MAP.get(self.symbol, self.symbol)
        return f"${latex}$"


# ---------------------------------------------------------------------------
# PARAM_REGISTRY — every parameter used by the Alnus–beetle–parasitoid–bird
# ecoepidemic model, with full ecological descriptions from the manuscript.
# ---------------------------------------------------------------------------

PARAM_REGISTRY: Dict[str, ParamMeta] = {}


def _r(p: ParamMeta) -> None:
    """Register a ParamMeta into the global registry."""
    PARAM_REGISTRY[p.name] = p


# ── Within-season parameters ──────────────────────────────────────────────

_r(ParamMeta(
    name="beta",
    symbol="β",
    default=0.20,
    min_val=0.01,
    max_val=0.50,
    unit="/day",
    description=(
        "Parasitoid attack rate (Holling Type II functional response numerator; "
        "rate at which adult Meigenia mutabilis parasitoids successfully oviposit "
        "into Agelastica alni beetle larvae)"
    ),
    module="within_season",
    category="biotic_rate",
))

_r(ParamMeta(
    name="h",
    symbol="h",
    default=0.00575,
    min_val=0.001,
    max_val=0.01,
    unit="days",
    description=(
        "Parasitoid handling time (time-limiting saturation parameter in Holling II "
        "response; represents search-and-oviposition time per host)"
    ),
    module="within_season",
    category="biotic_rate",
))

_r(ParamMeta(
    name="c_B",
    symbol="c_B",
    default=0.0209,
    min_val=0.01,
    max_val=0.03,
    unit="/day",
    description=(
        "Bird per-unit consumption rate coefficient (rate at which generalist "
        "passeriform birds consume beetle larvae)"
    ),
    module="within_season",
    category="biotic_rate",
))

_r(ParamMeta(
    name="a_B",
    symbol="a_B",
    default=0.00651,
    min_val=0.0001,
    max_val=0.02,
    unit="days",
    description=(
        "Bird half-saturation parameter (Holling II; larval density at which bird "
        "predation reaches half its maximum)"
    ),
    module="within_season",
    category="biotic_rate",
))

_r(ParamMeta(
    name="mu_S",
    symbol="μ_S",
    default=0.00423,
    min_val=0.003,
    max_val=0.03,
    unit="/day",
    description=(
        "Background mortality rate of susceptible (unparasitised) beetle larvae "
        "(natural death from desiccation, disease, intraspecific competition)"
    ),
    module="within_season",
    category="mortality",
))

_r(ParamMeta(
    name="mu_I",
    symbol="μ_I",
    default=0.0443,
    min_val=0.02,
    max_val=0.08,
    unit="/day",
    description=(
        "Background mortality rate of parasitised beetle larvae (higher than mu_S "
        "due to physiological burden of parasitoid development)"
    ),
    module="within_season",
    category="mortality",
))

_r(ParamMeta(
    name="delta",
    symbol="δ",
    default=0.1918,
    min_val=0.05,
    max_val=0.25,
    unit="/day",
    description=(
        "Parasitoid-induced mortality rate (rate at which parasitoid emergence kills "
        "the host larva; temperature-dependent development)"
    ),
    module="within_season",
    category="mortality",
))

_r(ParamMeta(
    name="eta",
    symbol="η",
    default=0.7054,
    min_val=0.5,
    max_val=1.0,
    unit="dimensionless",
    description=(
        "Parasitoid conversion efficiency (number of new adult parasitoid flies "
        "produced per parasitised host that undergoes emergence)"
    ),
    module="within_season",
    category="biotic_rate",
))

_r(ParamMeta(
    name="mu_F",
    symbol="μ_F",
    default=0.0309,
    min_val=0.01,
    max_val=0.08,
    unit="/day",
    description="Baseline natural mortality of adult parasitoid flies",
    module="within_season",
    category="mortality",
))

_r(ParamMeta(
    name="kappa",
    symbol="κ",
    default=0.00273,
    min_val=0.0001,
    max_val=0.003,
    unit="/day",
    description=(
        "Defoliation conversion rate (rate at which larval feeding density "
        "translates to fractional canopy loss per day)"
    ),
    module="within_season",
    category="biotic_rate",
))

_r(ParamMeta(
    name="T",
    symbol="T",
    default=49.9,  # calibrated value; manuscript baseline is 55 days
    min_val=45.0,
    max_val=70.0,
    unit="days",
    description=(
        "Duration of larval vulnerability window (spring-summer period when beetle "
        "larvae are active and exposed to parasitism/predation). "
        "Manuscript baseline is 55 days; default here is calibrated to 49.9 days."
    ),
    module="within_season",
    category="phenology",
))

_r(ParamMeta(
    name="B_index",
    symbol="B_idx",
    default=1.59,
    min_val=0.5,
    max_val=2.0,
    unit="dimensionless",
    description=(
        "Exogenous bird predation pressure index (scaled from PECBMS passerine "
        "monitoring data; reflects regional bird abundance)"
    ),
    module="within_season",
    category="biotic_rate",
))

# ── Annual (between-season) parameters ────────────────────────────────────

_r(ParamMeta(
    name="R_B",
    symbol="R_B",
    default=9.53,
    min_val=6.0,
    max_val=16.0,
    unit="dimensionless",
    description=(
        "Beetle annual reproduction ratio (Beverton-Holt fecundity; expected "
        "offspring per adult surviving to reproduce)"
    ),
    module="annual",
    category="biotic_rate",
))

_r(ParamMeta(
    name="sigma_A",
    symbol="σ_A",
    default=0.781,
    min_val=0.5,
    max_val=0.9,
    unit="dimensionless",
    description=(
        "Beetle overwintering survival probability (fraction surviving pupation, "
        "winter dormancy, spring emergence, and mating)"
    ),
    module="annual",
    category="mortality",
))

_r(ParamMeta(
    name="sigma_F",
    symbol="σ_F",
    default=0.363,
    min_val=0.3,
    max_val=0.7,
    unit="dimensionless",
    description=(
        "Parasitoid overwinter survival probability (fraction of parasitoid puparia "
        "surviving in soil through winter)"
    ),
    module="annual",
    category="mortality",
))

_r(ParamMeta(
    name="K_0",
    symbol="K_0",
    default=1.712,
    min_val=1.0,
    max_val=2.0,
    unit="relative units",
    description=(
        "Baseline carrying capacity (maximum beetle recruitment capacity under "
        "fully recovered, undamaged canopy)"
    ),
    module="annual",
    category="threshold",
))

_r(ParamMeta(
    name="phi",
    symbol="φ",
    default=0.0449,
    min_val=0.01,
    max_val=0.1,
    unit="dimensionless",
    description=(
        "Foliage-feedback penalty coefficient (strength of induced phytochemical "
        "defence; K_t = K_0 * exp(-phi * D_t))"
    ),
    module="annual",
    category="phenology",
))

_r(ParamMeta(
    name="rho",
    symbol="ρ",
    default=0.5,
    min_val=0.5,
    max_val=0.5,
    unit="dimensionless",
    description="Baseline bird pressure multiplier",
    module="annual",
    category="biotic_rate",
))

# ── Control parameters ────────────────────────────────────────────────────

_r(ParamMeta(
    name="u_P_max",
    symbol="u_P^{max}",
    default=0.5,
    min_val=0.0,
    max_val=1.0,
    unit="individuals/ha/day",
    description="Maximum parasitoid augmentation effort",
    module="annual",
    category="control",
))

_r(ParamMeta(
    name="u_C_max",
    symbol="u_C^{max}",
    default=0.2,
    min_val=0.0,
    max_val=1.0,
    unit="individuals/ha/day",
    description="Maximum direct larval removal effort",
    module="annual",
    category="control",
))

_r(ParamMeta(
    name="u_B_max",
    symbol="u_B^{max}",
    default=1.0,
    min_val=0.0,
    max_val=2.0,
    unit="relative units",
    description="Maximum annual bird-habitat enhancement",
    module="annual",
    category="control",
))

# ── Threshold parameters ──────────────────────────────────────────────────

_r(ParamMeta(
    name="D_crit",
    symbol="D_crit",
    default=0.5,
    min_val=0.0,
    max_val=1.0,
    unit="dimensionless",
    description=(
        "Critical defoliation threshold (canopy loss exceeding 50% triggers "
        "collapse risk)"
    ),
    module="annual",
    category="threshold",
))

_r(ParamMeta(
    name="K_min",
    symbol="K_min",
    default=0.856,
    min_val=0.0,
    max_val=1.0,
    unit="relative units",
    description=(
        "Minimum carrying capacity for viable beetle population (0.5 * K_0)"
    ),
    module="annual",
    category="threshold",
))

# Clean up module-level helper
del _r


# ---------------------------------------------------------------------------
# Preset Scenarios — ecologically meaningful parameter combinations
# representing climate change impacts and management strategies.
# ---------------------------------------------------------------------------

PRESET_SCENARIOS: Dict[str, Dict] = {
    "baseline_calibrated": {
        "name": "Baseline Calibrated",
        "description": (
            "Current calibrated parameter values fitted to field observations. "
            "Represents the present-day Alnus glutinosa–beetle–parasitoid–bird system."
        ),
        "params": {
            "beta": 0.20, "h": 0.00575, "c_B": 0.0209, "a_B": 0.00651,
            "mu_S": 0.00423, "mu_I": 0.0443, "delta": 0.1918, "eta": 0.7054,
            "mu_F": 0.0309, "kappa": 0.00273, "T": 49.9, "B_index": 1.59,
            "R_B": 9.53, "sigma_A": 0.781, "sigma_F": 0.363, "K_0": 1.712,
            "phi": 0.0449,
        },
        "expected_regime": "coexistence",
        "manuscript_ref": "Table 1 and Section 2.1",
    },
    "warm_winter": {
        "name": "Warm Winter",
        "description": (
            "Warmer winters increase beetle and parasitoid overwintering survival "
            "and extend the larval season, raising outbreak risk under climate change."
        ),
        "params": {
            "sigma_A": 0.88, "sigma_F": 0.55, "T": 55,
        },
        "expected_regime": "parasitoid_free",
        "manuscript_ref": "Section 3.3 — phenological sensitivity analysis",
    },
    "short_season": {
        "name": "Short Season",
        "description": (
            "Cooler or delayed springs shorten the larval vulnerability window, "
            "reduce beetle survival, and lower fecundity."
        ),
        "params": {
            "T": 45, "sigma_A": 0.6, "R_B": 7.0,
        },
        "expected_regime": "coexistence",
        "manuscript_ref": "Section 3.3 — phenological sensitivity analysis",
    },
    "high_bird_pressure": {
        "name": "High Bird Pressure",
        "description": (
            "Enhanced avian predation through increased passerine abundance and "
            "higher per-capita consumption, simulating bird-habitat management."
        ),
        "params": {
            "B_index": 1.9, "c_B": 0.025,
        },
        "expected_regime": "coexistence",
        "manuscript_ref": "Section 3.4 — bird predation impact",
    },
    "low_parasitism": {
        "name": "Low Parasitism",
        "description": (
            "Weak parasitoid control due to low attack rate, poor conversion "
            "efficiency, and slow parasitoid-induced mortality."
        ),
        "params": {
            "beta": 0.05, "eta": 0.5, "delta": 0.1,
        },
        "expected_regime": "parasitoid_free",
        "manuscript_ref": "Section 3.2 — parasitoid efficacy analysis",
    },
    "outbreak_risk": {
        "name": "Outbreak Risk",
        "description": (
            "High beetle fecundity with elevated overwintering survival and "
            "weak canopy feedback creates conditions for severe defoliation outbreaks."
        ),
        "params": {
            "R_B": 14.0, "sigma_A": 0.85, "phi": 0.02,
        },
        "expected_regime": "parasitoid_free",
        "manuscript_ref": "Section 3.5 — tipping point analysis",
    },
    "managed_forest": {
        "name": "Managed Forest",
        "description": (
            "Integrated pest management combining parasitoid augmentation, "
            "direct larval removal, and bird-habitat enhancement (Strategy C optimal)."
        ),
        "params": {
            "u_P_max": 0.5, "u_C_max": 0.2, "u_B_max": 1.0,
        },
        "expected_regime": "coexistence",
        "manuscript_ref": "Section 4 — optimal control comparison",
    },
}


def get_preset(name: str) -> Dict:
    """Return a preset scenario dict by key. Raises KeyError if not found."""
    try:
        return PRESET_SCENARIOS[name]
    except KeyError:
        raise KeyError(
            f"Unknown preset '{name}'. "
            f"Available: {', '.join(sorted(PRESET_SCENARIOS))}"
        ) from None


def list_presets() -> Dict[str, str]:
    """Return a dict mapping preset key to its display name."""
    return {k: v["name"] for k, v in PRESET_SCENARIOS.items()}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def get_defaults() -> Dict[str, float]:
    """Return a dictionary mapping parameter name to its default value."""
    return {name: pm.default for name, pm in PARAM_REGISTRY.items()}


def get_param(name: str) -> ParamMeta:
    """Look up a parameter by name. Raises KeyError if not found."""
    try:
        return PARAM_REGISTRY[name]
    except KeyError:
        raise KeyError(
            f"Unknown parameter '{name}'. "
            f"Available: {', '.join(sorted(PARAM_REGISTRY))}"
        ) from None


def validate_params(params: Dict[str, float]) -> None:
    """Validate that every value in *params* lies within its registered bounds.

    Raises ``ValueError`` with a descriptive message for the first
    out-of-range parameter encountered.  Unknown parameter names are
    silently ignored so callers can pass supersets.
    """
    for name, value in params.items():
        meta: Optional[ParamMeta] = PARAM_REGISTRY.get(name)
        if meta is None:
            continue
        if not (meta.min_val <= value <= meta.max_val):
            raise ValueError(
                f"Parameter '{name}' ({meta.symbol}) = {value} is outside "
                f"the valid range [{meta.min_val}, {meta.max_val}]. "
                f"Description: {meta.description}"
            )
