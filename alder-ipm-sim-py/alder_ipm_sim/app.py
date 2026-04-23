# Streamlit interactive dashboard for the AlderIPM-Sim toolkit.
from __future__ import annotations

import json
import io
import base64
from typing import Dict, List, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import streamlit as st

from .parameters import PARAM_REGISTRY, PRESET_SCENARIOS, ParamMeta, get_defaults
from .model import AlderIPMSimModel
from .fitting import ModelFitter, ResidualDiagnostics
from .warnings import EarlyWarningDetector, PRCCResult
from .control import ControlOptimizer, OptimalControl
from .comparison import compare_scenarios, parameter_sweep_1d, parameter_sweep_2d, ScenarioResult
from .report import ReportGenerator

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(page_title="AlderIPM-Sim", layout="wide")

# ---------------------------------------------------------------------------
# Caching helpers
# ---------------------------------------------------------------------------


@st.cache_resource
def _get_model(params_json: str) -> AlderIPMSimModel:
    """Cache a model instance keyed by its serialised parameter dict."""
    return AlderIPMSimModel(json.loads(params_json))


@st.cache_data(show_spinner=False)
def _cached_simulate(
    params_json: str, A0: float, F0: float, K0: float, D0: float,
    n_years: int, store_within_season: bool = False,
) -> Dict:
    model = AlderIPMSimModel(json.loads(params_json))
    result = model.simulate(
        A0=A0, F0=F0, K0=K0, D0=D0, n_years=n_years,
        store_within_season=store_within_season,
    )
    # Convert arrays to lists for caching
    out = {}
    for k, v in result.items():
        if isinstance(v, np.ndarray):
            out[k] = v.tolist()
        elif isinstance(v, list):
            out[k] = v  # within_season sol objects
        else:
            out[k] = v
    return out


@st.cache_data(show_spinner=False)
def _cached_find_fixed_points(params_json: str):
    model = AlderIPMSimModel(json.loads(params_json))
    return model.find_fixed_points()


@st.cache_data(show_spinner=False)
def _cached_compute_R_P(params_json: str) -> float:
    model = AlderIPMSimModel(json.loads(params_json))
    return model.compute_R_P()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Mapping from PARAM_REGISTRY keys in calibrated JSON that differ
_CALIBRATED_KEY_MAP = {
    "K0": "K_0",
    "uP_max": "u_P_max",
    "uC_max": "u_C_max",
    "uB_max": "u_B_max",
}

# Friendly category labels and grouping
_CATEGORY_LABELS = {
    ("within_season", "biotic_rate"): "Within-Season Biotic Rates",
    ("within_season", "mortality"): "Mortality Rates",
    ("within_season", "phenology"): "Phenology",
    ("annual", "biotic_rate"): "Annual Dynamics",
    ("annual", "mortality"): "Annual Dynamics",
    ("annual", "phenology"): "Annual Dynamics",
    ("annual", "control"): "Control",
    ("annual", "threshold"): "Thresholds",
}

# Parameter presets — use canonical definitions from parameters.py
_PRESETS = {v["name"]: v["params"] for v in PRESET_SCENARIOS.values()}


def _group_params() -> Dict[str, Dict[str, ParamMeta]]:
    """Group parameters by display category."""
    groups: Dict[str, Dict[str, ParamMeta]] = {}
    for name, pm in PARAM_REGISTRY.items():
        label = _CATEGORY_LABELS.get((pm.module, pm.category), pm.category.title())
        groups.setdefault(label, {})[name] = pm
    return groups


def _load_calibrated_baseline() -> Dict[str, float]:
    """Load baseline_params_calibrated.json with key normalisation."""
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    path = os.path.join(os.path.dirname(base), "baseline_params_calibrated.json")
    if not os.path.exists(path):
        path = "baseline_params_calibrated.json"
    with open(path) as f:
        raw = json.load(f)
    mapped: Dict[str, float] = {}
    for k, v in raw.items():
        key = _CALIBRATED_KEY_MAP.get(k, k)
        if key in PARAM_REGISTRY:
            mapped[key] = float(v)
    return mapped


def _download_params_button(params: Dict[str, float], key: str = "dl") -> None:
    st.download_button(
        "Download current parameters (JSON)",
        data=json.dumps(params, indent=2),
        file_name="alder-ipm-sim_params.json",
        mime="application/json",
        key=key,
    )


def _regime_color(eq_class: str) -> str:
    if eq_class == "coexistence":
        return "green"
    if eq_class in ("parasitoid_free", "canopy_only", "trivial"):
        return "red"
    return "orange"


def _regime_emoji(eq_class: str) -> str:
    colors = {"green": "🟢", "red": "🔴", "orange": "🟡"}
    return colors.get(_regime_color(eq_class), "⚪")


def _alert_css(color: str, text: str) -> str:
    bg = {"green": "#d4edda", "yellow": "#fff3cd", "red": "#f8d7da", "orange": "#fff3cd"}
    border = {"green": "#28a745", "yellow": "#ffc107", "red": "#dc3545", "orange": "#ffc107"}
    return (
        f'<div style="padding:12px;border-left:5px solid {border.get(color, "#666")}; '
        f'background:{bg.get(color, "#eee")};border-radius:4px;margin:8px 0;">'
        f"{text}</div>"
    )


def _params_json(params: Dict[str, float]) -> str:
    """Serialise params dict to a JSON string for use as cache key."""
    return json.dumps(params, sort_keys=True)


def _check_stability_warnings(params: Dict[str, float]) -> List[str]:
    """Return warnings when parameters approach unstable regimes."""
    warnings = []
    try:
        model = AlderIPMSimModel(dict(params))
        R_P = model.compute_R_P()
        if R_P < 1.05 and R_P > 1.0:
            warnings.append(
                f"R_P = {R_P:.4f} is very close to 1. "
                "Small parameter changes could cause parasitoid extinction."
            )
        if R_P <= 1.0:
            warnings.append(
                f"R_P = {R_P:.4f} < 1: parasitoid cannot invade. "
                "System will collapse to parasitoid-free state."
            )
    except Exception:
        pass

    phi = params.get("phi", 0.0449)
    if phi > 0.08:
        warnings.append(
            f"phi = {phi:.4f} is high. Strong foliage-feedback penalty "
            "may cause canopy collapse."
        )

    R_B = params.get("R_B", 9.53)
    sigma_A = params.get("sigma_A", 0.781)
    if R_B * sigma_A > 14:
        warnings.append(
            f"R_B * sigma_A = {R_B * sigma_A:.2f} is high. "
            "Beetle population may outpace parasitoid control."
        )

    return warnings


def _generate_report_text(params, sim_result, fps, R_P, ews_report=None) -> str:
    """Generate a plain-text summary report of all analyses."""
    lines = [
        "=" * 60,
        "AlderIPM-Sim Analysis Report",
        "=" * 60,
        "",
        "--- Parameters ---",
    ]
    for k, v in sorted(params.items()):
        pm = PARAM_REGISTRY.get(k)
        if pm:
            lines.append(f"  {pm.symbol} ({k}) = {v:.6g}  [{pm.unit}]")

    lines.extend(["", "--- Key Metrics ---"])
    lines.append(f"  R_P = {R_P:.6f}")

    if fps:
        lines.extend(["", "--- Equilibrium Points ---"])
        for fp in fps:
            lines.append(
                f"  {fp.equilibrium_class}: A*={fp.A_star:.4f}, F*={fp.F_star:.4f}, "
                f"K*={fp.K_star:.4f}, D*={fp.D_star:.4f} | "
                f"stable={fp.stable}, |lambda|={fp.dominant_eigenvalue:.4f}"
            )

    if sim_result:
        lines.extend(["", "--- Simulation End State ---"])
        n = len(sim_result["A"]) - 1
        for key in ["A", "F", "K", "D"]:
            arr = sim_result[key]
            lines.append(f"  {key}[{n}] = {arr[-1]:.6f}")

    if ews_report:
        lines.extend(["", "--- Early Warning Signals ---"])
        lines.append(f"  Alert Level: {ews_report.alert_level.upper()}")
        for name, res in ews_report.kendall_results.items():
            lines.append(f"  {name}: tau={res['tau']:+.4f}, p={res['p_value']:.4f}")

    lines.extend(["", "=" * 60])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Sidebar — persistent regime status
# ---------------------------------------------------------------------------

st.sidebar.title("AlderIPM-Sim")
st.sidebar.markdown(
    "Decision-support toolkit for Alnus-beetle-parasitoid-bird "
    "ecoepidemic management."
)

# Session-state defaults
if "params" not in st.session_state:
    st.session_state["params"] = get_defaults()

# Persistent regime traffic light
st.sidebar.markdown("---")
st.sidebar.markdown("### Current Regime Status")

try:
    _sb_params = st.session_state["params"]
    _sb_model = AlderIPMSimModel(dict(_sb_params))
    _sb_R_P = _sb_model.compute_R_P()
    _sb_rp_ok = _sb_R_P > 1.0

    # Quick classification from a short simulation
    _sb_sim = _sb_model.simulate(
        A0=_sb_params.get("K_0", 1.7) * 0.5,
        F0=0.1, K0=_sb_params.get("K_0", 1.7), D0=0.0,
        n_years=50,
    )
    _sb_eq = AlderIPMSimModel._classify_equilibrium(
        _sb_sim["A"][-1], _sb_sim["F"][-1],
        _sb_sim["K"][-1], _sb_sim["D"][-1], 1e-6,
    )
    _sb_color = _regime_color(_sb_eq)
    _sb_emoji = _regime_emoji(_sb_eq)

    st.sidebar.markdown(
        f"**{_sb_emoji} {_sb_eq.replace('_', ' ').title()}**"
    )
    st.sidebar.markdown(f"R_P = {_sb_R_P:.4f}")
    if _sb_color == "green":
        st.sidebar.success("System is in stable coexistence.")
    elif _sb_color == "orange":
        st.sidebar.warning("Regime approaching instability.")
    else:
        st.sidebar.error("System in degraded regime.")
except Exception:
    st.sidebar.info("Configure parameters to see regime status.")

st.sidebar.markdown("---")
st.sidebar.markdown("**About**")
st.sidebar.markdown(
    "This tool implements the mathematical model from:\n\n"
    "*Ecological dynamics and integrated pest management of the "
    "Alnus-Agelastica-Meigenia-passerine system.*"
)

# Export full report button in sidebar
st.sidebar.markdown("---")
if st.sidebar.button("Export HTML Report", key="export_report"):
    try:
        p = st.session_state["params"]
        mdl = AlderIPMSimModel(dict(p))
        rp = mdl.compute_R_P()
        fps = mdl.find_fixed_points()
        sim = mdl.simulate(
            A0=p.get("K_0", 1.7) * 0.5, F0=0.1,
            K0=p.get("K_0", 1.7), D0=0.0, n_years=50,
        )
        sim_list = {k: v.tolist() if isinstance(v, np.ndarray) else v for k, v in sim.items()}

        gen = ReportGenerator(params=dict(p), scenario_name="Current Session")
        gen.add_simulation(sim_list)

        R1, R2 = None, None
        try:
            R1 = mdl.compute_R1()
        except Exception:
            pass
        try:
            R2 = mdl.compute_R2()
        except Exception:
            pass
        gen.add_equilibrium(fps, rp, R1=R1, R2=R2)

        # Add EWS if available
        if "ews_report" in st.session_state and st.session_state["ews_report"] is not None:
            gen.add_warnings(st.session_state["ews_report"])

        # Add control results if available
        try:
            optimizer = ControlOptimizer(dict(p))
            ic = {"A": p.get("K_0", 1.7) * 0.5, "F": 0.1, "K": p.get("K_0", 1.7), "D": 0.0}
            ctrl_results = optimizer.compare_strategies(ic, n_years=50)
            feasible = [r for r in ctrl_results if r.feasible]
            rec = None
            if feasible:
                best = min(feasible, key=lambda r: r.cost_J)
                rec = f"Scenario {best.scenario} (cost J = {best.cost_J:.4f})"
            gen.add_control(ctrl_results, recommendation=rec)
        except Exception:
            pass

        html_report = gen.render()
        st.sidebar.download_button(
            "Download Report (.html)",
            data=html_report,
            file_name="alder-ipm-sim_report.html",
            mime="text/html",
            key="dl_report",
        )
    except Exception as exc:
        st.sidebar.error(f"Report generation failed: {exc}")

# ---------------------------------------------------------------------------
# Tab navigation
# ---------------------------------------------------------------------------

tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs([
    "Parameter Setup",
    "Simulation & Forecast",
    "Data Fitting",
    "Early Warning Signals",
    "Management Strategies",
    "Bifurcation Analysis",
    "Scenario Comparison",
])

# ===================================================================
# Page 1 -- Parameter Setup
# ===================================================================

with tab1:
    st.header("Parameter Setup")

    # --- R_P display at top ---
    params = st.session_state["params"]
    try:
        model_rp = AlderIPMSimModel(dict(params))
        R_P = model_rp.compute_R_P()
        rp_color = "green" if R_P > 1 else "red"
        rp_label = "Coexistence possible" if R_P > 1 else "Parasitoid cannot persist"
        st.markdown(
            _alert_css(rp_color, f"<b>R<sub>P</sub> = {R_P:.4f}</b> &mdash; {rp_label}"),
            unsafe_allow_html=True,
        )
    except Exception as exc:
        st.warning(f"Could not compute R_P: {exc}")

    # --- Real-time parameter validation warnings ---
    stab_warnings = _check_stability_warnings(params)
    for sw in stab_warnings:
        st.warning(sw)

    # --- Action buttons + Presets ---
    col_a, col_b, col_c, col_d = st.columns(4)
    with col_a:
        uploaded = st.file_uploader("Load from JSON", type=["json"], key="param_upload")
        if uploaded is not None:
            try:
                raw = json.load(uploaded)
                loaded = {}
                for k, v in raw.items():
                    key = _CALIBRATED_KEY_MAP.get(k, k)
                    if key in PARAM_REGISTRY:
                        loaded[key] = float(v)
                st.session_state["params"].update(loaded)
                st.success(f"Loaded {len(loaded)} parameters.")
                st.rerun()
            except Exception as exc:
                st.error(f"Failed to load JSON: {exc}")
    with col_b:
        if st.button("Reset to Defaults"):
            st.session_state["params"] = get_defaults()
            st.rerun()
    with col_c:
        if st.button("Load Calibrated Baseline"):
            try:
                cal = _load_calibrated_baseline()
                st.session_state["params"].update(cal)
                st.rerun()
            except Exception as exc:
                st.error(f"Could not load calibrated baseline: {exc}")
    with col_d:
        preset_choice = st.selectbox(
            "Parameter Presets",
            ["(select preset)"] + list(_PRESETS.keys()),
            key="preset_select",
            help="Load ecologically meaningful parameter combinations.",
        )
        if preset_choice != "(select preset)":
            # Show description of selected scenario
            _scenario = next(
                (v for v in PRESET_SCENARIOS.values() if v["name"] == preset_choice),
                None,
            )
            if _scenario:
                st.info(
                    f"**{_scenario['name']}** — {_scenario['description']}  \n"
                    f"Expected regime: *{_scenario['expected_regime']}* "
                    f"(Ref: {_scenario['manuscript_ref']})"
                )
            if st.button("Apply Preset", key="apply_preset"):
                preset_vals = _PRESETS[preset_choice]
                if preset_choice == "Baseline Calibrated":
                    st.session_state["params"] = get_defaults()
                st.session_state["params"].update(preset_vals)
                st.rerun()

    # --- Parameter sliders by category ---
    groups = _group_params()
    for cat_label, cat_params in groups.items():
        with st.expander(cat_label, expanded=True):
            for pname, pm in cat_params.items():
                col1, col2 = st.columns([3, 1])
                step = (pm.max_val - pm.min_val) / 200.0
                if step == 0:
                    step = 0.001
                with col1:
                    val = st.slider(
                        f"{pm.symbol}  ({pm.unit})",
                        min_value=float(pm.min_val),
                        max_value=float(pm.max_val),
                        value=float(st.session_state["params"].get(pname, pm.default)),
                        step=step,
                        key=f"slider_{pname}",
                        help=pm.description,
                    )
                    st.session_state["params"][pname] = val
                with col2:
                    st.markdown(f"**{val:.6g}**")

    # --- Mini radar chart: current vs defaults ---
    st.subheader("Parameter Comparison (Current vs Default)")
    defaults = get_defaults()
    radar_params = ["beta", "delta", "eta", "R_B", "sigma_A", "sigma_F", "phi", "T", "B_index"]
    radar_labels = [PARAM_REGISTRY[p].symbol for p in radar_params if p in PARAM_REGISTRY]
    radar_current = []
    radar_default = []
    for p in radar_params:
        if p not in PARAM_REGISTRY:
            continue
        pm = PARAM_REGISTRY[p]
        rng = pm.max_val - pm.min_val
        if rng > 0:
            radar_current.append((params.get(p, pm.default) - pm.min_val) / rng)
            radar_default.append((defaults[p] - pm.min_val) / rng)
        else:
            radar_current.append(0.5)
            radar_default.append(0.5)

    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=radar_current + [radar_current[0]],
        theta=radar_labels + [radar_labels[0]],
        fill="toself", name="Current", opacity=0.6,
    ))
    fig_radar.add_trace(go.Scatterpolar(
        r=radar_default + [radar_default[0]],
        theta=radar_labels + [radar_labels[0]],
        fill="toself", name="Default", opacity=0.4,
    ))
    fig_radar.update_layout(
        polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
        height=400, showlegend=True,
        title="Normalised parameter values (0=min, 1=max)",
    )
    st.plotly_chart(fig_radar, use_container_width=True)

    _download_params_button(st.session_state["params"], key="dl_p1")


# ===================================================================
# Page 2 -- Simulation & Forecast
# ===================================================================

with tab2:
    st.header("Simulation & Forecast")
    params = st.session_state["params"]

    col_ic1, col_ic2 = st.columns(2)
    with col_ic1:
        A0 = st.number_input(
            "A0 (initial beetle density)",
            value=params.get("K_0", 1.7) * 0.5,
            min_value=0.0, step=0.01, format="%.4f",
            help="Adult beetle density entering year 0.",
        )
        F0 = st.number_input(
            "F0 (initial parasitoid density)",
            value=0.1, min_value=0.0, step=0.01, format="%.4f",
            help="Adult parasitoid fly density entering year 0.",
        )
    with col_ic2:
        K0 = st.number_input(
            "K0 (initial carrying capacity)",
            value=params.get("K_0", 1.7),
            min_value=0.01, step=0.01, format="%.4f",
            help="Beetle carrying capacity at year 0 (undamaged canopy).",
        )
        D0 = st.number_input(
            "D0 (initial defoliation)",
            value=0.0, min_value=0.0, step=0.01, format="%.4f",
            help="Cumulative defoliation entering year 0.",
        )

    n_years = st.slider("Number of years", 1, 200, 50, key="sim_years")

    if st.button("Run Simulation", key="run_sim"):
        with st.spinner("Simulating..."):
            model = AlderIPMSimModel(dict(params))
            result = model.simulate(
                A0=A0, F0=F0, K0=K0, D0=D0, n_years=n_years,
                store_within_season=True,
            )
            years = np.arange(n_years + 1)

            # Store for within-season viewer
            st.session_state["sim_result"] = result
            st.session_state["sim_n_years"] = n_years

            # --- Regime Summary Card ---
            st.subheader("Regime Summary")
            A_end, F_end = result["A"][-1], result["F"][-1]
            K_end, D_end = result["K"][-1], result["D"][-1]
            eq_class = AlderIPMSimModel._classify_equilibrium(A_end, F_end, K_end, D_end, 1e-6)

            try:
                R_P = model.compute_R_P()
                jac = model.compute_jacobian(A_end, F_end, K_end, D_end)
                rho_star = float(np.max(np.abs(np.linalg.eigvals(jac))))
            except Exception:
                R_P = float("nan")
                rho_star = float("nan")

            try:
                fps = model.find_fixed_points()
                coex_fp = next((f for f in fps if f.equilibrium_class == "coexistence"), None)
                r1 = model.compute_R1(fp=coex_fp) if coex_fp else float("nan")
                r2 = model.compute_R2(fp=coex_fp) if coex_fp else float("nan")
            except Exception:
                r1, r2 = float("nan"), float("nan")

            color = _regime_color(eq_class)
            em = _regime_emoji(eq_class)

            m1, m2, m3, m4, m5 = st.columns(5)
            m1.metric("Regime", f"{em} {eq_class.replace('_', ' ').title()}")
            m2.metric("R_P", f"{R_P:.4f}")
            m3.metric("rho*", f"{rho_star:.4f}")
            m4.metric("R1 (Resistance)", f"{r1:.4f}" if not np.isnan(r1) else "N/A")
            m5.metric("R2 (Resilience)", f"{r2:.4f}" if not np.isnan(r2) else "N/A")

            st.markdown(
                _alert_css(color,
                    f"<b>Regime: {eq_class.replace('_', ' ').title()}</b><br>"
                    f"R<sub>P</sub> = {R_P:.4f} &mdash; "
                    f"{'Parasitoid can invade and persist.' if R_P > 1 else 'Parasitoid cannot persist; augmentation needed.'}"
                ),
                unsafe_allow_html=True,
            )

            # --- Multi-panel time-series with color-coded backgrounds ---
            st.subheader("Time Series")
            fig = make_subplots(rows=2, cols=2, shared_xaxes=True,
                                subplot_titles=["Beetle density (A)", "Parasitoid density (F)",
                                                 "Carrying capacity (K)", "Cumulative defoliation (D)"])

            # Determine regime zones for background colouring
            for idx, (key, row, col) in enumerate([("A", 1, 1), ("F", 1, 2), ("K", 2, 1), ("D", 2, 2)]):
                arr = result[key]
                fig.add_trace(go.Scatter(x=years, y=arr, mode="lines", name=key), row=row, col=col)

                # Color-code background by regime status per year
                # Use D and F to classify: green=coexistence, yellow=warning, red=degraded
                if key == "D":
                    D_crit = params.get("D_crit", 0.5)
                    for yr_i in range(len(arr)):
                        if arr[yr_i] > D_crit:
                            fig.add_vrect(
                                x0=yr_i - 0.5, x1=yr_i + 0.5,
                                fillcolor="rgba(255,0,0,0.05)", line_width=0,
                                row=row, col=col,
                            )
                        elif arr[yr_i] > D_crit * 0.7:
                            fig.add_vrect(
                                x0=yr_i - 0.5, x1=yr_i + 0.5,
                                fillcolor="rgba(255,255,0,0.05)", line_width=0,
                                row=row, col=col,
                            )

            fig.update_layout(height=600, showlegend=False)
            fig.update_xaxes(title_text="Year", row=2)
            st.plotly_chart(fig, use_container_width=True)

            # --- Phase Portraits ---
            st.subheader("Phase Portraits")
            pp_col1, pp_col2, pp_col3 = st.columns(3)

            with pp_col1:
                fig_pp1 = go.Figure()
                fig_pp1.add_trace(go.Scatter(
                    x=result["A"], y=result["F"], mode="lines+markers",
                    marker=dict(size=3, color=years, colorscale="Viridis", showscale=True,
                                colorbar=dict(title="Year")),
                    line=dict(width=1, color="grey"),
                    name="A vs F",
                ))
                # Mark start and end
                fig_pp1.add_trace(go.Scatter(
                    x=[result["A"][0]], y=[result["F"][0]],
                    mode="markers", marker=dict(size=10, color="green", symbol="star"),
                    name="Start", showlegend=True,
                ))
                fig_pp1.add_trace(go.Scatter(
                    x=[result["A"][-1]], y=[result["F"][-1]],
                    mode="markers", marker=dict(size=10, color="red", symbol="x"),
                    name="End", showlegend=True,
                ))
                fig_pp1.update_layout(
                    xaxis_title="Beetle density (A)", yaxis_title="Parasitoid density (F)",
                    title="A vs F", height=350,
                )
                st.plotly_chart(fig_pp1, use_container_width=True)

            with pp_col2:
                fig_pp2 = go.Figure()
                fig_pp2.add_trace(go.Scatter(
                    x=result["A"], y=result["D"], mode="lines+markers",
                    marker=dict(size=3, color=years, colorscale="Viridis", showscale=False),
                    line=dict(width=1, color="grey"), name="A vs D",
                ))
                fig_pp2.add_trace(go.Scatter(
                    x=[result["A"][0]], y=[result["D"][0]],
                    mode="markers", marker=dict(size=10, color="green", symbol="star"),
                    name="Start",
                ))
                fig_pp2.add_trace(go.Scatter(
                    x=[result["A"][-1]], y=[result["D"][-1]],
                    mode="markers", marker=dict(size=10, color="red", symbol="x"),
                    name="End",
                ))
                fig_pp2.update_layout(
                    xaxis_title="Beetle density (A)", yaxis_title="Defoliation (D)",
                    title="A vs D", height=350,
                )
                st.plotly_chart(fig_pp2, use_container_width=True)

            with pp_col3:
                fig_pp3 = go.Figure()
                fig_pp3.add_trace(go.Scatter(
                    x=result["K"], y=result["D"], mode="lines+markers",
                    marker=dict(size=3, color=years, colorscale="Viridis", showscale=False),
                    line=dict(width=1, color="grey"), name="K vs D",
                ))
                fig_pp3.add_trace(go.Scatter(
                    x=[result["K"][0]], y=[result["D"][0]],
                    mode="markers", marker=dict(size=10, color="green", symbol="star"),
                    name="Start",
                ))
                fig_pp3.add_trace(go.Scatter(
                    x=[result["K"][-1]], y=[result["D"][-1]],
                    mode="markers", marker=dict(size=10, color="red", symbol="x"),
                    name="End",
                ))
                fig_pp3.update_layout(
                    xaxis_title="Carrying capacity (K)", yaxis_title="Defoliation (D)",
                    title="K vs D", height=350,
                )
                st.plotly_chart(fig_pp3, use_container_width=True)

            # --- Equilibrium analysis ---
            st.subheader("Equilibrium Analysis")
            try:
                fps = model.find_fixed_points()
                if fps:
                    fp_data = []
                    for fp in fps:
                        r1_fp = model.compute_R1(fp=fp)
                        r2_fp = model.compute_R2(fp=fp)
                        fp_data.append({
                            "Class": fp.equilibrium_class,
                            "Stable": fp.stable,
                            "A*": f"{fp.A_star:.4f}",
                            "F*": f"{fp.F_star:.4f}",
                            "K*": f"{fp.K_star:.4f}",
                            "D*": f"{fp.D_star:.4f}",
                            "|lambda_dom|": f"{fp.dominant_eigenvalue:.4f}",
                            "Bifurcation": fp.bifurcation_type,
                            "R1 (Resistance)": f"{r1_fp:.4f}" if not np.isnan(r1_fp) else "N/A",
                            "R2 (Resilience)": f"{r2_fp:.4f}" if not np.isnan(r2_fp) else "N/A",
                        })
                    st.dataframe(pd.DataFrame(fp_data), use_container_width=True)
                else:
                    st.info("No fixed points found.")
            except Exception as exc:
                st.warning(f"Equilibrium search failed: {exc}")

    # --- Within-season dynamics viewer ---
    with st.expander("Within-Season Dynamics", expanded=False):
        st.markdown(
            "Select a year to view the within-season ODE trajectories "
            "(S, I, F, D as functions of day within the larval vulnerability window). "
            "This reveals **how** parasitism and bird predation interact within "
            "a single season -- the mechanistic core of the model.",
        )
        if "sim_result" in st.session_state and "within_season" in st.session_state["sim_result"]:
            ws_result = st.session_state["sim_result"]
            ws_sols = ws_result["within_season"]
            ws_max = len(ws_sols) - 1
            if ws_max >= 0:
                ws_year = st.slider("Select year", 0, ws_max, 0, key="ws_year_slider")

                # Use the model method for rich trajectory data
                ws_model = AlderIPMSimModel(dict(params))
                traj = ws_model.get_season_trajectory(ws_result, ws_year)

                # 4-panel plot
                fig_ws = make_subplots(
                    rows=2, cols=2, shared_xaxes=True,
                    subplot_titles=[
                        "Susceptible larvae S(\u03c4)", "Parasitised larvae I(\u03c4)",
                        "Parasitoid flies F(\u03c4)", "Cumulative defoliation D(\u03c4)",
                    ],
                )
                for i, (key, lbl, row, col) in enumerate([
                    ("S", "S", 1, 1), ("I", "I", 1, 2),
                    ("F", "F", 2, 1), ("D", "D", 2, 2),
                ]):
                    fig_ws.add_trace(
                        go.Scatter(x=traj["tau"], y=traj[key], mode="lines", name=lbl),
                        row=row, col=col,
                    )

                # Annotate peak parasitism on S panel
                fig_ws.add_trace(
                    go.Scatter(
                        x=[traj["peak_parasitism_day"]],
                        y=[float(traj["S"][np.argmin(np.abs(traj["tau"] - traj["peak_parasitism_day"]))])],
                        mode="markers+text",
                        marker=dict(size=10, color="red", symbol="triangle-down"),
                        text=["Peak parasitism"],
                        textposition="top center",
                        showlegend=False,
                    ),
                    row=1, col=1,
                )

                # Annotate peak defoliation rate on D panel
                fig_ws.add_trace(
                    go.Scatter(
                        x=[traj["peak_defoliation_rate_day"]],
                        y=[float(traj["D"][np.argmin(np.abs(traj["tau"] - traj["peak_defoliation_rate_day"]))])],
                        mode="markers+text",
                        marker=dict(size=10, color="orange", symbol="triangle-up"),
                        text=["Peak defol. rate"],
                        textposition="top center",
                        showlegend=False,
                    ),
                    row=2, col=2,
                )

                fig_ws.update_layout(height=550, showlegend=False)
                fig_ws.update_xaxes(title_text="Day (\u03c4)", row=2)
                st.plotly_chart(fig_ws, use_container_width=True)

                # Functional response curve
                st.markdown("**Parasitoid functional response** (Holling Type II): "
                            "per-parasitoid attack rate as a function of susceptible larval density.")
                fr = traj["functional_response"]
                fig_fr = go.Figure()
                fig_fr.add_trace(go.Scatter(
                    x=fr["S_range"], y=fr["fr"],
                    mode="lines", name="Functional response",
                    line=dict(width=2),
                ))
                # Mark the actual operating point at several time snapshots
                n_pts = len(traj["tau"])
                sample_idx = np.linspace(0, n_pts - 1, min(8, n_pts), dtype=int)
                fig_fr.add_trace(go.Scatter(
                    x=traj["S"][sample_idx],
                    y=(params.get("beta", 0.5) * traj["S"][sample_idx]
                       / (1.0 + params.get("h", 0.1) * traj["S"][sample_idx])),
                    mode="markers",
                    marker=dict(size=8, color="red"),
                    name="Operating points",
                    text=[f"Day {traj['tau'][i]:.0f}" for i in sample_idx],
                ))
                fig_fr.update_layout(
                    height=350,
                    xaxis_title="Susceptible larval density S",
                    yaxis_title="Per-capita attack rate \u03b2S/(1+hS)",
                    showlegend=True,
                )
                st.plotly_chart(fig_fr, use_container_width=True)
        else:
            st.info("Run a simulation first to view within-season dynamics.")

    _download_params_button(st.session_state["params"], key="dl_p2")

# ===================================================================
# Page 3 -- Data Fitting
# ===================================================================

with tab3:
    st.header("Data Fitting")
    params = st.session_state["params"]

    st.markdown(
        "Upload a CSV with columns for time and state variables. "
        "Example format: `year, A, F, K, D` (partial observations are supported)."
    )

    uploaded_data = st.file_uploader("Upload CSV data", type=["csv"], key="fit_upload")

    if uploaded_data is not None:
        df = pd.read_csv(uploaded_data)

        # Data preview and quality summary
        st.subheader("Data Preview")
        st.dataframe(df.head(10), use_container_width=True)
        q1, q2, q3, q4 = st.columns(4)
        q1.metric("Rows", len(df))
        q2.metric("Columns", len(df.columns))
        n_missing = int(df.isnull().sum().sum())
        q3.metric("Missing values", n_missing)
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        q4.metric("Numeric columns", len(numeric_cols))
        if len(df) < 10:
            st.warning("Short time series (< 10 points). Parameter estimates may be unreliable.")

        columns = list(df.columns)
        # Auto-detect likely column mappings
        _auto_map = {}
        for sv in ["A", "F", "K", "D"]:
            for col in columns:
                if col.strip().upper() == sv or col.strip().lower() in {
                    "beetle" if sv == "A" else "",
                    "parasitoid" if sv == "F" else "",
                    "capacity" if sv == "K" else "",
                    "defoliation" if sv == "D" else "",
                }:
                    _auto_map[sv] = col
                    break

        col_f1, col_f2 = st.columns(2)
        with col_f1:
            # Auto-detect time column
            _time_default = 0
            for i, c in enumerate(columns):
                if c.strip().lower() in ("year", "time", "t", "date"):
                    _time_default = i
                    break
            time_col = st.selectbox("Time column", columns, index=_time_default)
            state_options = ["A", "F", "K", "D"]
            col_map = {}
            for sv in state_options:
                _default_idx = 0
                if sv in _auto_map:
                    try:
                        _default_idx = columns.index(_auto_map[sv]) + 1
                    except ValueError:
                        _default_idx = columns.index(sv) + 1 if sv in columns else 0
                elif sv in columns:
                    _default_idx = columns.index(sv) + 1
                match = st.selectbox(
                    f"Column for {sv}",
                    ["(none)"] + columns,
                    index=_default_idx,
                    key=f"col_{sv}",
                )
                if match != "(none)":
                    col_map[sv] = match
        with col_f2:
            timestep = st.selectbox("Timestep", ["annual", "seasonal"])
            fit_param_options = sorted(PARAM_REGISTRY.keys())
            fit_params = st.multiselect(
                "Parameters to fit",
                fit_param_options,
                default=["beta", "mu_S", "delta", "R_B", "phi", "kappa"],
            )
            use_bootstrap = st.checkbox(
                "Bootstrap confidence intervals",
                value=False,
                help="Use bootstrap resampling for CI (slower but more robust).",
            )

        if st.button("Fit Model", key="run_fit"):
            if not col_map:
                st.error("Select at least one state column mapping.")
            elif not fit_params:
                st.error("Select at least one parameter to fit.")
            else:
                with st.spinner("Fitting model (this may take a moment)..."):
                    try:
                        model = AlderIPMSimModel(dict(params))
                        fitter = ModelFitter(model)
                        data_dict = {c: df[c].values.tolist() for c in df.columns}
                        prepared = fitter.prepare_data(
                            data_dict,
                            time_col=time_col,
                            state_cols=col_map if col_map else None,
                            timestep=timestep,
                        )
                        fit_result = fitter.fit(prepared, fit_params=fit_params)

                        # Bootstrap CI if requested
                        if use_bootstrap:
                            with st.spinner("Computing bootstrap CIs..."):
                                bs_result = fitter.bootstrap_ci(
                                    fit_result, prepared, n_bootstrap=200,
                                )
                                bs_ci = bs_result.ci
                                st.info(
                                    f"Bootstrap: {bs_result.n_successful}/{bs_result.n_bootstrap} "
                                    f"resamples succeeded."
                                )
                        else:
                            bs_ci = None

                        # --- Fitted parameters table ---
                        st.subheader("Fitted Parameters")
                        fp_rows = []
                        for name, val in fit_result.fitted_params.items():
                            ci = fit_result.confidence_intervals.get(name, (val, val))
                            row = {
                                "Parameter": name,
                                "Value": f"{val:.6f}",
                                "95% CI Low": f"{ci[0]:.6f}",
                                "95% CI High": f"{ci[1]:.6f}",
                            }
                            if bs_ci and name in bs_ci:
                                row["Bootstrap CI Low"] = f"{bs_ci[name][0]:.6f}"
                                row["Bootstrap CI High"] = f"{bs_ci[name][1]:.6f}"
                            fp_rows.append(row)
                        st.dataframe(pd.DataFrame(fp_rows), use_container_width=True)

                        # --- Goodness of fit ---
                        st.subheader("Diagnostics")
                        diag = ModelFitter.residual_diagnostics(fit_result)
                        met1, met2, met3, met4 = st.columns(4)
                        met1.metric("R-squared", f"{fit_result.r_squared:.4f}")
                        met2.metric("AIC", f"{fit_result.AIC:.2f}")
                        met3.metric("BIC", f"{fit_result.BIC:.2f}")
                        met4.metric("Durbin-Watson", f"{diag.durbin_watson:.3f}",
                                    help="~2 = no autocorrelation, <1 = positive, >3 = negative")

                        # --- Observed vs Predicted ---
                        st.subheader("Observed vs Predicted")
                        fitted_params_full = dict(params)
                        fitted_params_full.update(fit_result.fitted_params)
                        mdl_pred = AlderIPMSimModel(fitted_params_full)
                        n_obs = len(df)
                        ic = fitter._initial_conditions_from_data(prepared)
                        if timestep == "annual":
                            sim = mdl_pred.simulate(
                                A0=ic["A"], F0=ic["F"], K0=ic["K"], D0=ic["D"],
                                n_years=n_obs - 1,
                            )
                            fig_fit = make_subplots(
                                rows=1, cols=len(col_map),
                                subplot_titles=[f"{sv}" for sv in col_map],
                            )
                            for i, (sv, col_name) in enumerate(col_map.items()):
                                obs_vals = df[col_name].values
                                pred_vals = sim[sv][:n_obs]
                                times = df[time_col].values
                                fig_fit.add_trace(
                                    go.Scatter(x=times, y=obs_vals, mode="markers",
                                               name=f"{sv} observed"), row=1, col=i + 1)
                                fig_fit.add_trace(
                                    go.Scatter(x=times, y=pred_vals, mode="lines",
                                               name=f"{sv} predicted"), row=1, col=i + 1)
                            fig_fit.update_layout(height=400)
                            st.plotly_chart(fig_fit, use_container_width=True)

                        # --- Residual diagnostics ---
                        st.subheader("Residual Diagnostics")
                        res_col1, res_col2 = st.columns(2)

                        with res_col1:
                            fig_res = go.Figure()
                            fig_res.add_trace(go.Histogram(
                                x=fit_result.residuals, nbinsx=30, name="Residuals",
                            ))
                            fig_res.update_layout(
                                xaxis_title="Residual", yaxis_title="Count",
                                height=300, title="Residual Histogram",
                            )
                            st.plotly_chart(fig_res, use_container_width=True)

                        with res_col2:
                            # Residual ACF plot from diagnostics
                            if len(diag.acf_lags) > 1:
                                fig_acf = go.Figure()
                                fig_acf.add_trace(go.Bar(
                                    x=diag.acf_lags.tolist(),
                                    y=diag.acf_values.tolist(), name="ACF",
                                ))
                                ci_bound = 1.96 / np.sqrt(len(fit_result.residuals))
                                fig_acf.add_hline(y=ci_bound, line_dash="dash",
                                                  line_color="red", opacity=0.5)
                                fig_acf.add_hline(y=-ci_bound, line_dash="dash",
                                                  line_color="red", opacity=0.5)
                                fig_acf.update_layout(
                                    xaxis_title="Lag", yaxis_title="ACF",
                                    height=300, title="Residual Autocorrelation",
                                )
                                st.plotly_chart(fig_acf, use_container_width=True)

                        # QQ plot
                        res_col3, res_col4 = st.columns(2)
                        with res_col3:
                            fig_qq = go.Figure()
                            fig_qq.add_trace(go.Scatter(
                                x=diag.qq_theoretical, y=diag.qq_observed,
                                mode="markers", name="Residuals",
                            ))
                            qq_min = min(diag.qq_theoretical.min(), diag.qq_observed.min())
                            qq_max = max(diag.qq_theoretical.max(), diag.qq_observed.max())
                            fig_qq.add_trace(go.Scatter(
                                x=[qq_min, qq_max], y=[qq_min, qq_max],
                                mode="lines", name="Reference",
                                line=dict(dash="dash", color="red"),
                            ))
                            fig_qq.update_layout(
                                xaxis_title="Theoretical Quantiles",
                                yaxis_title="Sample Quantiles",
                                height=300, title="Normal Q-Q Plot",
                            )
                            st.plotly_chart(fig_qq, use_container_width=True)

                        with res_col4:
                            # Convergence info
                            st.markdown("**Convergence Info**")
                            ci_info = fit_result.convergence_info
                            conv_rows = []
                            if "success" in ci_info:
                                conv_rows.append({"Metric": "Converged", "Value": str(ci_info["success"])})
                            if "message" in ci_info:
                                conv_rows.append({"Metric": "Message", "Value": str(ci_info["message"])})
                            if "gradient_norm" in ci_info and ci_info["gradient_norm"] is not None:
                                conv_rows.append({"Metric": "Gradient norm", "Value": f"{ci_info['gradient_norm']:.2e}"})
                            if "nfev" in ci_info:
                                conv_rows.append({"Metric": "Function evaluations", "Value": str(ci_info["nfev"])})
                            if conv_rows:
                                st.dataframe(pd.DataFrame(conv_rows), use_container_width=True, hide_index=True)

                        # --- Correlation matrix heatmap ---
                        if (fit_result.param_correlation is not None
                                and len(fit_result.fitted_params) > 1):
                            st.subheader("Parameter Correlation Matrix")
                            st.markdown(
                                "Computed from the Fisher information matrix at the optimum.",
                            )
                            pnames = fit_result.param_names_order or list(fit_result.fitted_params.keys())
                            corr_matrix = fit_result.param_correlation

                            fig_corr = go.Figure(data=go.Heatmap(
                                z=corr_matrix, x=pnames, y=pnames,
                                colorscale="RdBu", zmid=0, zmin=-1, zmax=1,
                                text=np.round(corr_matrix, 2),
                                texttemplate="%{text}",
                            ))
                            fig_corr.update_layout(
                                height=400, title="Parameter Correlation Heatmap",
                            )
                            st.plotly_chart(fig_corr, use_container_width=True)

                        # --- Parameter identifiability: profile likelihood ---
                        st.subheader("Parameter Identifiability (Profile Likelihood)")
                        st.markdown(
                            "Shows how the objective function changes when each "
                            "fitted parameter is varied around its optimum. "
                            "Flat profiles indicate poor identifiability.",
                        )
                        n_profile_pts = 11
                        fitted_p = fit_result.fitted_params
                        profile_params = list(fitted_p.keys())[:6]  # limit to first 6

                        n_cols = min(3, len(profile_params))
                        if n_cols > 0:
                            profile_fig = make_subplots(
                                rows=(len(profile_params) + n_cols - 1) // n_cols,
                                cols=n_cols,
                                subplot_titles=profile_params,
                            )
                            for p_idx, pn in enumerate(profile_params):
                                row_idx = p_idx // n_cols + 1
                                col_idx = p_idx % n_cols + 1
                                pm = PARAM_REGISTRY.get(pn)
                                if pm is None:
                                    continue
                                opt_val = fitted_p[pn]
                                ci = fit_result.confidence_intervals.get(pn, (opt_val, opt_val))
                                ci_width = max(ci[1] - ci[0], (pm.max_val - pm.min_val) * 0.1)
                                lo = max(pm.min_val, opt_val - ci_width)
                                hi = min(pm.max_val, opt_val + ci_width)
                                sweep_vals = np.linspace(lo, hi, n_profile_pts)
                                profile_costs = []
                                for sv in sweep_vals:
                                    test_params = dict(fitted_params_full)
                                    test_params[pn] = sv
                                    try:
                                        test_model = AlderIPMSimModel(test_params)
                                        test_sim = test_model.simulate(
                                            A0=ic["A"], F0=ic["F"],
                                            K0=ic["K"], D0=ic["D"],
                                            n_years=n_obs - 1,
                                        )
                                        # Compute SSE
                                        sse = 0.0
                                        for sv_name, col_name in col_map.items():
                                            obs = df[col_name].values
                                            pred = test_sim[sv_name][:n_obs]
                                            sse += np.sum((obs - pred) ** 2)
                                        profile_costs.append(sse)
                                    except Exception:
                                        profile_costs.append(float("nan"))

                                profile_fig.add_trace(
                                    go.Scatter(
                                        x=sweep_vals, y=profile_costs,
                                        mode="lines+markers", name=pn,
                                        showlegend=False,
                                    ),
                                    row=row_idx, col=col_idx,
                                )
                                # Mark optimum
                                profile_fig.add_trace(
                                    go.Scatter(
                                        x=[opt_val],
                                        y=[min(c for c in profile_costs if np.isfinite(c))] if any(np.isfinite(c) for c in profile_costs) else [0],
                                        mode="markers",
                                        marker=dict(size=10, color="red", symbol="star"),
                                        showlegend=False,
                                    ),
                                    row=row_idx, col=col_idx,
                                )

                            n_rows_profile = (len(profile_params) + n_cols - 1) // n_cols
                            profile_fig.update_layout(
                                height=300 * n_rows_profile,
                                title="Profile Likelihood (SSE vs parameter value)",
                            )
                            st.plotly_chart(profile_fig, use_container_width=True)

                        # --- Regime forecast ---
                        st.subheader("Regime Forecast from Fitted Parameters")
                        try:
                            regime = fitter.forecast_regime(fit_result)
                            color = _regime_color(regime["equilibrium_class"])
                            st.markdown(
                                _alert_css(color, regime["interpretation"]),
                                unsafe_allow_html=True,
                            )
                        except Exception as exc:
                            st.warning(f"Regime forecast failed: {exc}")

                        # --- Download ---
                        dl_data = {
                            "fitted_params": fit_result.fitted_params,
                            "r_squared": fit_result.r_squared,
                            "AIC": fit_result.AIC,
                            "BIC": fit_result.BIC,
                            "confidence_intervals": {
                                k: list(v) for k, v in fit_result.confidence_intervals.items()
                            },
                        }
                        st.download_button(
                            "Download Results (JSON)",
                            data=json.dumps(dl_data, indent=2),
                            file_name="fit_results.json",
                            mime="application/json",
                            key="dl_fit_results",
                        )

                        # Store fit result for EWS page
                        st.session_state["fit_data"] = df
                        st.session_state["fit_result"] = fit_result

                    except Exception as exc:
                        st.error(f"Fitting failed: {exc}")

    _download_params_button(st.session_state["params"], key="dl_p3")


# ===================================================================
# Page 4 -- Early Warning Signals
# ===================================================================

with tab4:
    st.header("Early Warning Signals")

    ews_source = st.radio(
        "Data source",
        ["Upload CSV", "Use data from Data Fitting tab"],
        key="ews_source",
    )

    ews_df = None
    if ews_source == "Upload CSV":
        ews_upload = st.file_uploader("Upload time series CSV", type=["csv"], key="ews_upload")
        if ews_upload is not None:
            ews_df = pd.read_csv(ews_upload)
    else:
        if "fit_data" in st.session_state:
            ews_df = st.session_state["fit_data"]
            st.success("Using data from Data Fitting tab.")
        else:
            st.info("No data available from the Data Fitting tab. Fit a model first or upload a CSV.")

    if ews_df is not None:
        st.dataframe(ews_df.head(), use_container_width=True)
        numeric_cols = [c for c in ews_df.columns if pd.api.types.is_numeric_dtype(ews_df[c])]
        col_ews = st.selectbox("Variable to analyse", numeric_cols, key="ews_col")

        col_e1, col_e2 = st.columns(2)
        with col_e1:
            window_size = st.slider(
                "Window size",
                min_value=3,
                max_value=max(len(ews_df) - 1, 4),
                value=max(int(len(ews_df) * 0.5), 3),
                key="ews_window",
            )
        with col_e2:
            detrend = st.selectbox("Detrending method", ["gaussian", "linear", "loess"], key="ews_detrend")

        if st.button("Run EWS Analysis", key="run_ews"):
            ts = ews_df[col_ews].values.astype(float)
            if len(ts) < 6:
                st.error("Time series too short (need at least 6 observations).")
            else:
                with st.spinner("Computing early warning signals..."):
                    detector = EarlyWarningDetector(window_size=window_size, detrend_method=detrend)
                    report = detector.detect_regime_shift(ts)

                    # --- 4-panel plot ---
                    fig_ews = make_subplots(
                        rows=2, cols=2,
                        subplot_titles=["Original time series", "Rolling variance",
                                         "Rolling autocorrelation", "Rolling skewness"],
                    )
                    fig_ews.add_trace(
                        go.Scatter(y=ts, mode="lines", name=col_ews), row=1, col=1)
                    fig_ews.add_trace(
                        go.Scatter(y=report.indicators["variance"], mode="lines", name="Variance"),
                        row=1, col=2)
                    fig_ews.add_trace(
                        go.Scatter(y=report.indicators["autocorrelation"], mode="lines", name="AR(1)"),
                        row=2, col=1)
                    fig_ews.add_trace(
                        go.Scatter(y=report.indicators["skewness"], mode="lines", name="Skewness"),
                        row=2, col=2)
                    fig_ews.update_layout(height=600, showlegend=False)
                    st.plotly_chart(fig_ews, use_container_width=True)

                    # --- Spectral reddening indicator ---
                    st.subheader("Spectral Reddening Indicator")
                    st.markdown(
                        "Power spectrum shift toward lower frequencies indicates "
                        "critical slowing down (spectral reddening).",
                    )
                    residuals_ews = detector.detrend(ts)
                    n_ts = len(residuals_ews)
                    if n_ts > 10:
                        # Compute power spectrum
                        freqs = np.fft.rfftfreq(n_ts, d=1.0)
                        power = np.abs(np.fft.rfft(residuals_ews)) ** 2
                        # Split into first and second half for comparison
                        half = n_ts // 2
                        res_first = residuals_ews[:half]
                        res_second = residuals_ews[half:]

                        freqs1 = np.fft.rfftfreq(len(res_first), d=1.0)
                        power1 = np.abs(np.fft.rfft(res_first)) ** 2
                        freqs2 = np.fft.rfftfreq(len(res_second), d=1.0)
                        power2 = np.abs(np.fft.rfft(res_second)) ** 2

                        spec_col1, spec_col2 = st.columns(2)
                        with spec_col1:
                            fig_spec = go.Figure()
                            fig_spec.add_trace(go.Scatter(
                                x=freqs1[1:], y=power1[1:], mode="lines",
                                name="First half", line=dict(color="blue"),
                            ))
                            fig_spec.add_trace(go.Scatter(
                                x=freqs2[1:], y=power2[1:], mode="lines",
                                name="Second half", line=dict(color="red"),
                            ))
                            fig_spec.update_layout(
                                xaxis_title="Frequency", yaxis_title="Power",
                                title="Power Spectrum (first vs second half)",
                                height=350,
                            )
                            st.plotly_chart(fig_spec, use_container_width=True)

                        with spec_col2:
                            # Spectral exponent comparison
                            if len(freqs1) > 3 and len(freqs2) > 3:
                                from scipy.stats import linregress
                                log_f1 = np.log10(freqs1[1:] + 1e-10)
                                log_p1 = np.log10(power1[1:] + 1e-10)
                                log_f2 = np.log10(freqs2[1:] + 1e-10)
                                log_p2 = np.log10(power2[1:] + 1e-10)
                                slope1, _, _, _, _ = linregress(log_f1, log_p1)
                                slope2, _, _, _, _ = linregress(log_f2, log_p2)

                                delta_slope = slope2 - slope1
                                reddening = delta_slope < -0.3

                                fig_gauge = go.Figure(go.Indicator(
                                    mode="gauge+number+delta",
                                    value=slope2,
                                    delta={"reference": slope1, "decreasing": {"color": "red"}},
                                    title={"text": "Spectral Exponent"},
                                    gauge={
                                        "axis": {"range": [-4, 1]},
                                        "bar": {"color": "darkred" if reddening else "darkblue"},
                                        "steps": [
                                            {"range": [-4, -2], "color": "lightcoral"},
                                            {"range": [-2, -0.5], "color": "lightyellow"},
                                            {"range": [-0.5, 1], "color": "lightgreen"},
                                        ],
                                        "threshold": {
                                            "line": {"color": "black", "width": 4},
                                            "thickness": 0.75, "value": slope1,
                                        },
                                    },
                                ))
                                fig_gauge.update_layout(height=300)
                                st.plotly_chart(fig_gauge, use_container_width=True)

                                if reddening:
                                    st.warning(
                                        f"Spectral reddening detected: exponent shifted from "
                                        f"{slope1:.2f} to {slope2:.2f} (delta = {delta_slope:.2f})."
                                    )
                                else:
                                    st.success("No significant spectral reddening detected.")

                    # --- Kendall tau table ---
                    st.subheader("Kendall Tau Trend Tests")
                    kt_rows = []
                    for name, res in report.kendall_results.items():
                        sig = "Yes" if res["p_value"] < 0.05 else "No"
                        kt_rows.append({
                            "Indicator": name.capitalize(),
                            "Kendall tau": f"{res['tau']:+.4f}",
                            "p-value": f"{res['p_value']:.4f}",
                            "Significant (p<0.05)": sig,
                        })
                    st.dataframe(pd.DataFrame(kt_rows), use_container_width=True)

                    # --- Alert box with specific management recommendations ---
                    st.subheader("Alert")
                    alert_color = report.alert_level
                    st.markdown(
                        _alert_css(alert_color, f"<b>{report.alert_level.upper()} ALERT</b><br>{report.interpretation}"),
                        unsafe_allow_html=True,
                    )

                    # --- Specific recommendations based on trending parameters ---
                    st.subheader("Management Recommendations")
                    trending_indicators = []
                    for iname, ires in report.kendall_results.items():
                        if ires["p_value"] < 0.05 and ires["tau"] > 0.2:
                            trending_indicators.append(iname)

                    if not trending_indicators:
                        st.markdown(
                            "- Continue routine annual monitoring of beetle larval density.\n"
                            "- Maintain current parasitoid habitat conservation measures.\n"
                            "- Re-run EWS analysis after each new season of data."
                        )
                    else:
                        recs = []
                        if "variance" in trending_indicators:
                            recs.append(
                                "**Rising variance** detected -- the system is amplifying "
                                "perturbations. Consider increasing parasitoid augmentation "
                                "releases (u_P) to stabilise beetle populations."
                            )
                        if "autocorrelation" in trending_indicators:
                            recs.append(
                                "**Rising autocorrelation** detected -- recovery from "
                                "perturbations is slowing. Evaluate bird habitat quality "
                                "(nest boxes, hedgerows) and prepare for Strategy B or C."
                            )
                        if "skewness" in trending_indicators:
                            recs.append(
                                "**Rising skewness** detected -- the system is flickering "
                                "toward an alternative state. This is an advanced warning; "
                                "consider emergency canopy protection for high-value stands."
                            )
                        if "kurtosis" in trending_indicators:
                            recs.append(
                                "**Rising kurtosis** detected -- extreme fluctuations are "
                                "becoming more frequent. Immediate intensive monitoring "
                                "and contingency planning recommended."
                            )
                        for r in recs:
                            st.markdown(f"- {r}")

                    # Store report for PRCC section
                    st.session_state["ews_report"] = report

    # --- PRCC Sensitivity Analysis ---
    st.markdown("---")
    st.subheader("LHS-PRCC Sensitivity Analysis")
    st.markdown(
        "Latin Hypercube Sampling with Partial Rank Correlation Coefficients: "
        "identifies which parameters most strongly influence the dominant "
        "eigenvalue rho* (proximity to tipping point).",
    )

    prcc_col1, prcc_col2 = st.columns(2)
    with prcc_col1:
        prcc_n_samples = st.slider(
            "Number of LHS samples",
            min_value=50, max_value=500, value=100, step=50,
            key="prcc_samples",
            help="More samples = more accurate but slower. 100-200 is usually sufficient.",
        )
    with prcc_col2:
        prcc_seed = st.number_input(
            "Random seed", value=42, step=1, key="prcc_seed",
            help="Fix the seed for reproducible results.",
        )

    if st.button("Run PRCC Analysis", key="run_prcc"):
        with st.spinner(f"Running LHS-PRCC with {prcc_n_samples} samples (this may take a while)..."):
            prcc_progress = st.progress(0.0, text="Initialising LHS-PRCC analysis...")
            try:
                prcc_model = AlderIPMSimModel(dict(st.session_state["params"]))
                prcc_detector = EarlyWarningDetector()
                prcc_result = prcc_detector.lhs_prcc_analysis(
                    prcc_model,
                    n_samples=prcc_n_samples,
                    seed=int(prcc_seed),
                )
                prcc_progress.progress(1.0, text="PRCC analysis complete!")

                st.session_state["prcc_result"] = prcc_result

                # --- Regime shift probability gauge ---
                st.subheader("Regime Shift Probability")
                shift_prob = prcc_result.regime_shift_probability
                fig_rsp = go.Figure(go.Indicator(
                    mode="gauge+number",
                    value=shift_prob * 100,
                    title={"text": "Regime Shift Probability (%)"},
                    number={"suffix": "%"},
                    gauge={
                        "axis": {"range": [0, 100]},
                        "bar": {"color": "darkred" if shift_prob > 0.5 else "darkorange" if shift_prob > 0.2 else "darkgreen"},
                        "steps": [
                            {"range": [0, 20], "color": "#d4edda"},
                            {"range": [20, 50], "color": "#fff3cd"},
                            {"range": [50, 100], "color": "#f8d7da"},
                        ],
                        "threshold": {
                            "line": {"color": "black", "width": 4},
                            "thickness": 0.75, "value": 50,
                        },
                    },
                ))
                fig_rsp.update_layout(height=300)
                st.plotly_chart(fig_rsp, use_container_width=True)

                if shift_prob > 0.5:
                    st.error(
                        f"High regime shift probability ({shift_prob:.1%}): "
                        "a large fraction of parameter space leads to non-coexistence."
                    )
                elif shift_prob > 0.2:
                    st.warning(
                        f"Moderate regime shift probability ({shift_prob:.1%}): "
                        "some parameter combinations lead to regime shift."
                    )
                else:
                    st.success(
                        f"Low regime shift probability ({shift_prob:.1%}): "
                        "the system is robust across sampled parameter space."
                    )

                # --- PRCC tornado chart ---
                st.subheader("PRCC Values (Tornado Chart)")
                pnames = prcc_result.param_names
                prcc_vals = [prcc_result.prcc_values[p] for p in pnames]
                p_vals = [prcc_result.p_values[p] for p in pnames]

                # Sort by absolute PRCC
                sorted_idx = np.argsort(np.abs(prcc_vals))
                sorted_pnames = [pnames[i] for i in sorted_idx]
                sorted_prcc = [prcc_vals[i] for i in sorted_idx]
                sorted_pvals = [p_vals[i] for i in sorted_idx]

                colors = ["#dc3545" if abs(v) > 0.3 and pv < 0.05
                          else "#ffc107" if abs(v) > 0.15 and pv < 0.05
                          else "#6c757d"
                          for v, pv in zip(sorted_prcc, sorted_pvals)]

                fig_prcc = go.Figure()
                fig_prcc.add_trace(go.Bar(
                    y=[PARAM_REGISTRY[p].symbol if p in PARAM_REGISTRY else p for p in sorted_pnames],
                    x=sorted_prcc,
                    orientation="h",
                    marker=dict(color=colors),
                    text=[f"{v:+.3f} (p={pv:.3f})" for v, pv in zip(sorted_prcc, sorted_pvals)],
                    textposition="outside",
                ))
                fig_prcc.add_vline(x=0, line_dash="solid", line_color="black")
                fig_prcc.add_vline(x=0.3, line_dash="dash", line_color="red", opacity=0.5)
                fig_prcc.add_vline(x=-0.3, line_dash="dash", line_color="red", opacity=0.5)
                fig_prcc.update_layout(
                    xaxis_title="PRCC with rho*",
                    height=50 + 40 * len(pnames),
                    title="Parameter sensitivity to dominant eigenvalue",
                )
                st.plotly_chart(fig_prcc, use_container_width=True)

                # --- Equilibrium class distribution ---
                st.subheader("Equilibrium Class Distribution")
                from collections import Counter
                eq_counts = Counter(prcc_result.equilibrium_classes)
                fig_eq = go.Figure(data=[go.Pie(
                    labels=list(eq_counts.keys()),
                    values=list(eq_counts.values()),
                    marker=dict(colors=[
                        "#28a745" if c == "coexistence" else
                        "#dc3545" if c in ("parasitoid_free", "trivial") else
                        "#ffc107" for c in eq_counts.keys()
                    ]),
                )])
                fig_eq.update_layout(title="Equilibrium classes across LHS samples", height=350)
                st.plotly_chart(fig_eq, use_container_width=True)

            except Exception as exc:
                st.error(f"PRCC analysis failed: {exc}")

    _download_params_button(st.session_state["params"], key="dl_p4")


# ===================================================================
# Page 5 -- Management Strategies
# ===================================================================

with tab5:
    st.header("Management Strategies")
    params = st.session_state["params"]

    st.markdown(
        "Compare management scenarios using the current parameter set. "
        "Choose from predefined strategies A/B/C or define a custom strategy.",
    )

    col_m1, col_m2 = st.columns(2)
    with col_m1:
        m_A0 = st.number_input(
            "A0 (beetle density)", value=params.get("K_0", 1.7) * 0.5,
            min_value=0.0, step=0.01, format="%.4f", key="m_A0",
            help="Initial adult beetle density.",
        )
        m_F0 = st.number_input(
            "F0 (parasitoid density)", value=0.1,
            min_value=0.0, step=0.01, format="%.4f", key="m_F0",
            help="Initial parasitoid fly density.",
        )
    with col_m2:
        m_K0 = st.number_input(
            "K0 (carrying capacity)", value=params.get("K_0", 1.7),
            min_value=0.01, step=0.01, format="%.4f", key="m_K0",
            help="Initial carrying capacity (undamaged canopy).",
        )
        m_D0 = st.number_input(
            "D0 (defoliation)", value=0.0,
            min_value=0.0, step=0.01, format="%.4f", key="m_D0",
            help="Initial cumulative defoliation.",
        )

    m_years = st.slider("Planning horizon (years)", 5, 200, 50, key="m_years")

    # --- Custom strategy option ---
    st.markdown("---")
    use_custom = st.checkbox(
        "Define a Custom Strategy",
        key="use_custom",
        help="Set your own u_P, u_C, u_B values instead of optimising.",
    )
    custom_controls = None
    if use_custom:
        cc1, cc2, cc3 = st.columns(3)
        with cc1:
            custom_uP = st.slider(
                "u_P (parasitoid augmentation)",
                0.0, float(params.get("u_P_max", 0.5)), 0.1, step=0.01,
                key="custom_uP",
                help="Parasitoid augmentation release rate.",
            )
        with cc2:
            custom_uC = st.slider(
                "u_C (direct larval removal)",
                0.0, float(params.get("u_C_max", 0.2)), 0.0, step=0.01,
                key="custom_uC",
                help="Direct mechanical/biopesticide larval removal rate.",
            )
        with cc3:
            custom_uB = st.slider(
                "u_B (bird habitat enhancement)",
                0.0, float(params.get("u_B_max", 1.0)), 0.0, step=0.01,
                key="custom_uB",
                help="Bird habitat enhancement effort (nest boxes, hedgerows).",
            )
        custom_controls = {"u_P": custom_uP, "u_C": custom_uC, "u_B": custom_uB}
    st.markdown("---")

    if st.button("Compare Strategies", key="run_ctrl"):
        initial_state = {"A0": m_A0, "F0": m_F0, "K0": m_K0, "D0": m_D0}

        progress = st.progress(0.0, text="Optimising strategies...")
        try:
            model = AlderIPMSimModel(dict(params))
            optimizer = ControlOptimizer(model)

            results: List = []
            for i, sc in enumerate(["A", "B", "C"]):
                progress.progress((i + 1) / 4, text=f"Optimising Strategy {sc}...")
                results.append(optimizer.optimize_scenario(sc, initial_state, m_years))

            # Add custom strategy if defined
            if custom_controls is not None:
                progress.progress(0.9, text="Evaluating custom strategy...")
                traj_custom = optimizer.multi_year_trajectory(custom_controls, initial_state, m_years)
                A_end_c = traj_custom["A"][-1]
                F_end_c = traj_custom["F"][-1]
                K_end_c = traj_custom["K"][-1]
                D_end_c = traj_custom["D"][-1]

                cost_custom = optimizer.objective_functional(custom_controls, initial_state, m_years)
                try:
                    model_c = AlderIPMSimModel(dict(params))
                    model_c.u_P = custom_controls["u_P"]
                    model_c.u_C = custom_controls["u_C"]
                    orig_B = model_c.params.get("_B_index_base", model_c.params["B_index"])
                    rho_p = model_c.params["rho"]
                    model_c.params["B_index"] = orig_B * (1.0 + rho_p * custom_controls["u_B"])
                    jac_c = model_c.compute_jacobian(A_end_c, F_end_c, K_end_c, D_end_c)
                    rho_c = float(np.max(np.abs(np.linalg.eigvals(jac_c))))
                    model_c.params["B_index"] = orig_B
                    model_c.u_P = 0.0
                    model_c.u_C = 0.0
                except Exception:
                    rho_c = float("nan")

                feasible_c, violations_c = optimizer.feasibility_check(
                    D_end_c, K_end_c, rho_c, F_end_c, K_trajectory=traj_custom["K"],
                )
                results.append(OptimalControl(
                    scenario="Custom",
                    optimal_controls=custom_controls,
                    cost_J=cost_custom,
                    final_equilibrium={"A": A_end_c, "F": F_end_c, "K": K_end_c, "D": D_end_c},
                    final_D_star=D_end_c,
                    final_K_star=K_end_c,
                    final_rho_star=rho_c,
                    feasible=feasible_c,
                    violations=violations_c,
                ))

            progress.progress(1.0, text="Strategy comparison complete!")

            # --- Comparison table ---
            st.subheader("Strategy Comparison")
            scenario_names = {
                "A": "A: Parasitoid augmentation only",
                "B": "B: Parasitoid + bird habitat",
                "C": "C: Full integrated control",
                "Custom": "Custom: User-defined",
            }
            comp_rows = []
            for r in results:
                comp_rows.append({
                    "Strategy": scenario_names.get(r.scenario, r.scenario),
                    "Cost (J)": f"{r.cost_J:.2f}",
                    "D*": f"{r.final_D_star:.4f}",
                    "K*": f"{r.final_K_star:.4f}",
                    "rho*": f"{r.final_rho_star:.4f}",
                    "u_P": f"{r.optimal_controls['u_P']:.4f}",
                    "u_C": f"{r.optimal_controls['u_C']:.4f}",
                    "u_B": f"{r.optimal_controls['u_B']:.4f}",
                    "Feasible": "Yes" if r.feasible else "No",
                })
            st.dataframe(pd.DataFrame(comp_rows), use_container_width=True)

            # --- Pareto frontier: cost vs defoliation (sweep + strategies) ---
            st.subheader("Pareto Frontier (Cost vs Defoliation)")
            fig_pareto = go.Figure()
            colors_p = {"A": "#1f77b4", "B": "#ff7f0e", "C": "#2ca02c", "Custom": "#9467bd"}

            # Sweep: uniform budget scaling across 30 points
            try:
                pareto = optimizer.pareto_frontier(initial_state, n_points=30, n_years=m_years)
                fig_pareto.add_trace(go.Scatter(
                    x=pareto["cost"], y=pareto["final_D"],
                    mode="lines+markers",
                    marker=dict(size=5, color="grey"),
                    line=dict(color="grey", dash="dot"),
                    name="Budget sweep",
                    hovertemplate="Cost: %{x:.1f}<br>D*: %{y:.4f}<extra>sweep</extra>",
                ))
            except Exception:
                pass

            for r in results:
                marker_sym = "star" if r.feasible else "x"
                fig_pareto.add_trace(go.Scatter(
                    x=[r.cost_J], y=[r.final_D_star],
                    mode="markers+text",
                    text=[f"Strategy {r.scenario}"],
                    textposition="top center",
                    marker=dict(size=15, color=colors_p.get(r.scenario, "grey"), symbol=marker_sym),
                    name=f"Strategy {r.scenario}",
                ))
            fig_pareto.add_hline(
                y=params.get("D_crit", 0.5), line_dash="dash",
                line_color="red", annotation_text="D_crit",
            )
            fig_pareto.update_layout(
                xaxis_title="Total Cost (J)", yaxis_title="Final Defoliation (D*)",
                height=400, title="Cost-Defoliation Trade-off",
            )
            st.plotly_chart(fig_pareto, use_container_width=True)

            # --- Trajectory plots ---
            st.subheader("Multi-Year Trajectories")
            fig_ctrl = make_subplots(
                rows=2, cols=2, shared_xaxes=True,
                subplot_titles=["Beetle density (A)", "Parasitoid density (F)",
                                 "Carrying capacity (K)", "Cumulative defoliation (D)"],
            )
            traj_colors = {"A": "#1f77b4", "B": "#ff7f0e", "C": "#2ca02c", "Custom": "#9467bd"}
            for r in results:
                traj = optimizer.multi_year_trajectory(
                    r.optimal_controls, initial_state, m_years,
                )
                yrs = np.arange(m_years + 1)
                for key, row, col in [("A", 1, 1), ("F", 1, 2), ("K", 2, 1), ("D", 2, 2)]:
                    show_legend = key == "A"
                    fig_ctrl.add_trace(
                        go.Scatter(
                            x=yrs, y=traj[key], mode="lines",
                            name=f"Strategy {r.scenario}",
                            legendgroup=r.scenario,
                            showlegend=show_legend,
                            line=dict(color=traj_colors.get(r.scenario, "grey")),
                        ),
                        row=row, col=col,
                    )
            fig_ctrl.update_layout(height=600)
            fig_ctrl.update_xaxes(title_text="Year", row=2)
            st.plotly_chart(fig_ctrl, use_container_width=True)

            # --- Scenario timeline: control effort allocation ---
            st.subheader("Control Effort Allocation Timeline")
            fig_timeline = make_subplots(
                rows=1, cols=3,
                subplot_titles=["u_P (Parasitoid)", "u_C (Larval removal)", "u_B (Bird habitat)"],
            )
            for r in results:
                for i, ctrl_key in enumerate(["u_P", "u_C", "u_B"]):
                    val = r.optimal_controls[ctrl_key]
                    fig_timeline.add_trace(
                        go.Bar(
                            x=[f"Strategy {r.scenario}"], y=[val],
                            name=f"{r.scenario}" if i == 0 else None,
                            legendgroup=r.scenario,
                            showlegend=(i == 0),
                            marker=dict(color=traj_colors.get(r.scenario, "grey")),
                        ),
                        row=1, col=i + 1,
                    )
            fig_timeline.update_layout(height=350, title="Optimal Control Intensities by Strategy")
            st.plotly_chart(fig_timeline, use_container_width=True)

            # --- Temporal allocation: stacked area of per-year costs ---
            st.subheader("Temporal Cost Allocation")
            # Use the best feasible strategy (or first result) for temporal chart
            std_results_t = [r for r in results if r.scenario != "Custom"]
            feasible_t = [r for r in std_results_t if r.feasible]
            best_for_temporal = min(feasible_t, key=lambda r: r.cost_J) if feasible_t else results[0]
            try:
                ta = optimizer.temporal_allocation(
                    best_for_temporal.optimal_controls, initial_state, m_years,
                )
                fig_temporal = go.Figure()
                fig_temporal.add_trace(go.Scatter(
                    x=ta["years"], y=ta["running_cost"],
                    mode="lines", name="Running cost (damage)",
                    stackgroup="one", line=dict(color="#1f77b4"),
                ))
                fig_temporal.add_trace(go.Scatter(
                    x=ta["years"], y=ta["terminal_cost"],
                    mode="lines", name="Terminal cost (defoliation)",
                    stackgroup="one", line=dict(color="#ff7f0e"),
                ))
                fig_temporal.add_trace(go.Scatter(
                    x=ta["years"], y=ta["control_cost"],
                    mode="lines", name="Control cost (management)",
                    stackgroup="one", line=dict(color="#2ca02c"),
                ))
                fig_temporal.update_layout(
                    height=400,
                    title=f"Year-by-Year Cost Breakdown (Strategy {best_for_temporal.scenario})",
                    xaxis_title="Year", yaxis_title="Cost",
                )
                st.plotly_chart(fig_temporal, use_container_width=True)
            except Exception:
                st.info("Temporal cost allocation could not be computed.")

            # --- Cost breakdown table ---
            st.subheader("Cost Breakdown by Strategy")
            cost_rows = []
            for r in results:
                try:
                    ta_r = optimizer.temporal_allocation(
                        r.optimal_controls, initial_state, m_years,
                    )
                    cost_rows.append({
                        "Strategy": f"{r.scenario}",
                        "Running Cost": f"{float(ta_r['running_cost'].sum()):.2f}",
                        "Terminal Cost": f"{float(ta_r['terminal_cost'].sum()):.2f}",
                        "Control Cost": f"{float(ta_r['control_cost'].sum()):.2f}",
                        "Total J": f"{r.cost_J:.2f}",
                    })
                except Exception:
                    cost_rows.append({
                        "Strategy": f"{r.scenario}",
                        "Running Cost": "N/A",
                        "Terminal Cost": "N/A",
                        "Control Cost": "N/A",
                        "Total J": f"{r.cost_J:.2f}",
                    })
            st.dataframe(pd.DataFrame(cost_rows), use_container_width=True)

            # --- Recommendation ---
            st.subheader("Recommended Strategy")
            std_results = [r for r in results if r.scenario != "Custom"]
            feasible_std = [r for r in std_results if r.feasible]
            rec = min(feasible_std, key=lambda r: r.cost_J) if feasible_std else None

            if rec is not None:
                st.markdown(
                    _alert_css(
                        "green",
                        f"<b>Recommended: Strategy {rec.scenario}</b> "
                        f"(Cost J = {rec.cost_J:.2f})<br>"
                        f"{scenario_names[rec.scenario]}",
                    ),
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    _alert_css(
                        "red",
                        "<b>No feasible strategy found.</b> "
                        "Consider increasing control budgets or extending the planning horizon.",
                    ),
                    unsafe_allow_html=True,
                )

            comparison = {"results": std_results, "recommended": rec}
            comparison["recommendation_text"] = ControlOptimizer._build_recommendation(std_results, rec)
            st.markdown(comparison["recommendation_text"])

            # --- Feasibility checklist with green/red indicators ---
            st.subheader("Feasibility Checklist")
            for r in results:
                with st.expander(f"Strategy {r.scenario} — {'FEASIBLE' if r.feasible else 'INFEASIBLE'}"):
                    D_crit = params.get("D_crit", 0.5)
                    K_min = params.get("K_min", 0.856)
                    checks = [
                        (f"D* ({r.final_D_star:.4f}) < D_crit ({D_crit})", r.final_D_star < D_crit),
                        (f"K* ({r.final_K_star:.4f}) > K_min ({K_min})", r.final_K_star > K_min),
                        (f"F* ({r.final_equilibrium['F']:.4f}) > 0", r.final_equilibrium["F"] > 0),
                        (f"rho* ({r.final_rho_star:.4f}) < 1", r.final_rho_star < 1.01),
                    ]
                    for label, ok in checks:
                        icon = "green" if ok else "red"
                        circle = "🟢" if ok else "🔴"
                        st.markdown(f"{circle} {label}")
                    if r.violations:
                        for v in r.violations:
                            st.warning(v)

        except Exception as exc:
            st.error(f"Strategy comparison failed: {exc}")

    _download_params_button(st.session_state["params"], key="dl_p5")


# ===================================================================
# Page 6 -- Bifurcation Analysis
# ===================================================================

with tab6:
    st.header("Bifurcation Analysis")
    st.markdown(
        "Sweep a parameter to see how equilibria and the parasitoid invasion "
        "number R_P change — reproducing the bifurcation diagrams of "
        "manuscript Figures 2-3. Use the 2-D contour to find the R_P = 1 "
        "boundary in two-parameter space."
    )
    params = st.session_state["params"]

    # --- 1-D Bifurcation Diagram ---
    st.subheader("1-D Bifurcation Diagram")
    sweepable = sorted(k for k in PARAM_REGISTRY.keys()
                       if k not in ("D_crit", "K_min", "u_C_max", "u_P_max", "u_B_max"))

    bif_col1, bif_col2, bif_col3 = st.columns(3)
    with bif_col1:
        bif_param = st.selectbox(
            "Parameter to sweep",
            sweepable,
            index=sweepable.index("phi") if "phi" in sweepable else 0,
            key="bif_param",
            help="Select which parameter to vary across its ecological range.",
        )
    with bif_col2:
        pm = PARAM_REGISTRY[bif_param]
        bif_lo = st.number_input(
            "Range start", value=float(pm.min_val),
            format="%.6g", key="bif_lo",
        )
    with bif_col3:
        bif_hi = st.number_input(
            "Range end", value=float(pm.max_val),
            format="%.6g", key="bif_hi",
        )

    bif_npts = st.slider("Resolution (number of sweep points)", 20, 200, 60, key="bif_npts")

    if st.button("Compute Bifurcation Diagram", key="run_bif"):
        with st.spinner(f"Sweeping {bif_param} over {bif_npts} values..."):
            model = AlderIPMSimModel(dict(params))
            sweep_vals = np.linspace(bif_lo, bif_hi, bif_npts)
            bif_data = model.bifurcation_diagram(bif_param, sweep_vals)

            st.session_state["bif_data"] = bif_data
            st.session_state["bif_param_name"] = bif_param

    if "bif_data" in st.session_state:
        bif_data = st.session_state["bif_data"]
        bif_pname = st.session_state["bif_param_name"]
        pvals = bif_data["param_values"]
        pm_symbol = PARAM_REGISTRY[bif_pname].symbol if bif_pname in PARAM_REGISTRY else bif_pname

        # --- D* vs parameter (Fig 2 style) ---
        st.subheader(f"Equilibrium D* vs {pm_symbol}")
        fig_dstar = go.Figure()
        class_colors = {
            "trivial": "#6c757d",
            "canopy_only": "#17a2b8",
            "parasitoid_free": "#dc3545",
            "coexistence": "#28a745",
        }
        # Collect scatter points grouped by class and stability
        scatter_data: dict = {}  # (class, stable) -> (x, y, hover)
        for i, fps in enumerate(bif_data["equilibria"]):
            for fp in fps:
                key = (fp.equilibrium_class, fp.stable)
                if key not in scatter_data:
                    scatter_data[key] = ([], [], [])
                scatter_data[key][0].append(pvals[i])
                scatter_data[key][1].append(fp.D_star)
                scatter_data[key][2].append(
                    f"A*={fp.A_star:.4f}<br>F*={fp.F_star:.4f}<br>"
                    f"K*={fp.K_star:.4f}<br>D*={fp.D_star:.4f}<br>"
                    f"|λ|={fp.dominant_eigenvalue:.4f}<br>"
                    f"Bif: {fp.bifurcation_type}"
                )
        for (eq_cls, stable), (xs, ys, hovers) in scatter_data.items():
            marker_sym = "circle" if stable else "x"
            fig_dstar.add_trace(go.Scatter(
                x=xs, y=ys, mode="markers",
                marker=dict(
                    color=class_colors.get(eq_cls, "grey"),
                    symbol=marker_sym, size=7,
                    line=dict(width=1, color="black") if stable else dict(width=0),
                ),
                name=f"{eq_cls} ({'stable' if stable else 'unstable'})",
                hovertext=hovers, hoverinfo="text",
            ))
        fig_dstar.update_layout(
            xaxis_title=pm_symbol,
            yaxis_title="Equilibrium defoliation D*",
            height=450,
            title=f"Bifurcation diagram: D* vs {pm_symbol}",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_dstar, use_container_width=True)

        # --- R_P vs parameter (Fig 3 style) ---
        st.subheader(f"R_P vs {pm_symbol}")
        fig_rp = go.Figure()
        fig_rp.add_trace(go.Scatter(
            x=pvals, y=bif_data["R_P"], mode="lines+markers",
            marker=dict(size=5), name="R_P",
        ))
        fig_rp.add_hline(
            y=1.0, line_dash="dash", line_color="red",
            annotation_text="R_P = 1 (transcritical boundary)",
        )
        fig_rp.update_layout(
            xaxis_title=pm_symbol,
            yaxis_title="Parasitoid invasion number R_P",
            height=400,
            title=f"R_P vs {pm_symbol}",
        )
        st.plotly_chart(fig_rp, use_container_width=True)

        # --- Dominant eigenvalue rho* vs parameter ---
        st.subheader(f"Dominant eigenvalue |λ| vs {pm_symbol}")
        fig_rho = go.Figure()
        rho_data: dict = {}
        for i, fps in enumerate(bif_data["equilibria"]):
            for fp in fps:
                key = (fp.equilibrium_class, fp.stable)
                if key not in rho_data:
                    rho_data[key] = ([], [])
                rho_data[key][0].append(pvals[i])
                rho_data[key][1].append(fp.dominant_eigenvalue)
        for (eq_cls, stable), (xs, ys) in rho_data.items():
            marker_sym = "circle" if stable else "x"
            fig_rho.add_trace(go.Scatter(
                x=xs, y=ys, mode="markers",
                marker=dict(
                    color=class_colors.get(eq_cls, "grey"),
                    symbol=marker_sym, size=6,
                ),
                name=f"{eq_cls} ({'stable' if stable else 'unstable'})",
            ))
        fig_rho.add_hline(y=1.0, line_dash="dash", line_color="red",
                          annotation_text="|λ| = 1 (stability boundary)")
        fig_rho.update_layout(
            xaxis_title=pm_symbol,
            yaxis_title="Dominant eigenvalue |λ|",
            height=400,
            title=f"Spectral radius vs {pm_symbol}",
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig_rho, use_container_width=True)

    # --- 2-D R_P Contour ---
    st.markdown("---")
    st.subheader("2-D R_P Boundary Contour")
    st.markdown(
        "Select two parameters to produce a heatmap of R_P. "
        "The R_P = 1 contour marks the transcritical bifurcation boundary "
        "(parasitoid invasion threshold)."
    )

    c2d1, c2d2 = st.columns(2)
    with c2d1:
        bif2_p1 = st.selectbox("Parameter 1 (x-axis)", sweepable,
                                index=sweepable.index("beta") if "beta" in sweepable else 0,
                                key="bif2_p1")
        pm1 = PARAM_REGISTRY[bif2_p1]
        bif2_lo1 = st.number_input("P1 range start", value=float(pm1.min_val),
                                    format="%.6g", key="bif2_lo1")
        bif2_hi1 = st.number_input("P1 range end", value=float(pm1.max_val),
                                    format="%.6g", key="bif2_hi1")
    with c2d2:
        bif2_p2 = st.selectbox("Parameter 2 (y-axis)", sweepable,
                                index=sweepable.index("c_B") if "c_B" in sweepable else 1,
                                key="bif2_p2")
        pm2 = PARAM_REGISTRY[bif2_p2]
        bif2_lo2 = st.number_input("P2 range start", value=float(pm2.min_val),
                                    format="%.6g", key="bif2_lo2")
        bif2_hi2 = st.number_input("P2 range end", value=float(pm2.max_val),
                                    format="%.6g", key="bif2_hi2")

    bif2_grid = st.slider("Grid resolution per axis", 10, 80, 30, key="bif2_grid")

    if st.button("Compute 2-D R_P Boundary", key="run_bif2d"):
        if bif2_p1 == bif2_p2:
            st.error("Select two different parameters.")
        else:
            total_evals = bif2_grid * bif2_grid
            with st.spinner(f"Computing R_P over {total_evals} grid points..."):
                model = AlderIPMSimModel(dict(params))
                r1_vals = np.linspace(bif2_lo1, bif2_hi1, bif2_grid)
                r2_vals = np.linspace(bif2_lo2, bif2_hi2, bif2_grid)
                boundary = model.rp_boundary(bif2_p1, r1_vals, bif2_p2, r2_vals)
                st.session_state["bif2d_data"] = boundary
                st.session_state["bif2d_p1"] = bif2_p1
                st.session_state["bif2d_p2"] = bif2_p2

    if "bif2d_data" in st.session_state:
        bd = st.session_state["bif2d_data"]
        p1_name = st.session_state["bif2d_p1"]
        p2_name = st.session_state["bif2d_p2"]
        p1_sym = PARAM_REGISTRY[p1_name].symbol if p1_name in PARAM_REGISTRY else p1_name
        p2_sym = PARAM_REGISTRY[p2_name].symbol if p2_name in PARAM_REGISTRY else p2_name

        fig_2d = go.Figure()
        fig_2d.add_trace(go.Heatmap(
            x=bd["param1_values"],
            y=bd["param2_values"],
            z=bd["R_P_grid"].T,
            colorscale="RdYlGn",
            colorbar=dict(title="R_P"),
            zmin=0,
            zmax=max(2.0, float(np.nanmax(bd["R_P_grid"]))),
        ))
        # Add R_P = 1 contour
        fig_2d.add_trace(go.Contour(
            x=bd["param1_values"],
            y=bd["param2_values"],
            z=bd["R_P_grid"].T,
            contours=dict(
                start=1.0, end=1.0, size=0.1,
                coloring="none",
            ),
            line=dict(color="black", width=3),
            showscale=False,
            name="R_P = 1",
        ))

        # Mark current parameter values
        cur_v1 = params.get(p1_name, PARAM_REGISTRY[p1_name].default)
        cur_v2 = params.get(p2_name, PARAM_REGISTRY[p2_name].default)
        fig_2d.add_trace(go.Scatter(
            x=[cur_v1], y=[cur_v2],
            mode="markers",
            marker=dict(size=14, color="white", symbol="star",
                        line=dict(width=2, color="black")),
            name="Current",
        ))

        fig_2d.update_layout(
            xaxis_title=p1_sym,
            yaxis_title=p2_sym,
            height=550,
            title=f"R_P boundary: {p1_sym} vs {p2_sym} (black line = R_P = 1)",
        )
        st.plotly_chart(fig_2d, use_container_width=True)

        st.markdown(
            "**Green** region: R_P > 1 (parasitoid can invade, coexistence possible). "
            "**Red** region: R_P < 1 (parasitoid cannot persist). "
            "The **black contour** marks the transcritical bifurcation boundary."
        )

    _download_params_button(st.session_state["params"], key="dl_p6")

# ===================================================================
# Page 7 -- Scenario Comparison
# ===================================================================

with tab7:
    st.header("Scenario Comparison")
    st.markdown(
        "Save the current parameter set as a named scenario, then compare "
        "up to 4 scenarios side-by-side. Use parameter sweeps to explore "
        "how individual parameters affect system outcomes."
    )

    params = st.session_state["params"]

    # -- Initialize session state for saved scenarios --
    if "saved_scenarios" not in st.session_state:
        st.session_state["saved_scenarios"] = {}

    # -- Save current parameters as scenario --
    st.subheader("Save Current Parameters as Scenario")
    sc_col1, sc_col2 = st.columns([3, 1])
    with sc_col1:
        scenario_name = st.text_input(
            "Scenario name", value="Scenario 1", key="sc_name_input"
        )
    with sc_col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("Save Scenario", key="btn_save_scenario"):
            st.session_state["saved_scenarios"][scenario_name] = dict(params)
            st.success(f"Saved '{scenario_name}' ({len(params)} parameters)")

    saved = st.session_state["saved_scenarios"]
    if saved:
        st.markdown(f"**Saved scenarios:** {', '.join(saved.keys())}")
        if st.button("Clear all scenarios", key="btn_clear_scenarios"):
            st.session_state["saved_scenarios"] = {}
            st.rerun()

    st.markdown("---")

    # =================================================================
    # Section 1: Side-by-side scenario comparison
    # =================================================================
    st.subheader("Compare Scenarios Side-by-Side")

    if len(saved) < 2:
        st.info("Save at least 2 scenarios above to enable comparison.")
    else:
        selected_names = st.multiselect(
            "Select scenarios to compare (up to 4)",
            list(saved.keys()),
            default=list(saved.keys())[:min(4, len(saved))],
            max_selections=4,
            key="sc_compare_select",
        )

        cmp_col1, cmp_col2 = st.columns(2)
        with cmp_col1:
            cmp_years = st.slider("Simulation years", 10, 200, 50, 5, key="sc_cmp_years")
        with cmp_col2:
            cmp_A0 = st.number_input("A0", 0.0, 50.0, 0.8, 0.1, key="sc_cmp_a0")

        if st.button("Run Comparison", key="btn_run_compare") and selected_names:
            param_dicts = [saved[n] for n in selected_names]
            with st.spinner("Comparing scenarios..."):
                results = compare_scenarios(
                    param_dicts, selected_names,
                    n_years=cmp_years, A0=cmp_A0,
                )

            # -- Overlaid time series --
            st.markdown("#### Overlaid Time Series")
            colors = ["#E69F00", "#56B4E9", "#009E73", "#CC79A7"]
            dashes = ["solid", "dash", "dot", "dashdot"]
            for var_name, var_label in [("A", "Beetle Density A"), ("F", "Parasitoid Density F"),
                                         ("K", "Carrying Capacity K"), ("D", "Defoliation D")]:
                fig = go.Figure()
                for idx, res in enumerate(results):
                    arr = res.sim[var_name]
                    fig.add_trace(go.Scatter(
                        x=list(range(len(arr))),
                        y=arr if isinstance(arr, list) else arr.tolist(),
                        mode="lines",
                        name=res.name,
                        line=dict(color=colors[idx % 4], dash=dashes[idx % 4], width=2),
                    ))
                fig.update_layout(
                    title=var_label, xaxis_title="Year", yaxis_title=var_label,
                    height=350, legend=dict(orientation="h", yanchor="bottom", y=1.02),
                )
                st.plotly_chart(fig, use_container_width=True)

            # -- Comparison table --
            st.markdown("#### Equilibrium Comparison Table")
            table_data = []
            for res in results:
                table_data.append({
                    "Scenario": res.name,
                    "Equilibrium": res.equilibrium_class.replace("_", " ").title(),
                    "ρ*": f"{res.rho_star:.4f}",
                    "R_P": f"{res.R_P:.4f}",
                    "R1": f"{res.R1:.4f}" if res.R1 is not None else "N/A",
                    "R2": f"{res.R2:.4f}" if res.R2 is not None else "N/A",
                    "D*": f"{res.D_star:.4f}",
                    "K*": f"{res.K_star:.4f}",
                })
            st.dataframe(pd.DataFrame(table_data), use_container_width=True)

            # -- Radar chart --
            st.markdown("#### Radar Chart — Key Metrics")
            radar_cats = ["R_P", "R1", "R2", "K*", "1−D*"]
            fig_radar = go.Figure()
            for idx, res in enumerate(results):
                r1_val = res.R1 if res.R1 is not None else 0.0
                r2_val = res.R2 if res.R2 is not None else 0.0
                vals = [
                    min(res.R_P, 3.0),
                    max(r1_val, 0.0),
                    max(r2_val, 0.0),
                    min(res.K_star, 3.0),
                    max(1.0 - res.D_star, 0.0),
                ]
                fig_radar.add_trace(go.Scatterpolar(
                    r=vals + [vals[0]],
                    theta=radar_cats + [radar_cats[0]],
                    fill="toself",
                    name=res.name,
                    line=dict(color=colors[idx % 4]),
                    opacity=0.6,
                ))
            fig_radar.update_layout(
                polar=dict(radialaxis=dict(visible=True, range=[0, 3])),
                height=450,
                title="Scenario Comparison Radar",
            )
            st.plotly_chart(fig_radar, use_container_width=True)

    st.markdown("---")

    # =================================================================
    # Section 2: 1-D Parameter Sweep
    # =================================================================
    st.subheader("1-D Parameter Sweep")
    st.markdown("Sweep a single parameter and see how final-state metrics change.")

    sweep_params = [k for k in sorted(PARAM_REGISTRY.keys())
                    if k not in ("u_C", "u_P", "u_B", "u_C_max", "u_P_max", "u_B_max")]
    sw1_col1, sw1_col2, sw1_col3 = st.columns(3)
    with sw1_col1:
        sw1_param = st.selectbox("Parameter to sweep", sweep_params, key="sw1_param")
    with sw1_col2:
        pm = PARAM_REGISTRY[sw1_param]
        sw1_lo = st.number_input("Min value", value=float(pm.min_val), key="sw1_lo")
        sw1_hi = st.number_input("Max value", value=float(pm.max_val), key="sw1_hi")
    with sw1_col3:
        sw1_n = st.slider("Resolution (points)", 10, 100, 30, key="sw1_n")
        sw1_years = st.slider("Sim. years", 10, 200, 50, 5, key="sw1_years")

    if st.button("Run 1-D Sweep", key="btn_run_1d_sweep"):
        values = np.linspace(sw1_lo, sw1_hi, sw1_n)
        with st.spinner(f"Sweeping {sw1_param}..."):
            sweep_result = parameter_sweep_1d(
                sw1_param, values, n_years=sw1_years,
                base_params=dict(params),
            )

        sym = PARAM_REGISTRY[sw1_param].symbol

        # Plot D*, K*, rho* vs parameter value
        fig_sw = make_subplots(rows=3, cols=1, shared_xaxes=True,
                               subplot_titles=["Final Defoliation D*", "Final Capacity K*", "ρ* (dominant eigenvalue)"])
        fig_sw.add_trace(go.Scatter(
            x=sweep_result["param_values"].tolist(),
            y=sweep_result["D_star"].tolist(),
            mode="lines+markers", marker=dict(size=4),
            line=dict(color="#CC79A7"), name="D*",
        ), row=1, col=1)
        fig_sw.add_trace(go.Scatter(
            x=sweep_result["param_values"].tolist(),
            y=sweep_result["K_star"].tolist(),
            mode="lines+markers", marker=dict(size=4),
            line=dict(color="#009E73"), name="K*",
        ), row=2, col=1)
        fig_sw.add_trace(go.Scatter(
            x=sweep_result["param_values"].tolist(),
            y=sweep_result["rho_star"].tolist(),
            mode="lines+markers", marker=dict(size=4),
            line=dict(color="#56B4E9"), name="ρ*",
        ), row=3, col=1)
        # stability threshold line
        fig_sw.add_hline(y=1.0, line_dash="dash", line_color="red",
                         annotation_text="stability boundary", row=3, col=1)

        fig_sw.update_layout(height=700, xaxis3_title=sym, showlegend=False)
        st.plotly_chart(fig_sw, use_container_width=True)

        # Also show R_P sweep
        fig_rp = go.Figure()
        fig_rp.add_trace(go.Scatter(
            x=sweep_result["param_values"].tolist(),
            y=sweep_result["R_P"].tolist(),
            mode="lines+markers", marker=dict(size=4),
            line=dict(color="#E69F00"),
        ))
        fig_rp.add_hline(y=1.0, line_dash="dash", line_color="red",
                         annotation_text="R_P = 1")
        fig_rp.update_layout(
            title=f"R_P vs {sym}", xaxis_title=sym, yaxis_title="R_P",
            height=350,
        )
        st.plotly_chart(fig_rp, use_container_width=True)

    st.markdown("---")

    # =================================================================
    # Section 3: 2-D Parameter Sweep Heatmap
    # =================================================================
    st.subheader("2-D Parameter Sweep Heatmap")
    st.markdown("Sweep two parameters and visualise the resulting regime or metric as a heatmap.")

    sw2_col1, sw2_col2 = st.columns(2)
    with sw2_col1:
        sw2_p1 = st.selectbox("Parameter 1", sweep_params, index=0, key="sw2_p1")
        pm1 = PARAM_REGISTRY[sw2_p1]
        sw2_lo1 = st.number_input("P1 min", value=float(pm1.min_val), key="sw2_lo1")
        sw2_hi1 = st.number_input("P1 max", value=float(pm1.max_val), key="sw2_hi1")
    with sw2_col2:
        sw2_p2 = st.selectbox("Parameter 2", sweep_params, index=min(1, len(sweep_params)-1), key="sw2_p2")
        pm2 = PARAM_REGISTRY[sw2_p2]
        sw2_lo2 = st.number_input("P2 min", value=float(pm2.min_val), key="sw2_lo2")
        sw2_hi2 = st.number_input("P2 max", value=float(pm2.max_val), key="sw2_hi2")

    sw2_n = st.slider("Grid resolution (per axis)", 5, 30, 15, key="sw2_n")
    sw2_metric = st.selectbox("Metric to display", ["D_star", "K_star", "R_P", "rho_star"], key="sw2_metric")

    if st.button("Run 2-D Sweep", key="btn_run_2d_sweep"):
        v1 = np.linspace(sw2_lo1, sw2_hi1, sw2_n)
        v2 = np.linspace(sw2_lo2, sw2_hi2, sw2_n)
        with st.spinner(f"Sweeping {sw2_p1} × {sw2_p2} ({sw2_n}×{sw2_n} grid)..."):
            sweep2d = parameter_sweep_2d(
                sw2_p1, v1, sw2_p2, v2,
                n_years=50, base_params=dict(params),
            )

        sym1 = PARAM_REGISTRY[sw2_p1].symbol
        sym2 = PARAM_REGISTRY[sw2_p2].symbol
        metric_labels = {"D_star": "D*", "K_star": "K*", "R_P": "R_P", "rho_star": "ρ*"}

        z_data = sweep2d[sw2_metric]
        fig_2d = go.Figure()
        fig_2d.add_trace(go.Heatmap(
            x=sweep2d["param1_values"].tolist(),
            y=sweep2d["param2_values"].tolist(),
            z=z_data.T.tolist() if hasattr(z_data, 'T') else z_data,
            colorscale="Viridis",
            colorbar=dict(title=metric_labels.get(sw2_metric, sw2_metric)),
        ))

        # Mark current parameter values
        cur_v1 = params.get(sw2_p1, pm1.default)
        cur_v2 = params.get(sw2_p2, pm2.default)
        fig_2d.add_trace(go.Scatter(
            x=[cur_v1], y=[cur_v2],
            mode="markers",
            marker=dict(size=14, color="white", symbol="star",
                        line=dict(width=2, color="black")),
            name="Current",
        ))

        fig_2d.update_layout(
            xaxis_title=sym1, yaxis_title=sym2,
            height=550,
            title=f"{metric_labels.get(sw2_metric, sw2_metric)}: {sym1} vs {sym2}",
        )
        st.plotly_chart(fig_2d, use_container_width=True)

    _download_params_button(st.session_state["params"], key="dl_p7")
