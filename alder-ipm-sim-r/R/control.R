#' @title Optimal Control Strategy Evaluation
#' @description Evaluate and compare integrated pest management strategies for the
#'   Alnus-beetle-parasitoid-bird ecoepidemic system.

# Default cost-functional weights (manuscript Table 3)
.DEFAULT_COST_WEIGHTS <- list(
  W_D = 10,      # weight on cumulative defoliation
  W_S = 1,       # weight on susceptible larvae density
  W_T = 5,       # terminal cost on end-of-season defoliation
  C_P = 2,       # cost per unit parasitoid augmentation
  C_C = 5,       # cost per unit direct larval removal
  C_B = 3        # annual cost per unit bird-habitat enhancement
)

# Get cost weights, allowing override from params
.get_cost_weights <- function(params) {
  W <- .DEFAULT_COST_WEIGHTS
  if (!is.null(params[["w_D"]])) W$W_D <- params[["w_D"]]
  if (!is.null(params[["w_S"]])) W$W_S <- params[["w_S"]]
  if (!is.null(params[["w_T"]])) W$W_T <- params[["w_T"]]
  if (!is.null(params[["c_P_cost"]])) W$C_P <- params[["c_P_cost"]]
  if (!is.null(params[["c_C_cost"]])) W$C_C <- params[["c_C_cost"]]
  if (!is.null(params[["c_B_cost"]])) W$C_B <- params[["c_B_cost"]]
  W
}

# Scenario definitions: which controls are free
.SCENARIOS <- list(
  A = list(u_P = TRUE,  u_C = FALSE, u_B = FALSE),
  B = list(u_P = TRUE,  u_C = FALSE, u_B = TRUE),
  C = list(u_P = TRUE,  u_C = TRUE,  u_B = TRUE)
)

#' Optimize control for a management scenario.
#'
#' Minimises a cost functional that penalises defoliation, larval density, and
#' control effort over a multi-year horizon. Uses \code{stats::optim} with
#' L-BFGS-B for bounded optimisation.
#'
#' Three scenarios are available:
#' \itemize{
#'   \item \strong{A}: Parasitoid augmentation only (u_P free; u_C = u_B = 0).
#'   \item \strong{B}: Parasitoid augmentation + bird habitat enhancement (u_P,
#'     u_B free; u_C = 0).
#'   \item \strong{C}: Full integrated control (u_P, u_C, u_B all free).
#' }
#'
#' @param params Named list of parameters (from \code{\link{default_params}}).
#' @param scenario Character: \code{"A"}, \code{"B"}, or \code{"C"}.
#' @param initial_state Named numeric vector \code{c(A=, F=, K=, D=)}.
#' @param n_years Integer simulation horizon (default 50).
#' @return A list with components: \code{scenario} (character),
#'   \code{optimal_controls} (named numeric), \code{cost} (numeric),
#'   \code{final_equilibrium} (named numeric), \code{D_star} (numeric),
#'   \code{K_star} (numeric), \code{rho_star} (numeric), \code{feasible}
#'   (logical), \code{violations} (character vector).
#' @examples
#' params <- as.list(default_params())
#' params$u_C <- 0; params$u_P <- 0
#' ic <- c(A = 0.8, F = 0.1, K = 1.712, D = 0)
#' result <- optimize_scenario(params, scenario = "A", initial_state = ic, n_years = 10)
#' cat("Cost:", result$cost, "Feasible:", result$feasible, "\n")
#' @export
optimize_scenario <- function(params, scenario = "C", initial_state, n_years = 50) {
  if (!scenario %in% names(.SCENARIOS))
    stop("Unknown scenario '", scenario, "'. Choose from A, B, C.")

  free <- .SCENARIOS[[scenario]]

  # Build bounds for free controls
  free_keys <- character(0)
  lower <- numeric(0)
  upper <- numeric(0)
  if (free$u_P) {
    free_keys <- c(free_keys, "u_P")
    lower <- c(lower, 0)
    upper <- c(upper, params[["u_P_max"]])
  }
  if (free$u_C) {
    free_keys <- c(free_keys, "u_C")
    lower <- c(lower, 0)
    upper <- c(upper, params[["u_C_max"]])
  }
  if (free$u_B) {
    free_keys <- c(free_keys, "u_B")
    lower <- c(lower, 0)
    upper <- c(upper, params[["u_B_max"]])
  }

  # Objective: total cost over n_years
  obj_fn <- function(x) {
    ctrl <- c(u_P = 0, u_C = 0, u_B = 0)
    for (i in seq_along(free_keys)) ctrl[[free_keys[i]]] <- x[i]
    .objective_functional(params, ctrl, initial_state, n_years)
  }

  x0 <- rep(0.01, length(free_keys))

  opt <- stats::optim(
    par = x0, fn = obj_fn, method = "L-BFGS-B",
    lower = lower, upper = upper,
    control = list(maxit = 2000, factr = 1e7)
  )

  optimal_ctrl <- c(u_P = 0, u_C = 0, u_B = 0)
  for (i in seq_along(free_keys)) optimal_ctrl[[free_keys[i]]] <- opt$par[i]

  # Evaluate terminal state
  traj <- .controlled_trajectory(params, optimal_ctrl, initial_state, n_years)
  n <- nrow(traj)
  A_end <- traj$A[n]; F_end <- traj$F[n]; K_end <- traj$K[n]; D_end <- traj$D[n]

  # Spectral radius at terminal state
  ctrl_params <- params
  ctrl_params[["u_C"]] <- optimal_ctrl[["u_C"]]
  ctrl_params[["u_P"]] <- optimal_ctrl[["u_P"]]
  ctrl_params[["B_index"]] <- params[["B_index"]] * (1 + params[["rho"]] * optimal_ctrl[["u_B"]])

  rho_star <- tryCatch({
    jac <- jacobian_numerical(ctrl_params, c(A_end, F_end, K_end, D_end))
    stab <- classify_stability(jac)
    stab$rho_star
  }, error = function(e) NA_real_)

  feas <- feasibility_check(D_end, K_end, rho_star, F_end, params,
                            K_trajectory = traj$K)

  list(
    scenario = scenario,
    optimal_controls = optimal_ctrl,
    cost = opt$value,
    final_equilibrium = c(A = A_end, F = F_end, K = K_end, D = D_end),
    D_star = D_end,
    K_star = K_end,
    rho_star = rho_star,
    feasible = feas$feasible,
    violations = feas$violations
  )
}

#' Compare all three management strategies.
#'
#' Runs \code{\link{optimize_scenario}} for scenarios A, B, and C and returns a
#' comparison table with a recommended strategy.
#'
#' @param params Named list of parameters.
#' @param initial_state Named numeric vector \code{c(A=, F=, K=, D=)}.
#' @param n_years Integer simulation horizon (default 50).
#' @return A list with components: \code{comparison} (data.frame with one row
#'   per scenario), \code{recommended} (character scenario label or \code{NA}),
#'   and \code{interpretation} (character string with plain-language guidance).
#' @examples
#' \dontrun{
#' params <- as.list(default_params())
#' params$u_C <- 0; params$u_P <- 0
#' ic <- c(A = 0.8, F = 0.1, K = 1.712, D = 0)
#' comp <- compare_strategies(params, initial_state = ic, n_years = 10)
#' print(comp$comparison)
#' }
#' @export
compare_strategies <- function(params, initial_state, n_years = 50) {
  results <- lapply(c("A", "B", "C"), function(sc) {
    optimize_scenario(params, scenario = sc, initial_state = initial_state,
                      n_years = n_years)
  })

  comparison <- data.frame(
    scenario = vapply(results, `[[`, character(1), "scenario"),
    cost = vapply(results, `[[`, numeric(1), "cost"),
    D_star = vapply(results, `[[`, numeric(1), "D_star"),
    K_star = vapply(results, `[[`, numeric(1), "K_star"),
    rho_star = vapply(results, `[[`, numeric(1), "rho_star"),
    feasible = vapply(results, `[[`, logical(1), "feasible"),
    stringsAsFactors = FALSE
  )

  feasible_idx <- which(comparison$feasible)
  if (length(feasible_idx) > 0) {
    best <- feasible_idx[which.min(comparison$cost[feasible_idx])]
    recommended <- comparison$scenario[best]
  } else {
    recommended <- NA_character_
  }

  interpretation <- .build_strategy_recommendation(results, recommended)

  list(
    comparison = comparison,
    recommended = recommended,
    interpretation = interpretation
  )
}

#' Check feasibility of a management outcome.
#'
#' Evaluates whether all ecological and stability criteria are satisfied.
#'
#' @param D_star Numeric equilibrium defoliation.
#' @param K_star Numeric equilibrium carrying capacity.
#' @param rho_star Numeric spectral radius of the Jacobian.
#' @param F_star Numeric equilibrium parasitoid density.
#' @param params Named list of parameters (needs D_crit and K_min).
#' @return A list with components \code{feasible} (logical) and
#'   \code{violations} (character vector).
#' @examples
#' params <- as.list(default_params())
#' # Feasible outcome
#' feasibility_check(0.3, 1.5, 0.8, 0.05, params)
#' # Infeasible: defoliation exceeds D_crit
#' feasibility_check(0.6, 1.5, 0.8, 0.05, params)
#' @export
feasibility_check <- function(D_star, K_star, rho_star, F_star, params,
                              K_trajectory = NULL) {
  violations <- character(0)

  if (D_star >= params[["D_crit"]])
    violations <- c(violations,
      sprintf("Defoliation D* = %.4f >= D_crit = %s", D_star, params[["D_crit"]]))

  # Check K trajectory for 3+ consecutive years below K_min (Section 2.4)
  K_min <- params[["K_min"]]
  if (!is.null(K_trajectory)) {
    consec <- 0; max_consec <- 0
    for (Kv in K_trajectory) {
      if (Kv <= K_min) { consec <- consec + 1; max_consec <- max(max_consec, consec) }
      else consec <- 0
    }
    if (max_consec >= 3)
      violations <- c(violations,
        sprintf("Carrying capacity below K_min for %d consecutive years", max_consec))
  } else if (K_star <= K_min) {
    violations <- c(violations,
      sprintf("Carrying capacity K* = %.4f <= K_min = %s", K_star, K_min))
  }

  if (F_star <= 0)
    violations <- c(violations, "Parasitoid population extinct (F* <= 0)")

  if (!is.na(rho_star) && rho_star >= 1.001)
    violations <- c(violations,
      sprintf("Equilibrium unstable (rho* = %.4f >= 1.001)", rho_star))

  list(feasible = length(violations) == 0, violations = violations)
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

#' @noRd
.objective_functional <- function(params, ctrl, initial_state, n_years) {
  p <- params
  p[["u_C"]] <- ctrl[["u_C"]]
  p[["u_P"]] <- ctrl[["u_P"]]
  p[["B_index"]] <- params[["B_index"]] * (1 + params[["rho"]] * ctrl[["u_B"]])

  A_t <- initial_state[["A"]]
  F_t <- initial_state[["F"]]
  K_t <- initial_state[["K"]]
  D_t <- initial_state[["D"]]

  W <- .get_cost_weights(params)
  total_cost <- 0

  for (yr in seq_len(n_years)) {
    # Beverton-Holt recruitment at season start (Eq. 5)
    S0_bh <- p[["R_B"]] * A_t / (1 + A_t / K_t)
    result <- tryCatch(
      integrate_season(p, S0 = S0_bh, I0 = 0, F0 = F_t, D0 = 0),
      error = function(e) NULL
    )
    if (is.null(result)) return(1e12)

    traj <- result$trajectory
    S_vals <- pmax(traj$S, 0)
    D_vals <- traj$D
    t_vals <- traj$time

    # Trapezoidal integration of running cost
    integrand <- W$W_D * D_vals + W$W_S * S_vals + W$C_P * ctrl[["u_P"]] + W$C_C * ctrl[["u_C"]]
    n_pts <- length(t_vals)
    if (n_pts > 1) {
      dt <- diff(t_vals)
      season_cost <- sum(dt * (integrand[-n_pts] + integrand[-1]) / 2)
    } else {
      season_cost <- 0
    }

    # Terminal cost
    season_cost <- season_cost + W$W_T * D_vals[n_pts]
    total_cost <- total_cost + season_cost

    # Annual map update (Beverton-Holt at start, overwinter survival at end)
    end <- result$end
    S_T <- end$S_T; F_T <- end$F_T; D_T <- end$D_T
    A_t <- p[["sigma_A"]] * S_T
    F_t <- p[["sigma_F"]] * F_T
    K_t <- p[["K_0"]] * exp(-p[["phi"]] * D_T)
    D_t <- D_T
  }

  # Annual bird-habitat enhancement cost
  total_cost <- total_cost + W$C_B * ctrl[["u_B"]] * n_years

  total_cost
}

#' @noRd
.controlled_trajectory <- function(params, ctrl, initial_state, n_years) {
  p <- params
  p[["u_C"]] <- ctrl[["u_C"]]
  p[["u_P"]] <- ctrl[["u_P"]]
  p[["B_index"]] <- params[["B_index"]] * (1 + params[["rho"]] * ctrl[["u_B"]])

  simulate(p, A0 = initial_state[["A"]], F0 = initial_state[["F"]],
           K0 = initial_state[["K"]], D0 = initial_state[["D"]],
           n_years = n_years)
}

#' @noRd
.build_strategy_recommendation <- function(results, recommended) {
  scenario_desc <- list(
    A = paste("Strategy A -- Parasitoid augmentation only: relies solely on",
              "releasing laboratory-reared parasitoid flies."),
    B = paste("Strategy B -- Parasitoid augmentation + bird habitat: combines",
              "parasitoid releases with nest boxes and hedgerow planting to",
              "boost avian predation."),
    C = paste("Strategy C -- Full integrated control: adds targeted larval",
              "removal (mechanical or biopesticide) on top of Strategy B.")
  )

  lines <- "=== Management Strategy Comparison ===\n"

  for (r in results) {
    sc <- r$scenario
    lines <- paste0(lines, "\n", scenario_desc[[sc]])
    lines <- paste0(lines, sprintf("\n  Cost J = %.2f", r$cost))
    lines <- paste0(lines, sprintf(
      "\n  Final defoliation D* = %.4f, capacity K* = %.4f, spectral radius rho* = %.4f",
      r$D_star, r$K_star, r$rho_star))
    status <- if (r$feasible) "FEASIBLE"
              else paste0("INFEASIBLE (", paste(r$violations, collapse = "; "), ")")
    lines <- paste0(lines, "\n  Status: ", status, "\n")
  }

  if (!is.na(recommended)) {
    r_best <- Filter(function(r) r$scenario == recommended, results)[[1]]
    lines <- paste0(lines, sprintf(
      "\nRecommendation: Strategy %s achieves the management objectives at lowest cost (J = %.2f).",
      recommended, r_best$cost))

    if (recommended == "A") {
      lines <- paste0(lines, "\n",
        "Parasitoid augmentation alone is sufficient. Managers should plan",
        " periodic releases of laboratory-reared Meigenia mutabilis at the optimal rate.")
    } else if (recommended == "B") {
      lines <- paste0(lines, "\n",
        "Combining parasitoid releases with bird habitat enhancement is recommended.",
        " Install nest boxes and plant hedgerows to sustain avian predation",
        " alongside biocontrol releases.")
    } else {
      lines <- paste0(lines, "\n",
        "Full integrated control is necessary. In addition to parasitoid releases",
        " and bird habitat enhancement, managers should implement targeted larval",
        " removal (mechanical collection or Bacillus thuringiensis application).")
    }
  } else {
    lines <- paste0(lines, "\n",
      "WARNING: No strategy met all feasibility criteria within the optimisation",
      " bounds. Consider increasing control budgets, extending the management",
      " horizon, or revising management targets.")
  }

  lines
}

#' Evaluate a user-defined control combination.
#'
#' Runs the controlled trajectory with the given control intensities (no
#' optimisation) and returns the same output structure as
#' \code{\link{optimize_scenario}} with \code{scenario = "Custom"}.
#'
#' @param params Named list of parameters (from \code{\link{default_params}}).
#' @param u_P Numeric parasitoid augmentation intensity.
#' @param u_C Numeric direct larval removal intensity.
#' @param u_B Numeric bird-habitat enhancement intensity.
#' @param initial_state Named numeric vector \code{c(A=, F=, K=, D=)}.
#' @param n_years Integer simulation horizon (default 50).
#' @return A list with the same components as \code{\link{optimize_scenario}}.
#' @export
custom_strategy <- function(params, u_P, u_C, u_B, initial_state, n_years = 50) {
  ctrl <- c(u_P = u_P, u_C = u_C, u_B = u_B)
  cost <- .objective_functional(params, ctrl, initial_state, n_years)
  traj <- .controlled_trajectory(params, ctrl, initial_state, n_years)
  n <- nrow(traj)
  A_end <- traj$A[n]; F_end <- traj$F[n]; K_end <- traj$K[n]; D_end <- traj$D[n]

  ctrl_params <- params
  ctrl_params[["u_C"]] <- u_C
  ctrl_params[["u_P"]] <- u_P
  ctrl_params[["B_index"]] <- params[["B_index"]] * (1 + params[["rho"]] * u_B)

  rho_star <- tryCatch({
    jac <- jacobian_numerical(ctrl_params, c(A_end, F_end, K_end, D_end))
    stab <- classify_stability(jac)
    stab$rho_star
  }, error = function(e) NA_real_)

  feas <- feasibility_check(D_end, K_end, rho_star, F_end, params, K_trajectory = traj$K)

  list(scenario = "Custom", optimal_controls = ctrl, cost = cost,
       final_equilibrium = c(A = A_end, F = F_end, K = K_end, D = D_end),
       D_star = D_end, K_star = K_end, rho_star = rho_star,
       feasible = feas$feasible, violations = feas$violations)
}

#' Compute a Pareto frontier by sweeping the control budget.
#'
#' Scales all three controls proportionally from zero to their maximum values
#' and evaluates cost and terminal state at each level.
#'
#' @param params Named list of parameters (from \code{\link{default_params}}).
#' @param initial_state Named numeric vector \code{c(A=, F=, K=, D=)}.
#' @param n_points Integer number of budget fractions to evaluate (default 50).
#' @param n_years Integer simulation horizon (default 50).
#' @return A \code{data.frame} with columns \code{fraction}, \code{cost},
#'   \code{D_star}, and \code{K_star}.
#' @export
pareto_frontier <- function(params, initial_state, n_points = 50, n_years = 50) {
  fracs <- seq(0, 1, length.out = n_points)
  results <- data.frame(fraction = fracs, cost = NA_real_, D_star = NA_real_, K_star = NA_real_)
  for (i in seq_along(fracs)) {
    f <- fracs[i]
    ctrl <- c(u_P = f * params[["u_P_max"]], u_C = f * params[["u_C_max"]], u_B = f * params[["u_B_max"]])
    results$cost[i] <- .objective_functional(params, ctrl, initial_state, n_years)
    traj <- .controlled_trajectory(params, ctrl, initial_state, n_years)
    n <- nrow(traj)
    results$D_star[i] <- traj$D[n]
    results$K_star[i] <- traj$K[n]
  }
  results
}

#' Per-year cost breakdown for a given control combination.
#'
#' Simulates the controlled system year by year and returns a
#' \code{data.frame} with running cost, terminal cost, and control cost
#' components for each year.
#'
#' @param params Named list of parameters (from \code{\link{default_params}}).
#' @param controls Named numeric vector \code{c(u_P=, u_C=, u_B=)}.
#' @param initial_state Named numeric vector \code{c(A=, F=, K=, D=)}.
#' @param n_years Integer simulation horizon.
#' @return A \code{data.frame} with columns \code{year}, \code{u_P},
#'   \code{u_C}, \code{u_B}, \code{running_cost}, \code{terminal_cost},
#'   \code{control_cost}, and \code{total_cost}.
#' @export
temporal_allocation <- function(params, controls, initial_state, n_years) {
  # controls is a named vector c(u_P=..., u_C=..., u_B=...)
  p <- params
  p[["u_C"]] <- controls[["u_C"]]
  p[["u_P"]] <- controls[["u_P"]]
  p[["B_index"]] <- params[["B_index"]] * (1 + params[["rho"]] * controls[["u_B"]])

  W <- .get_cost_weights(params)

  A_t <- initial_state[["A"]]; F_t <- initial_state[["F"]]
  K_t <- initial_state[["K"]]; D_t <- initial_state[["D"]]

  years <- seq_len(n_years)
  running <- numeric(n_years)
  terminal <- numeric(n_years)
  control_cost <- numeric(n_years)

  for (yr in years) {
    S0_bh <- p[["R_B"]] * A_t / (1 + A_t / K_t)
    result <- tryCatch(integrate_season(p, S0 = S0_bh, I0 = 0, F0 = F_t, D0 = 0), error = function(e) NULL)
    if (is.null(result)) { running[yr] <- NA; terminal[yr] <- NA; control_cost[yr] <- NA; next }

    traj_s <- result$trajectory
    S_vals <- pmax(traj_s$S, 0); D_vals <- traj_s$D; t_vals <- traj_s$time
    integrand <- W$W_D * D_vals + W$W_S * S_vals
    n_pts <- length(t_vals)
    if (n_pts > 1) {
      dt <- diff(t_vals)
      running[yr] <- sum(dt * (integrand[-n_pts] + integrand[-1]) / 2)
    } else { running[yr] <- 0 }
    terminal[yr] <- W$W_T * D_vals[n_pts]
    control_cost[yr] <- W$C_P * controls[["u_P"]] * max(t_vals) + W$C_C * controls[["u_C"]] * max(t_vals) + W$C_B * controls[["u_B"]]

    end <- result$end
    A_t <- p[["sigma_A"]] * end$S_T
    F_t <- p[["sigma_F"]] * end$F_T
    K_t <- p[["K_0"]] * exp(-p[["phi"]] * end$D_T)
    D_t <- end$D_T
  }

  data.frame(year = years, u_P = controls[["u_P"]], u_C = controls[["u_C"]], u_B = controls[["u_B"]],
             running_cost = running, terminal_cost = terminal, control_cost = control_cost,
             total_cost = running + terminal + control_cost)
}
