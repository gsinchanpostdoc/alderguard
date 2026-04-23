# Installation Guide for AlderIPM-Sim (R)

## One-Command Setup

The fastest way to get started — installs CRAN dependencies, builds the package, and runs all tests:

```bash
Rscript install_and_test.R
```

## Manual Installation

### Prerequisites

- R >= 4.0.0
- Required packages: `deSolve`, `rootSolve`
- Optional packages: `shiny`, `shinydashboard`, `ggplot2`, `plotly`, `DT`,
  `jsonlite`, `DEoptim`, `testthat`, `knitr`, `rmarkdown`

## Install from Source (Local)

From the repository root directory:

```r
install.packages("alder-ipm-sim-r", repos = NULL, type = "source")
```

Or from within the `alder-ipm-sim-r/` directory:

```r
install.packages(".", repos = NULL, type = "source")
```

## Install with devtools

```r
# install.packages("devtools")
devtools::install("alder-ipm-sim-r")
```

## Install from GitHub

```r
devtools::install_github("alder-ipm-sim/alder-ipm-sim-r")
```

## Install Dependencies

```r
install.packages(c("deSolve", "rootSolve"))

# Optional: for Shiny dashboard
install.packages(c("shiny", "shinydashboard", "ggplot2", "plotly", "DT", "jsonlite"))

# Optional: for global parameter estimation
install.packages("DEoptim")
```

## Verify Installation

```r
library(alderIPMSim)
params <- default_params()
cat("AlderIPM-Sim loaded successfully. Default beta =", params[["beta"]], "\n")
```

## Running Tests

```r
# From the alder-ipm-sim-r/ directory
devtools::test()

# Or using testthat directly
testthat::test_dir("tests/testthat")
```

## Launch the Shiny Dashboard

```r
library(alderIPMSim)
run_app()
```

This opens the interactive web dashboard at `http://localhost:3838` with tabs
for simulation, fitting, early warning analysis, and control strategy
comparison.

## Building the Vignette

```r
devtools::build_vignettes()
browseVignettes("alder-ipm-sim")
```
