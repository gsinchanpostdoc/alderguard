# AlderIPM-Sim (R)

R package for decision support in the *Alnus glutinosa* -- beetle -- parasitoid -- bird ecoepidemic system. Simulate multi-year ecosystem dynamics, estimate parameters from field data, detect early warning signals of regime shifts, and evaluate integrated pest management strategies.

## Quick Setup (Recommended)

Run the one-command setup script to install all dependencies, build the package, and run the test suite:

```bash
Rscript install_and_test.R
```

## Manual Installation

```r
# From local source (from repository root)
install.packages("alder-ipm-sim-r", repos = NULL, type = "source")

# With devtools
devtools::install("alder-ipm-sim-r")

# From GitHub
devtools::install_github("alder-ipm-sim/alder-ipm-sim-r")
```

See [INSTALL.md](INSTALL.md) for detailed instructions and dependency setup.

## Quick Start

```r
library(alderIPMSim)

# Get default parameters
params <- as.list(default_params())
params$u_C <- 0
params$u_P <- 0

# Run a 50-year simulation
traj <- simulate(params, A0 = 0.8, F0 = 0.1, K0 = 1.712, D0 = 0, n_years = 50)
plot(traj$year, traj$A, type = "l", xlab = "Year", ylab = "Beetle density")

# Compute parasitoid reproduction number
R_P <- compute_RP(params)
cat("R_P =", round(R_P, 3), "\n")

# Detect early warning signals
warnings <- detect_warnings(traj$A)
cat("Alert level:", warnings$alert_level, "\n")
```

## Core Functions

### Parameters
| Function | Description |
|---|---|
| `param_registry()` | Full parameter metadata registry |
| `default_params()` | Named vector of default parameter values |
| `validate_params()` | Check parameter bounds |
| `print_params()` | Pretty-print parameter table |

### Simulation (Module 1 & 2)
| Function | Description |
|---|---|
| `within_season_ode()` | Within-season ODE right-hand side |
| `integrate_season()` | Integrate within-season dynamics |
| `annual_map()` | One step of the annual discrete map |
| `simulate()` | Multi-year simulation |
| `compute_RP()` | Parasitoid invasion reproduction number |

### Equilibrium Analysis
| Function | Description |
|---|---|
| `find_fixed_points()` | Find equilibria from multiple starting points |
| `jacobian_numerical()` | Numerical Jacobian of the annual map |
| `classify_stability()` | Stability and bifurcation classification |

### Data Fitting
| Function | Description |
|---|---|
| `prepare_data()` | Validate and prepare data for fitting |
| `fit_model()` | Parameter estimation (NLS, L-BFGS-B, DE) |
| `predict_trajectory()` | Forward projection with uncertainty |
| `forecast_regime()` | Regime classification from fitted params |

### Early Warning Signals
| Function | Description |
|---|---|
| `detrend_ts()` | Remove slow trends |
| `rolling_variance()` | Rolling-window variance |
| `rolling_autocorrelation()` | Rolling lag-k autocorrelation |
| `rolling_skewness()` | Rolling skewness |
| `compute_ews()` | All EWS indicators in one call |
| `kendall_trend()` | Kendall tau trend test |
| `detect_warnings()` | Full EWS pipeline with alert level |

### Control Optimisation
| Function | Description |
|---|---|
| `optimize_scenario()` | Optimise control for scenario A, B, or C |
| `compare_strategies()` | Compare all three management strategies |
| `feasibility_check()` | Check ecological feasibility criteria |

### Interactive Dashboard
| Function | Description |
|---|---|
| `run_app()` | Launch Shiny web dashboard |

## Example Data

The package includes example datasets in `inst/extdata/`:

- `example_stable_coexistence.csv` -- 30-year trajectory converging to a stable coexistence equilibrium
- `example_approaching_tipping.csv` -- 30-year trajectory approaching a tipping point

```r
f <- system.file("extdata", "example_stable_coexistence.csv", package = "alder-ipm-sim")
data <- read.csv(f)
prepared <- prepare_data(data, time_col = "year")
```

## Shiny Dashboard

Launch the interactive dashboard for real-time exploration:

```r
alderIPMSim::run_app()
```

The dashboard provides tabs for:
- **Simulation**: adjust parameters and visualise trajectories
- **Fitting**: upload field data and estimate parameters
- **Early Warnings**: detect critical slowing down indicators
- **Control**: compare management strategies A, B, and C

## Testing

```r
devtools::test()
```

## Vignette

```r
vignette("alderipmsim-workflow", package = "alder-ipm-sim")
```

## Documentation

Additional user guides are available in the `docs/` directory:

- [Forest Managers Guide](docs/user_guide_managers.md)
- [Conservation Scientists Guide](docs/user_guide_conservation.md)
- [Researchers Guide](docs/user_guide_researchers.md)
- [Data Format Specification](docs/data_format.md)

## Dependencies

**Required**: `deSolve`, `rootSolve`

**Optional**: `shiny`, `shinydashboard`, `ggplot2`, `plotly`, `DT`, `jsonlite`, `DEoptim`, `testthat`, `knitr`, `rmarkdown`

## Citation

```r
citation("alder-ipm-sim")
```

## License

MIT License. See [LICENSE](LICENSE) for details.
