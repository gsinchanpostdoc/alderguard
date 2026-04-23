# Command-line interface for the AlderIPM-Sim toolkit.
from __future__ import annotations

import argparse
import csv
import json
import sys
from typing import Dict, List, Optional


def _safe_print(text: str) -> None:
    """Print text, replacing unencodable characters on Windows."""
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode(sys.stdout.encoding or "utf-8", errors="replace").decode(
            sys.stdout.encoding or "utf-8", errors="replace"))


def _parse_params(raw: Optional[str]) -> Dict[str, float]:
    """Parse --params argument: either a JSON file path or key=value pairs."""
    if raw is None:
        return {}
    # Try as JSON file first
    if raw.endswith(".json"):
        with open(raw) as f:
            return {k: float(v) for k, v in json.load(f).items()}
    # Otherwise treat as comma-separated key=value
    params: Dict[str, float] = {}
    for token in raw.split(","):
        token = token.strip()
        if "=" not in token:
            raise argparse.ArgumentTypeError(
                f"Invalid param token '{token}'. Expected key=value."
            )
        k, v = token.split("=", 1)
        params[k.strip()] = float(v.strip())
    return params


def _parse_initial_state(raw: Optional[str]) -> Dict[str, float]:
    """Parse --initial-state JSON string or file."""
    if raw is None:
        return {}
    if raw.endswith(".json"):
        with open(raw) as f:
            return {k: float(v) for k, v in json.load(f).items()}
    return {k: float(v) for k, v in json.loads(raw).items()}


def _parse_state_cols(raw: Optional[str]) -> Optional[Dict[str, str]]:
    """Parse --state-cols like A=beetle_count,D=defoliation."""
    if raw is None:
        return None
    mapping: Dict[str, str] = {}
    for token in raw.split(","):
        token = token.strip()
        if "=" not in token:
            raise argparse.ArgumentTypeError(
                f"Invalid state-col token '{token}'. Expected State=column_name."
            )
        k, v = token.split("=", 1)
        mapping[k.strip()] = v.strip()
    return mapping


# ======================================================================
# Subcommand: simulate
# ======================================================================

def cmd_simulate(args: argparse.Namespace) -> None:
    from .model import AlderIPMSimModel
    from .parameters import get_defaults

    params = get_defaults()
    params.update(_parse_params(args.params))
    model = AlderIPMSimModel(params)

    ic = {"A0": params["K_0"] * 0.5, "F0": 0.1, "K0": params["K_0"], "D0": 0.0}
    user_ic = _parse_initial_state(args.initial_state)
    ic.update(user_ic)

    n_years = args.years
    result = model.simulate(
        A0=ic["A0"], F0=ic["F0"], K0=ic["K0"], D0=ic["D0"],
        n_years=n_years,
    )

    # Print summary
    print(f"Simulation complete: {n_years} years")
    print(f"  Final beetle density   A = {result['A'][-1]:.6f}")
    print(f"  Final parasitoid       F = {result['F'][-1]:.6f}")
    print(f"  Final carrying cap.    K = {result['K'][-1]:.6f}")
    print(f"  Final defoliation      D = {result['D'][-1]:.6f}")

    # Write CSV output
    if args.output:
        with open(args.output, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["year", "A", "F", "K", "D"])
            for i in range(n_years + 1):
                writer.writerow([
                    i, result["A"][i], result["F"][i],
                    result["K"][i], result["D"][i],
                ])
        print(f"  Output written to {args.output}")

    # Plot
    if args.plot:
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("matplotlib is required for --plot. Install it with: pip install matplotlib")
            sys.exit(1)
        import numpy as np
        years = np.arange(n_years + 1)
        fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
        for ax, key, label in zip(
            axes.flat,
            ["A", "F", "K", "D"],
            ["Beetle density (A)", "Parasitoid density (F)",
             "Carrying capacity (K)", "Cumulative defoliation (D)"],
        ):
            ax.plot(years, result[key])
            ax.set_ylabel(label)
            ax.set_xlabel("Year")
            ax.grid(True, alpha=0.3)
        fig.suptitle("AlderIPM-Sim Forward Simulation")
        plt.tight_layout()
        plt.show()


# ======================================================================
# Subcommand: equilibrium
# ======================================================================

def cmd_equilibrium(args: argparse.Namespace) -> None:
    from .model import AlderIPMSimModel
    from .parameters import get_defaults

    params = get_defaults()
    params.update(_parse_params(args.params))
    model = AlderIPMSimModel(params)

    print("Searching for fixed points of the annual map...")
    fps = model.find_fixed_points()

    if not fps:
        print("No fixed points found.")
        return

    # Header
    hdr = f"{'Class':<18} {'Stable':<8} {'A*':>10} {'F*':>10} {'K*':>10} {'D*':>10} {'|λ_dom|':>10} {'Bifurcation':<16}"
    print()
    print(hdr)
    print("-" * len(hdr))

    for fp in fps:
        print(
            f"{fp.equilibrium_class:<18} "
            f"{'Yes' if fp.stable else 'No':<8} "
            f"{fp.A_star:>10.4f} "
            f"{fp.F_star:>10.4f} "
            f"{fp.K_star:>10.4f} "
            f"{fp.D_star:>10.4f} "
            f"{fp.dominant_eigenvalue:>10.4f} "
            f"{fp.bifurcation_type:<16}"
        )

    if args.verbose:
        print()
        R_P = model.compute_R_P()
        print(f"Parasitoid invasion reproduction number R_P = {R_P:.4f}")
        print(f"  R_P {'>' if R_P > 1 else '<'} 1 => parasitoid {'can' if R_P > 1 else 'cannot'} invade")


# ======================================================================
# Subcommand: fit
# ======================================================================

def cmd_fit(args: argparse.Namespace) -> None:
    from .fitting import ModelFitter
    from .model import AlderIPMSimModel
    from .parameters import get_defaults

    import numpy as np

    # Load CSV data
    data_dict: Dict[str, list] = {}
    with open(args.data, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for k, v in row.items():
                data_dict.setdefault(k, []).append(float(v))

    params = get_defaults()
    params.update(_parse_params(args.params))
    model = AlderIPMSimModel(params)
    fitter = ModelFitter(model)

    state_cols = _parse_state_cols(args.state_cols)
    time_col = args.time_col or "year"
    timestep = args.timestep or "annual"

    prepared = fitter.prepare_data(
        data_dict, time_col=time_col, state_cols=state_cols, timestep=timestep,
    )

    fit_params = None
    if args.fit_params:
        fit_params = [p.strip() for p in args.fit_params.split(",")]

    result = fitter.fit(prepared, fit_params=fit_params)

    # Print results
    print("Fitted parameters:")
    for name, val in result.fitted_params.items():
        ci = result.confidence_intervals.get(name, (val, val))
        print(f"  {name:<12} = {val:.6f}  (95% CI: [{ci[0]:.6f}, {ci[1]:.6f}])")

    print(f"\nR-squared: {result.r_squared:.4f}")
    print(f"AIC: {result.AIC:.2f}")
    print(f"BIC: {result.BIC:.2f}")

    # Regime forecast
    regime = fitter.forecast_regime(result)
    print(f"\nRegime forecast: {regime['equilibrium_class']}")
    print(f"  R_P = {regime['R_P']:.4f}")
    print(f"  Dominant eigenvalue = {regime['dominant_eigenvalue']:.4f}")
    print(f"  {regime['interpretation']}")

    # Write output JSON
    if args.output:
        out = {
            "fitted_params": result.fitted_params,
            "r_squared": result.r_squared,
            "AIC": result.AIC,
            "BIC": result.BIC,
            "confidence_intervals": {
                k: list(v) for k, v in result.confidence_intervals.items()
            },
            "regime_forecast": {
                "equilibrium_class": regime["equilibrium_class"],
                "R_P": regime["R_P"],
                "dominant_eigenvalue": regime["dominant_eigenvalue"],
                "interpretation": regime["interpretation"],
            },
        }
        with open(args.output, "w") as f:
            json.dump(out, f, indent=2)
        print(f"\nResults written to {args.output}")


# ======================================================================
# Subcommand: warn
# ======================================================================

def cmd_warn(args: argparse.Namespace) -> None:
    from .warnings import EarlyWarningDetector

    import numpy as np

    # Load CSV data
    data_dict: Dict[str, list] = {}
    with open(args.data, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            for k, v in row.items():
                data_dict.setdefault(k, []).append(float(v))

    column = args.column
    if column not in data_dict:
        print(f"Error: column '{column}' not found in data. Available: {list(data_dict.keys())}")
        sys.exit(1)

    ts = np.array(data_dict[column])
    window = args.window
    detector = EarlyWarningDetector(window_size=window)
    report = detector.detect_regime_shift(ts)

    # Print results
    print(f"Early Warning Signal Analysis — column: {column}")
    print(f"  Time series length: {len(ts)}")
    print(f"  Window size: {detector._effective_window(ts)}")
    print()

    print("Kendall trend tests:")
    for name, res in report.kendall_results.items():
        sig = "*" if res["p_value"] < 0.05 else " "
        print(f"  {name:<20} tau = {res['tau']:+.4f}  p = {res['p_value']:.4f} {sig}")

    print(f"\nAlert level: {report.alert_level.upper()}")
    print(f"Interpretation: {report.interpretation}")

    # Write output JSON
    if args.output:
        out = {
            "column": column,
            "alert_level": report.alert_level,
            "interpretation": report.interpretation,
            "kendall_results": report.kendall_results,
        }
        with open(args.output, "w") as f:
            json.dump(out, f, indent=2)
        print(f"\nResults written to {args.output}")

    # Plot
    if args.plot:
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("matplotlib is required for --plot. Install it with: pip install matplotlib")
            sys.exit(1)
        fig, axes = plt.subplots(3, 1, figsize=(10, 8), sharex=True)

        axes[0].plot(ts)
        axes[0].set_ylabel(column)
        axes[0].set_title("Raw time series")
        axes[0].grid(True, alpha=0.3)

        var = report.indicators["variance"]
        axes[1].plot(var)
        axes[1].set_ylabel("Rolling variance")
        axes[1].grid(True, alpha=0.3)

        ac = report.indicators["autocorrelation"]
        axes[2].plot(ac)
        axes[2].set_ylabel("Rolling AR(1)")
        axes[2].set_xlabel("Index")
        axes[2].grid(True, alpha=0.3)

        fig.suptitle(f"Early Warning Signals — Alert: {report.alert_level.upper()}")
        plt.tight_layout()
        plt.show()


# ======================================================================
# Subcommand: control
# ======================================================================

def cmd_control(args: argparse.Namespace) -> None:
    from .control import ControlOptimizer
    from .model import AlderIPMSimModel
    from .parameters import get_defaults

    params = get_defaults()
    params.update(_parse_params(args.params))
    model = AlderIPMSimModel(params)
    optimizer = ControlOptimizer(model)

    ic = {"A0": params["K_0"] * 0.5, "F0": 0.1, "K0": params["K_0"], "D0": 0.0}
    user_ic = _parse_initial_state(args.initial_state)
    ic.update(user_ic)

    n_years = args.years
    comparison = optimizer.compare_strategies(ic, n_years)

    # Print the recommendation text (already formatted)
    print(comparison["recommendation_text"])

    # Write CSV output
    if args.output:
        with open(args.output, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "scenario", "cost_J", "D_star", "K_star", "rho_star",
                "u_P", "u_C", "u_B", "feasible",
            ])
            for r in comparison["results"]:
                writer.writerow([
                    r.scenario, r.cost_J, r.final_D_star, r.final_K_star,
                    r.final_rho_star,
                    r.optimal_controls["u_P"],
                    r.optimal_controls["u_C"],
                    r.optimal_controls["u_B"],
                    r.feasible,
                ])
        print(f"\nResults written to {args.output}")

    # Plot
    if args.plot:
        try:
            import matplotlib.pyplot as plt
        except ImportError:
            print("matplotlib is required for --plot. Install it with: pip install matplotlib")
            sys.exit(1)
        import numpy as np

        fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
        for r in comparison["results"]:
            traj = optimizer.multi_year_trajectory(
                r.optimal_controls, ic, n_years,
            )
            years = np.arange(n_years + 1)
            for ax, key, label in zip(
                axes.flat,
                ["A", "F", "K", "D"],
                ["Beetle density (A)", "Parasitoid density (F)",
                 "Carrying capacity (K)", "Cumulative defoliation (D)"],
            ):
                ax.plot(years, traj[key], label=f"Strategy {r.scenario}")
                ax.set_ylabel(label)
                ax.set_xlabel("Year")
                ax.grid(True, alpha=0.3)

        axes[0, 0].legend()
        fig.suptitle("Control Strategy Comparison")
        plt.tight_layout()
        plt.show()


# ======================================================================
# Subcommand: report
# ======================================================================

def cmd_report(args: argparse.Namespace) -> None:
    from .model import AlderIPMSimModel
    from .parameters import get_defaults
    from .report import ReportGenerator
    from .control import ControlOptimizer

    params = get_defaults()
    params.update(_parse_params(args.params))
    model = AlderIPMSimModel(params)

    scenario_name = args.scenario or "Custom"
    gen = ReportGenerator(params=params, scenario_name=scenario_name)

    # Simulation
    ic = {"A0": params["K_0"] * 0.5, "F0": 0.1, "K0": params["K_0"], "D0": 0.0}
    user_ic = _parse_initial_state(args.initial_state)
    ic.update(user_ic)
    n_years = args.years
    sim = model.simulate(
        A0=ic["A0"], F0=ic["F0"], K0=ic["K0"], D0=ic["D0"], n_years=n_years,
    )
    sim_lists = {k: v.tolist() if hasattr(v, "tolist") else v for k, v in sim.items()}
    gen.add_simulation(sim_lists)

    # Equilibrium
    fps = model.find_fixed_points()
    R_P = model.compute_R_P()
    R1, R2 = None, None
    try:
        R1 = model.compute_R1()
    except Exception:
        pass
    try:
        R2 = model.compute_R2()
    except Exception:
        pass
    gen.add_equilibrium(fps, R_P, R1=R1, R2=R2)

    # Control comparison
    try:
        optimizer = ControlOptimizer(params)
        initial_state = {"A": ic["A0"], "F": ic["F0"], "K": ic["K0"], "D": ic["D0"]}
        results = optimizer.compare_strategies(initial_state, n_years=n_years)
        feasible = [r for r in results if r.feasible]
        rec = None
        if feasible:
            best = min(feasible, key=lambda r: r.cost_J)
            rec = f"Scenario {best.scenario} (cost J = {best.cost_J:.4f})"
        gen.add_control(results, recommendation=rec)
    except Exception:
        pass

    html = gen.render()
    output = args.output or "alder-ipm-sim_report.html"
    with open(output, "w", encoding="utf-8") as f:
        f.write(html)
    _safe_print(f"Report written to {output}")


# ======================================================================
# Subcommand: params
# ======================================================================

def cmd_params(args: argparse.Namespace) -> None:
    from .parameters import PARAM_REGISTRY

    registry = PARAM_REGISTRY

    # Filter by category if requested
    if args.category:
        registry = {
            k: v for k, v in registry.items() if v.category == args.category
        }
        if not registry:
            print(f"No parameters found in category '{args.category}'.")
            categories = sorted({v.category for v in PARAM_REGISTRY.values()})
            print(f"Available categories: {', '.join(categories)}")
            return

    fmt = args.format or "table"

    if fmt == "json":
        out = {}
        for name, pm in registry.items():
            out[name] = {
                "symbol": pm.symbol,
                "default": pm.default,
                "min": pm.min_val,
                "max": pm.max_val,
                "unit": pm.unit,
                "description": pm.description,
                "module": pm.module,
                "category": pm.category,
            }
        print(json.dumps(out, indent=2))
        return

    if fmt == "csv":
        writer = csv.writer(sys.stdout)
        writer.writerow([
            "name", "symbol", "default", "min", "max", "unit",
            "description", "module", "category",
        ])
        for name, pm in registry.items():
            writer.writerow([
                name, pm.symbol, pm.default, pm.min_val, pm.max_val,
                pm.unit, pm.description, pm.module, pm.category,
            ])
        return

    # Default: table format
    hdr = f"{'Symbol':<10} {'Name':<12} {'Default':>10} {'Range':>20} {'Unit':<20} {'Description'}"
    _safe_print(hdr)
    _safe_print("-" * len(hdr))
    for name, pm in registry.items():
        range_str = f"[{pm.min_val}, {pm.max_val}]"
        desc = pm.description
        if len(desc) > 60:
            desc = desc[:57] + "..."
        _safe_print(
            f"{pm.symbol:<10} {name:<12} {pm.default:>10.4f} {range_str:>20} "
            f"{pm.unit:<20} {desc}"
        )


# ======================================================================
# Main entry point
# ======================================================================

def main(argv: Optional[List[str]] = None) -> None:
    parser = argparse.ArgumentParser(
        prog="alder-ipm-sim",
        description="AlderIPM-Sim: decision-support toolkit for the Alnus-beetle-parasitoid-bird ecoepidemic system.",
    )
    subparsers = parser.add_subparsers(dest="command", help="Available subcommands")

    # --- simulate ---
    p_sim = subparsers.add_parser("simulate", help="Run a forward simulation")
    p_sim.add_argument("--params", type=str, default=None,
                       help="JSON file or key=value pairs (e.g. beta=0.03,R_B=10)")
    p_sim.add_argument("--years", type=int, default=50, help="Number of years (default: 50)")
    p_sim.add_argument("--initial-state", type=str, default=None,
                       help="JSON with A0, F0, K0, D0")
    p_sim.add_argument("--output", type=str, default=None, help="Output CSV file path")
    p_sim.add_argument("--plot", action="store_true", help="Show matplotlib plot")
    p_sim.set_defaults(func=cmd_simulate)

    # --- equilibrium ---
    p_eq = subparsers.add_parser("equilibrium", help="Find and display fixed points")
    p_eq.add_argument("--params", type=str, default=None,
                      help="JSON file or key=value pairs")
    p_eq.add_argument("--verbose", action="store_true",
                      help="Show additional details (R_P, etc.)")
    p_eq.set_defaults(func=cmd_equilibrium)

    # --- fit ---
    p_fit = subparsers.add_parser("fit", help="Fit model to data")
    p_fit.add_argument("--data", type=str, required=True, help="Input CSV file")
    p_fit.add_argument("--params", type=str, default=None,
                       help="JSON file or key=value pairs for fixed params")
    p_fit.add_argument("--time-col", type=str, default=None,
                       help="Name of time column (default: year)")
    p_fit.add_argument("--state-cols", type=str, default=None,
                       help="State-column mapping (e.g. A=beetle_count,D=defoliation)")
    p_fit.add_argument("--fit-params", type=str, default=None,
                       help="Comma-separated list of params to fit")
    p_fit.add_argument("--timestep", type=str, default=None,
                       choices=["annual", "seasonal"],
                       help="Data timestep (default: annual)")
    p_fit.add_argument("--output", type=str, default=None,
                       help="Output JSON file for results")
    p_fit.set_defaults(func=cmd_fit)

    # --- warn ---
    p_warn = subparsers.add_parser("warn", help="Early warning signal analysis")
    p_warn.add_argument("--data", type=str, required=True, help="Input CSV file")
    p_warn.add_argument("--column", type=str, required=True,
                        help="Column to analyze")
    p_warn.add_argument("--window", type=int, default=None,
                        help="Rolling window size (default: 50%% of series)")
    p_warn.add_argument("--output", type=str, default=None,
                        help="Output JSON file")
    p_warn.add_argument("--plot", action="store_true", help="Show matplotlib plot")
    p_warn.set_defaults(func=cmd_warn)

    # --- control ---
    p_ctrl = subparsers.add_parser("control", help="Compare management strategies")
    p_ctrl.add_argument("--params", type=str, default=None,
                        help="JSON file or key=value pairs")
    p_ctrl.add_argument("--initial-state", type=str, default=None,
                        help="JSON with A0, F0, K0, D0")
    p_ctrl.add_argument("--years", type=int, default=50,
                        help="Number of years (default: 50)")
    p_ctrl.add_argument("--output", type=str, default=None,
                        help="Output CSV file")
    p_ctrl.add_argument("--plot", action="store_true", help="Show matplotlib plot")
    p_ctrl.set_defaults(func=cmd_control)

    # --- report ---
    p_report = subparsers.add_parser("report", help="Generate HTML analysis report")
    p_report.add_argument("--params", type=str, default=None,
                          help="JSON file or key=value pairs")
    p_report.add_argument("--initial-state", type=str, default=None,
                          help="JSON with A0, F0, K0, D0")
    p_report.add_argument("--years", type=int, default=50,
                          help="Number of simulation years (default: 50)")
    p_report.add_argument("--output", "-o", type=str, default=None,
                          help="Output HTML file (default: alder-ipm-sim_report.html)")
    p_report.add_argument("--scenario", type=str, default=None,
                          help="Scenario name for the report header")
    p_report.set_defaults(func=cmd_report)

    # --- params ---
    p_params = subparsers.add_parser("params", help="List all parameters")
    p_params.add_argument("--format", type=str, default=None,
                          choices=["table", "json", "csv"],
                          help="Output format (default: table)")
    p_params.add_argument("--category", type=str, default=None,
                          help="Filter by category")
    p_params.set_defaults(func=cmd_params)

    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    args.func(args)


if __name__ == "__main__":
    main()
