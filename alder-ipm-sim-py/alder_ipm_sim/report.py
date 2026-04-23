# HTML report generation for the AlderIPM-Sim toolkit.
from __future__ import annotations

import datetime
from typing import Any, Dict, List, Optional

from .parameters import PARAM_REGISTRY, get_defaults


class ReportGenerator:
    """Collect analysis results and render a standalone HTML report.

    Usage::

        gen = ReportGenerator(params=my_params, scenario_name="Warm Winter")
        gen.add_simulation(sim_result)
        gen.add_equilibrium(fixed_points, R_P)
        gen.add_warnings(warning_report)
        gen.add_control(control_results, recommendation)
        html = gen.render()
    """

    def __init__(
        self,
        params: Optional[Dict[str, float]] = None,
        scenario_name: str = "Custom",
        date: Optional[str] = None,
    ) -> None:
        self.params = params or get_defaults()
        self.scenario_name = scenario_name
        self.date = date or datetime.date.today().isoformat()

        self._simulation: Optional[Dict[str, Any]] = None
        self._fixed_points: Optional[List[Any]] = None
        self._R_P: Optional[float] = None
        self._R1: Optional[float] = None
        self._R2: Optional[float] = None
        self._warnings: Optional[Any] = None
        self._control_results: Optional[List[Any]] = None
        self._recommendation: Optional[str] = None

    # ── data setters ────────────────────────────────────────────────

    def add_simulation(self, sim_result: Dict[str, Any]) -> None:
        self._simulation = sim_result

    def add_equilibrium(
        self,
        fixed_points: List[Any],
        R_P: float,
        R1: Optional[float] = None,
        R2: Optional[float] = None,
    ) -> None:
        self._fixed_points = fixed_points
        self._R_P = R_P
        self._R1 = R1
        self._R2 = R2

    def add_warnings(self, warning_report: Any) -> None:
        self._warnings = warning_report

    def add_control(
        self,
        control_results: List[Any],
        recommendation: Optional[str] = None,
    ) -> None:
        self._control_results = control_results
        self._recommendation = recommendation

    # ── rendering ───────────────────────────────────────────────────

    def render(self) -> str:
        """Return a complete standalone HTML document."""
        sections = [
            self._section_params(),
            self._section_simulation(),
            self._section_equilibrium(),
            self._section_warnings(),
            self._section_management(),
            self._section_appendix(),
        ]
        body = "\n".join(s for s in sections if s)
        return _HTML_TEMPLATE.format(
            date=self.date,
            scenario=_esc(self.scenario_name),
            body=body,
        )

    # ── Section 1: Parameter summary ────────────────────────────────

    def _section_params(self) -> str:
        rows: list[str] = []
        defaults = get_defaults()
        for name in sorted(self.params.keys()):
            meta = PARAM_REGISTRY.get(name)
            if meta is None:
                continue
            val = self.params[name]
            default = defaults.get(name, val)
            changed = abs(val - default) > 1e-12
            cls = ' class="changed"' if changed else ""
            rows.append(
                f"<tr{cls}>"
                f"<td>{_esc(meta.symbol)}</td>"
                f"<td>{_esc(name)}</td>"
                f"<td>{val:.6g}</td>"
                f"<td>[{meta.min_val}, {meta.max_val}]</td>"
                f"<td>{_esc(meta.unit)}</td>"
                f"<td>{_esc(meta.description[:80])}</td>"
                f"</tr>"
            )
        return (
            '<h2>1. Parameter Summary</h2>'
            '<table><thead><tr>'
            '<th>Symbol</th><th>Name</th><th>Value</th>'
            '<th>Range</th><th>Unit</th><th>Description</th>'
            '</tr></thead><tbody>'
            + "\n".join(rows)
            + "</tbody></table>"
            + '<p class="note">Rows highlighted indicate values changed from defaults.</p>'
        )

    # ── Section 2: Simulation trajectories ──────────────────────────

    def _section_simulation(self) -> str:
        if self._simulation is None:
            return '<h2>2. Simulation Trajectories</h2><p>No simulation data available.</p>'

        sim = self._simulation
        n = len(sim["A"])
        years = list(range(n))

        # Build inline SVG sparkline charts for each state variable
        charts: list[str] = []
        labels = [
            ("A", "Beetle Larvae (A)", "#E69F00"),
            ("F", "Parasitoid Flies (F)", "#56B4E9"),
            ("K", "Canopy Capacity (K)", "#009E73"),
            ("D", "Cumulative Defoliation (D)", "#D55E00"),
        ]
        for key, label, color in labels:
            arr = sim[key]
            if hasattr(arr, "tolist"):
                arr = arr.tolist()
            charts.append(_svg_timeseries(years, arr, label, color))

        end_state = (
            "<h3>End State (Year {n})</h3>"
            "<table><thead><tr><th>Variable</th><th>Value</th></tr></thead><tbody>"
        ).format(n=n - 1)
        for key in ["A", "F", "K", "D"]:
            arr = sim[key]
            val = arr[-1] if not hasattr(arr, "item") else arr[-1]
            end_state += f"<tr><td>{key}</td><td>{val:.6f}</td></tr>"
        end_state += "</tbody></table>"

        return (
            '<h2>2. Simulation Trajectories</h2>'
            '<div class="chart-grid">' + "\n".join(charts) + "</div>"
            + end_state
        )

    # ── Section 3: Equilibrium analysis ─────────────────────────────

    def _section_equilibrium(self) -> str:
        parts = ['<h2>3. Equilibrium Analysis</h2>']

        if self._R_P is not None:
            status = "Coexistence possible" if self._R_P > 1 else "Parasitoid cannot persist"
            color = "#009E73" if self._R_P > 1 else "#D55E00"
            parts.append(
                f'<p><strong>R<sub>P</sub> = {self._R_P:.6f}</strong> '
                f'&mdash; <span style="color:{color}">{status}</span></p>'
            )

        if self._R1 is not None or self._R2 is not None:
            parts.append("<h3>Resistance &amp; Resilience</h3><ul>")
            if self._R1 is not None:
                parts.append(f"<li><strong>R1 (Resistance):</strong> {self._R1:.4f}</li>")
            if self._R2 is not None:
                parts.append(f"<li><strong>R2 (Resilience):</strong> {self._R2:.4f}</li>")
            parts.append("</ul>")

        if self._fixed_points:
            parts.append(
                '<table><thead><tr>'
                '<th>Class</th><th>Stable</th>'
                '<th>A*</th><th>F*</th><th>K*</th><th>D*</th>'
                '<th>|&lambda;<sub>dom</sub>|</th><th>Bifurcation</th>'
                '</tr></thead><tbody>'
            )
            for fp in self._fixed_points:
                stable_cls = "stable" if fp.stable else "unstable"
                parts.append(
                    f'<tr class="{stable_cls}">'
                    f"<td>{_esc(fp.equilibrium_class)}</td>"
                    f"<td>{'Yes' if fp.stable else 'No'}</td>"
                    f"<td>{fp.A_star:.4f}</td>"
                    f"<td>{fp.F_star:.4f}</td>"
                    f"<td>{fp.K_star:.4f}</td>"
                    f"<td>{fp.D_star:.4f}</td>"
                    f"<td>{fp.dominant_eigenvalue:.4f}</td>"
                    f"<td>{_esc(fp.bifurcation_type)}</td>"
                    f"</tr>"
                )
            parts.append("</tbody></table>")
        else:
            parts.append("<p>No fixed points computed.</p>")

        return "\n".join(parts)

    # ── Section 4: Early warning signals ────────────────────────────

    def _section_warnings(self) -> str:
        if self._warnings is None:
            return '<h2>4. Early Warning Signals</h2><p>No EWS data available.</p>'

        wr = self._warnings
        alert_colors = {"green": "#009E73", "yellow": "#E69F00", "red": "#D55E00"}
        color = alert_colors.get(wr.alert_level, "#999")

        parts = [
            '<h2>4. Early Warning Signals</h2>',
            f'<div class="alert-box" style="border-left:4px solid {color}; padding:12px; margin:12px 0;">'
            f'<strong>Alert Level: <span style="color:{color}">'
            f'{wr.alert_level.upper()}</span></strong></div>',
        ]

        if hasattr(wr, "interpretation") and wr.interpretation:
            parts.append(f"<p><em>{_esc(wr.interpretation)}</em></p>")

        parts.append(
            '<table><thead><tr>'
            '<th>Indicator</th><th>Kendall &tau;</th><th>p-value</th><th>Trend</th>'
            '</tr></thead><tbody>'
        )
        for name, res in wr.kendall_results.items():
            tau = res.get("tau", 0)
            pval = res.get("p_value", 1)
            sig = "Significant" if pval < 0.05 and tau > 0 else "Not significant"
            parts.append(
                f"<tr><td>{_esc(name)}</td>"
                f"<td>{tau:+.4f}</td>"
                f"<td>{pval:.4f}</td>"
                f"<td>{sig}</td></tr>"
            )
        parts.append("</tbody></table>")
        return "\n".join(parts)

    # ── Section 5: Management recommendation ────────────────────────

    def _section_management(self) -> str:
        if self._control_results is None:
            return '<h2>5. Management Recommendation</h2><p>No control analysis available.</p>'

        parts = ['<h2>5. Management Recommendation</h2>']

        if self._recommendation:
            parts.append(f'<div class="recommendation"><strong>Recommended:</strong> {_esc(self._recommendation)}</div>')

        parts.append(
            '<table><thead><tr>'
            '<th>Scenario</th><th>Cost (J)</th>'
            '<th>D*</th><th>K*</th><th>&rho;*</th>'
            '<th>u<sub>P</sub></th><th>u<sub>C</sub></th><th>u<sub>B</sub></th>'
            '<th>Feasible</th>'
            '</tr></thead><tbody>'
        )
        for r in self._control_results:
            feas_cls = "stable" if r.feasible else "unstable"
            uc = r.optimal_controls
            parts.append(
                f'<tr class="{feas_cls}">'
                f"<td>{_esc(r.scenario)}</td>"
                f"<td>{r.cost_J:.4f}</td>"
                f"<td>{r.final_D_star:.4f}</td>"
                f"<td>{r.final_K_star:.4f}</td>"
                f"<td>{r.final_rho_star:.4f}</td>"
                f"<td>{uc.get('u_P', 0):.4f}</td>"
                f"<td>{uc.get('u_C', 0):.4f}</td>"
                f"<td>{uc.get('u_B', 0):.4f}</td>"
                f"<td>{'Yes' if r.feasible else 'No'}</td>"
                f"</tr>"
            )
        parts.append("</tbody></table>")

        # Violations
        all_viols = []
        for r in self._control_results:
            if r.violations:
                for v in r.violations:
                    all_viols.append(f"Scenario {r.scenario}: {v}")
        if all_viols:
            parts.append("<h3>Feasibility Violations</h3><ul>")
            for v in all_viols:
                parts.append(f"<li>{_esc(v)}</li>")
            parts.append("</ul>")

        return "\n".join(parts)

    # ── Section 6: Technical appendix ───────────────────────────────

    def _section_appendix(self) -> str:
        rows: list[str] = []
        for name in sorted(PARAM_REGISTRY.keys()):
            meta = PARAM_REGISTRY[name]
            rows.append(
                f"<tr><td>{_esc(meta.symbol)}</td>"
                f"<td>{_esc(name)}</td>"
                f"<td>[{meta.min_val}, {meta.max_val}]</td>"
                f"<td>{_esc(meta.unit)}</td>"
                f"<td>{_esc(meta.description)}</td></tr>"
            )

        equations = (
            "<h3>Model Equations</h3>"
            "<p><strong>Within-season ODE system (Eqs. 1&ndash;4):</strong></p>"
            "<pre>"
            "dS/dt = -(&beta; S F)/(1 + h S) - (c_B B S)/(1 + a_B S) - &mu;_S S\n"
            "dI/dt =  (&beta; S F)/(1 + h S) - &mu;_I I\n"
            "dF/dt =  &delta; &eta; I(t - &tau;) - &mu;_F F\n"
            "dD/dt =  &kappa; S\n"
            "</pre>"
            "<p><strong>Annual map (Eqs. 5&ndash;8):</strong></p>"
            "<pre>"
            "A(t+1)  = R_B A(t) &sigma;_A exp(-A(t)/K(t))\n"
            "F(t+1)  = &sigma;_F (F_end(t) + u_P)\n"
            "K(t+1)  = K_0 (1 - &phi; D(t))\n"
            "&rho;(t) = spectral radius of the annual-map Jacobian\n"
            "</pre>"
        )

        return (
            '<h2>6. Technical Appendix</h2>'
            + equations
            + "<h3>Full Parameter Reference</h3>"
            '<table><thead><tr>'
            '<th>Symbol</th><th>Name</th><th>Range</th><th>Unit</th><th>Description</th>'
            '</tr></thead><tbody>'
            + "\n".join(rows)
            + "</tbody></table>"
        )


# ── Helpers ─────────────────────────────────────────────────────────────

def _esc(text: str) -> str:
    """Minimal HTML escaping."""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _svg_timeseries(
    x: list, y: list, title: str, color: str, width: int = 400, height: int = 150
) -> str:
    """Generate a simple inline SVG sparkline chart."""
    if not y:
        return f'<div class="chart-cell"><h4>{_esc(title)}</h4><p>No data</p></div>'

    pad = 40
    plot_w = width - 2 * pad
    plot_h = height - 2 * pad

    y_min = min(y)
    y_max = max(y)
    y_range = y_max - y_min if y_max > y_min else 1.0
    x_max = max(x) if x else 1

    points: list[str] = []
    for i, (xi, yi) in enumerate(zip(x, y)):
        px = pad + (xi / x_max) * plot_w if x_max else pad
        py = pad + plot_h - ((yi - y_min) / y_range) * plot_h
        points.append(f"{px:.1f},{py:.1f}")

    polyline = " ".join(points)
    return (
        f'<div class="chart-cell">'
        f'<h4>{_esc(title)}</h4>'
        f'<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg"'
        f' style="width:100%; max-width:{width}px; background:#fafafa; border:1px solid #ddd;">'
        # axes
        f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{pad + plot_h}" stroke="#999" stroke-width="1"/>'
        f'<line x1="{pad}" y1="{pad + plot_h}" x2="{pad + plot_w}" y2="{pad + plot_h}" stroke="#999" stroke-width="1"/>'
        # y-axis labels
        f'<text x="{pad - 4}" y="{pad + 4}" text-anchor="end" font-size="9" fill="#666">{y_max:.3g}</text>'
        f'<text x="{pad - 4}" y="{pad + plot_h}" text-anchor="end" font-size="9" fill="#666">{y_min:.3g}</text>'
        # x-axis labels
        f'<text x="{pad}" y="{pad + plot_h + 14}" text-anchor="start" font-size="9" fill="#666">0</text>'
        f'<text x="{pad + plot_w}" y="{pad + plot_h + 14}" text-anchor="end" font-size="9" fill="#666">{x_max}</text>'
        # data
        f'<polyline points="{polyline}" fill="none" stroke="{color}" stroke-width="2"/>'
        f'</svg></div>'
    )


# ── HTML template ───────────────────────────────────────────────────────

_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1.0"/>
<title>AlderIPM-Sim Analysis Report</title>
<style>
  body {{
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    max-width: 960px; margin: 0 auto; padding: 20px;
    color: #1a1a1a; line-height: 1.6; font-size: 14px;
  }}
  h1 {{ color: #2d6a4f; border-bottom: 3px solid #2d6a4f; padding-bottom: 8px; }}
  h2 {{ color: #40916c; margin-top: 2em; border-bottom: 1px solid #ddd; padding-bottom: 4px; }}
  h3 {{ color: #52b788; }}
  .header-meta {{ color: #666; margin-bottom: 1em; }}
  table {{
    border-collapse: collapse; width: 100%; margin: 12px 0; font-size: 13px;
  }}
  th, td {{ border: 1px solid #ddd; padding: 6px 10px; text-align: left; }}
  thead {{ background: #2d6a4f; color: #fff; }}
  tr:nth-child(even) {{ background: #f8f8f8; }}
  tr.changed {{ background: #fff3cd; }}
  tr.stable td:first-child {{ border-left: 4px solid #009E73; }}
  tr.unstable td:first-child {{ border-left: 4px solid #D55E00; }}
  .chart-grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 12px 0; }}
  .chart-cell {{ padding: 8px; }}
  .chart-cell h4 {{ margin: 0 0 4px; font-size: 13px; color: #444; }}
  .recommendation {{
    background: #d4edda; border: 1px solid #c3e6cb; padding: 12px; border-radius: 4px; margin: 12px 0;
  }}
  .alert-box {{ background: #f8f9fa; border-radius: 4px; }}
  .note {{ font-size: 12px; color: #888; font-style: italic; }}
  pre {{ background: #f4f4f4; padding: 12px; border-radius: 4px; overflow-x: auto; font-size: 13px; }}
  @media print {{
    body {{ font-size: 11pt; }}
    h1 {{ font-size: 18pt; }}
    h2 {{ page-break-before: auto; }}
    table {{ font-size: 9pt; }}
    .chart-grid {{ grid-template-columns: 1fr 1fr; }}
  }}
</style>
</head>
<body>
<h1>AlderIPM-Sim Analysis Report</h1>
<div class="header-meta">
  <strong>Date:</strong> {date} &nbsp;|&nbsp;
  <strong>Scenario:</strong> {scenario}
</div>
{body}
<hr/>
<p class="note">Generated by AlderIPM-Sim &mdash; Decision-support toolkit for the
Alnus-beetle-parasitoid-bird ecoepidemic system.</p>
</body>
</html>"""
