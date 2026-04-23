# install_and_test.R — One-command setup for alder-ipm-sim-r
# Usage:  Rscript install_and_test.R
#   (or source("install_and_test.R") from an R session)

cat("=== AlderIPM-Sim R — Install & Test ===\n\n")

# 1. Install CRAN dependencies
cat("[1/3] Installing CRAN dependencies...\n")
required_pkgs <- c("deSolve", "rootSolve")
optional_pkgs <- c("ggplot2", "shiny", "testthat", "devtools")
all_pkgs <- c(required_pkgs, optional_pkgs)

to_install <- all_pkgs[!vapply(all_pkgs, requireNamespace, logical(1), quietly = TRUE)]
if (length(to_install) > 0) {
  install.packages(to_install, repos = "https://cloud.r-project.org", quiet = TRUE)
  cat("  Installed:", paste(to_install, collapse = ", "), "\n")
} else {
  cat("  All dependencies already installed.\n")
}

# 2. Install the package itself
cat("[2/3] Installing alder-ipm-sim from source...\n")
if (!requireNamespace("devtools", quietly = TRUE)) {
  stop("devtools is required but could not be installed.")
}
devtools::install(pkg = ".", reload = TRUE, quiet = TRUE, upgrade = "never")

# 3. Run tests
cat("[3/3] Running test suite...\n\n")
results <- devtools::test(pkg = ".")
cat("\n")

# Summary
failed <- sum(as.data.frame(results)$failed)
if (failed == 0) {
  cat("============================================\n")
  cat("  Setup complete — all tests passed!\n")
  cat("============================================\n\n")
  cat("Next steps:\n")
  cat("  library(alderIPMSim)\n")
  cat("  params <- param_defaults()             # view default parameters\n")
  cat("  result <- simulate_model(params, 50)   # 50-year simulation\n")
  cat("  run_app()                              # launch Shiny dashboard\n\n")
} else {
  cat("WARNING:", failed, "test(s) failed. Check output above.\n")
}
