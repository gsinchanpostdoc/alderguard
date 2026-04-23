#' @title Parameter Registry for the Alnus-Beetle-Parasitoid-Bird Model
#' @description Functions for accessing, validating, and displaying model parameters.

#' Return the full parameter registry as a named list of lists.
#'
#' Each element contains: symbol, default, min, max, unit, description, module, category.
#' Values are identical to the Python \code{PARAM_REGISTRY}.
#'
#' @return Named list of parameter metadata lists.
#' @export
param_registry <- function() {
  reg <- list(
    beta = list(
      symbol = "beta", default = 0.0301, min = 0.005, max = 0.04,
      unit = "/day",
      description = paste(
        "Parasitoid attack rate (Holling Type II functional response numerator;",
        "rate at which adult Meigenia mutabilis parasitoids successfully oviposit",
        "into Agelastica alni beetle larvae)"
      ),
      module = "within_season", category = "biotic_rate"
    ),
    h = list(
      symbol = "h", default = 0.00575, min = 0.001, max = 0.01,
      unit = "days",
      description = paste(
        "Parasitoid handling time (time-limiting saturation parameter in Holling II",
        "response; represents search-and-oviposition time per host)"
      ),
      module = "within_season", category = "biotic_rate"
    ),
    c_B = list(
      symbol = "c_B", default = 0.0209, min = 0.01, max = 0.03,
      unit = "/day",
      description = paste(
        "Bird per-unit consumption rate coefficient (rate at which generalist",
        "passeriform birds consume beetle larvae)"
      ),
      module = "within_season", category = "biotic_rate"
    ),
    a_B = list(
      symbol = "a_B", default = 0.00651, min = 0.0001, max = 0.02,
      unit = "days",
      description = paste(
        "Bird half-saturation parameter (Holling II; larval density at which bird",
        "predation reaches half its maximum)"
      ),
      module = "within_season", category = "biotic_rate"
    ),
    mu_S = list(
      symbol = "mu_S", default = 0.00423, min = 0.003, max = 0.03,
      unit = "/day",
      description = paste(
        "Background mortality rate of susceptible (unparasitised) beetle larvae",
        "(natural death from desiccation, disease, intraspecific competition)"
      ),
      module = "within_season", category = "mortality"
    ),
    mu_I = list(
      symbol = "mu_I", default = 0.0443, min = 0.02, max = 0.08,
      unit = "/day",
      description = paste(
        "Background mortality rate of parasitised beetle larvae (higher than mu_S",
        "due to physiological burden of parasitoid development)"
      ),
      module = "within_season", category = "mortality"
    ),
    delta = list(
      symbol = "delta", default = 0.1918, min = 0.05, max = 0.25,
      unit = "/day",
      description = paste(
        "Parasitoid-induced mortality rate (rate at which parasitoid emergence kills",
        "the host larva; temperature-dependent development)"
      ),
      module = "within_season", category = "mortality"
    ),
    eta = list(
      symbol = "eta", default = 0.7054, min = 0.5, max = 1.0,
      unit = "dimensionless",
      description = paste(
        "Parasitoid conversion efficiency (number of new adult parasitoid flies",
        "produced per parasitised host that undergoes emergence)"
      ),
      module = "within_season", category = "biotic_rate"
    ),
    mu_F = list(
      symbol = "mu_F", default = 0.0309, min = 0.01, max = 0.08,
      unit = "/day",
      description = "Baseline natural mortality of adult parasitoid flies",
      module = "within_season", category = "mortality"
    ),
    kappa = list(
      symbol = "kappa", default = 0.00273, min = 0.0001, max = 0.003,
      unit = "/day",
      description = paste(
        "Defoliation conversion rate (rate at which larval feeding density",
        "translates to fractional canopy loss per day)"
      ),
      module = "within_season", category = "biotic_rate"
    ),
    T = list(
      symbol = "T", default = 49.9, min = 45.0, max = 70.0,
      unit = "days",
      description = paste(
        "Duration of larval vulnerability window (spring-summer period when beetle",
        "larvae are active and exposed to parasitism/predation)"
      ),
      module = "within_season", category = "phenology"
    ),
    B_index = list(
      symbol = "B_idx", default = 1.59, min = 0.5, max = 2.0,
      unit = "dimensionless",
      description = paste(
        "Exogenous bird predation pressure index (scaled from PECBMS passerine",
        "monitoring data; reflects regional bird abundance)"
      ),
      module = "within_season", category = "biotic_rate"
    ),
    R_B = list(
      symbol = "R_B", default = 9.53, min = 6.0, max = 16.0,
      unit = "dimensionless",
      description = paste(
        "Beetle annual reproduction ratio (Beverton-Holt fecundity; expected",
        "offspring per adult surviving to reproduce)"
      ),
      module = "annual", category = "biotic_rate"
    ),
    sigma_A = list(
      symbol = "sigma_A", default = 0.781, min = 0.5, max = 0.9,
      unit = "dimensionless",
      description = paste(
        "Beetle overwintering survival probability (fraction surviving pupation,",
        "winter dormancy, spring emergence, and mating)"
      ),
      module = "annual", category = "mortality"
    ),
    sigma_F = list(
      symbol = "sigma_F", default = 0.363, min = 0.3, max = 0.7,
      unit = "dimensionless",
      description = paste(
        "Parasitoid overwinter survival probability (fraction of parasitoid puparia",
        "surviving in soil through winter)"
      ),
      module = "annual", category = "mortality"
    ),
    K_0 = list(
      symbol = "K_0", default = 1.712, min = 1.0, max = 2.0,
      unit = "relative units",
      description = paste(
        "Baseline carrying capacity (maximum beetle recruitment capacity under",
        "fully recovered, undamaged canopy)"
      ),
      module = "annual", category = "threshold"
    ),
    phi = list(
      symbol = "phi", default = 0.0449, min = 0.01, max = 0.1,
      unit = "dimensionless",
      description = paste(
        "Foliage-feedback penalty coefficient (strength of induced phytochemical",
        "defence; K_t = K_0 * exp(-phi * D_t))"
      ),
      module = "annual", category = "phenology"
    ),
    rho = list(
      symbol = "rho", default = 0.5, min = 0.0, max = 1.0,
      unit = "dimensionless",
      description = paste(
        "Bird-habitat enhancement coupling coefficient (scales the effect of",
        "u_B on bird predation pressure: B_eff = B_index * (1 + rho * u_B))."
      ),
      module = "annual", category = "biotic_rate"
    ),
    u_P_max = list(
      symbol = "u_P_max", default = 0.5, min = 0.0, max = 1.0,
      unit = "individuals/ha/day",
      description = "Maximum parasitoid augmentation effort",
      module = "annual", category = "control"
    ),
    u_C_max = list(
      symbol = "u_C_max", default = 0.2, min = 0.0, max = 1.0,
      unit = "individuals/ha/day",
      description = "Maximum direct larval removal effort",
      module = "annual", category = "control"
    ),
    u_B_max = list(
      symbol = "u_B_max", default = 1.0, min = 0.0, max = 2.0,
      unit = "relative units",
      description = "Maximum annual bird-habitat enhancement",
      module = "annual", category = "control"
    ),
    D_crit = list(
      symbol = "D_crit", default = 0.5, min = 0.0, max = 1.0,
      unit = "dimensionless",
      description = paste(
        "Critical defoliation threshold (canopy loss exceeding 50% triggers",
        "collapse risk)"
      ),
      module = "annual", category = "threshold"
    ),
    K_min = list(
      symbol = "K_min", default = 0.856, min = 0.0, max = 1.0,
      unit = "relative units",
      description = "Minimum carrying capacity for viable beetle population (0.5 * K_0)",
      module = "annual", category = "threshold"
    )
  )
  reg
}

#' Return preset scenario definitions for climate and management analysis.
#'
#' Each preset is a named list with: name, description, params (overrides),
#' expected_regime, and manuscript_ref.
#'
#' @return Named list of preset scenario definitions.
#' @export
preset_scenarios <- function() {
  list(
    baseline_calibrated = list(
      name = "Baseline Calibrated",
      description = paste(
        "Current calibrated parameter values fitted to field observations.",
        "Represents the present-day Alnus glutinosa-beetle-parasitoid-bird system."
      ),
      params = list(
        beta = 0.0301, h = 0.00575, c_B = 0.0209, a_B = 0.00651,
        mu_S = 0.00423, mu_I = 0.0443, delta = 0.1918, eta = 0.7054,
        mu_F = 0.0309, kappa = 0.00273, T = 49.9, B_index = 1.59,
        R_B = 9.53, sigma_A = 0.781, sigma_F = 0.363, K_0 = 1.712,
        phi = 0.0449
      ),
      expected_regime = "coexistence",
      manuscript_ref = "Table 1 and Section 2.1"
    ),
    warm_winter = list(
      name = "Warm Winter",
      description = paste(
        "Warmer winters increase beetle and parasitoid overwintering survival",
        "and extend the larval season, raising outbreak risk under climate change."
      ),
      params = list(sigma_A = 0.88, sigma_F = 0.55, T = 55),
      expected_regime = "parasitoid_free",
      manuscript_ref = "Section 3.3 -- phenological sensitivity analysis"
    ),
    short_season = list(
      name = "Short Season",
      description = paste(
        "Cooler or delayed springs shorten the larval vulnerability window,",
        "reduce beetle survival, and lower fecundity."
      ),
      params = list(T = 45, sigma_A = 0.6, R_B = 7.0),
      expected_regime = "coexistence",
      manuscript_ref = "Section 3.3 -- phenological sensitivity analysis"
    ),
    high_bird_pressure = list(
      name = "High Bird Pressure",
      description = paste(
        "Enhanced avian predation through increased passerine abundance and",
        "higher per-capita consumption, simulating bird-habitat management."
      ),
      params = list(B_index = 1.9, c_B = 0.025),
      expected_regime = "coexistence",
      manuscript_ref = "Section 3.4 -- bird predation impact"
    ),
    low_parasitism = list(
      name = "Low Parasitism",
      description = paste(
        "Weak parasitoid control due to low attack rate, poor conversion",
        "efficiency, and slow parasitoid-induced mortality."
      ),
      params = list(beta = 0.01, eta = 0.5, delta = 0.1),
      expected_regime = "parasitoid_free",
      manuscript_ref = "Section 3.2 -- parasitoid efficacy analysis"
    ),
    outbreak_risk = list(
      name = "Outbreak Risk",
      description = paste(
        "High beetle fecundity with elevated overwintering survival and",
        "weak canopy feedback creates conditions for severe defoliation outbreaks."
      ),
      params = list(R_B = 14.0, sigma_A = 0.85, phi = 0.02),
      expected_regime = "parasitoid_free",
      manuscript_ref = "Section 3.5 -- tipping point analysis"
    ),
    managed_forest = list(
      name = "Managed Forest",
      description = paste(
        "Integrated pest management combining parasitoid augmentation,",
        "direct larval removal, and bird-habitat enhancement (Strategy C optimal)."
      ),
      params = list(u_P_max = 0.5, u_C_max = 0.2, u_B_max = 1.0),
      expected_regime = "coexistence",
      manuscript_ref = "Section 4 -- optimal control comparison"
    )
  )
}

#' Return a named list of default parameter values.
#'
#' @return Named list mapping parameter names to their default values.
#' @export
default_params <- function() {
  reg <- param_registry()
  vapply(reg, function(x) x$default, numeric(1))
}

#' Validate parameter values against registered bounds.
#'
#' @param params Named list or named numeric vector of parameter values.
#' @return Character vector of warning messages (empty if all valid).
#' @export
validate_params <- function(params) {
  reg <- param_registry()
  warnings_out <- character(0)
  for (nm in names(params)) {
    meta <- reg[[nm]]
    if (is.null(meta)) next
    val <- params[[nm]]
    if (val < meta$min || val > meta$max) {
      warnings_out <- c(warnings_out, sprintf(
        "Parameter '%s' (%s) = %g is outside [%g, %g]. %s",
        nm, meta$symbol, val, meta$min, meta$max, meta$description
      ))
    }
  }
  if (length(warnings_out) > 0) {
    for (w in warnings_out) warning(w, call. = FALSE)
  }
  invisible(warnings_out)
}

#' Pretty-print parameter table to console.
#'
#' @param params Named numeric vector of parameter values. If NULL, uses defaults.
#' @param category Optional category filter (e.g. "biotic_rate", "mortality").
#' @export
print_params <- function(params = NULL, category = NULL) {
  reg <- param_registry()
  if (is.null(params)) params <- default_params()

  # Filter by category if requested
  if (!is.null(category)) {
    keep <- vapply(reg, function(x) x$category == category, logical(1))
    reg <- reg[keep]
  }

  # Header
  cat(sprintf("%-12s %-8s %12s %12s %12s  %-20s  %s\n",
              "Name", "Symbol", "Value", "Min", "Max", "Unit", "Module"))
  cat(paste(rep("-", 100), collapse = ""), "\n")

  for (nm in names(reg)) {
    meta <- reg[[nm]]
    val <- if (!is.null(params[[nm]])) params[[nm]] else meta$default
    cat(sprintf("%-12s %-8s %12.5g %12.5g %12.5g  %-20s  %s\n",
                nm, meta$symbol, val, meta$min, meta$max, meta$unit, meta$module))
  }
  invisible(NULL)
}
