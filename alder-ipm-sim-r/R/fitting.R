#' @title Data Fitting and Parameter Estimation
#' @description Fit model parameters to time series data, predict trajectories,
#'   and classify forecast regimes for the Alnus-beetle-parasitoid-bird system.

# Null-coalescing operator (avoids rlang dependency)
`%||%` <- function(x, y) if (is.null(x)) y else x

#' Prepare and validate a data.frame for model fitting.
#'
#' Validates time ordering, checks for NaN values, and maps user-supplied column
#' names to the internal state variable convention (A, F, K, D).
#'
#' @param data A data.frame containing time series observations.
#' @param time_col Character string naming the time column (default \code{"year"}).
#' @param state_cols Named character vector mapping state variable names to column
#'   names, e.g. \code{c(A = "beetle_density", D = "defoliation")}. If \code{NULL},
#'   looks for columns named A, F, K, D directly.
#' @param timestep Character, either \code{"annual"} (default) or \code{"seasonal"}.
#' @return A list with components \code{times} (numeric vector), \code{obs}
#'   (named list of numeric vectors keyed by state name), \code{timestep}
#'   (character), and \code{n_obs} (integer).
#' @examples
#' df <- data.frame(year = 1:10, A = runif(10), D = runif(10, 0, 0.5))
#' prepared <- prepare_data(df)
#' @export
prepare_data <- function(data, time_col = "year", state_cols = NULL,
                         timestep = "annual") {
  if (!is.data.frame(data)) stop("data must be a data.frame")
  if (!timestep %in% c("annual", "seasonal"))
    stop("timestep must be 'annual' or 'seasonal'")
  if (!time_col %in% names(data))
    stop(paste0("Time column '", time_col, "' not found in data"))

  times <- as.numeric(data[[time_col]])
  if (any(is.na(times))) stop("NaN values found in time column")
  if (any(diff(times) <= 0)) stop("Time column must be strictly increasing")

  valid_states <- c("A", "F", "K", "D")

  if (is.null(state_cols)) {
    state_cols <- setNames(
      intersect(names(data), valid_states),
      intersect(names(data), valid_states)
    )
  }

  if (length(state_cols) == 0)
    stop("No observable state columns found. Provide state_cols mapping.")

  obs <- list()
  for (state_name in names(state_cols)) {
    col_name <- state_cols[[state_name]]
    if (!state_name %in% valid_states)
      stop(paste0("Unknown state variable '", state_name,
                  "'. Valid: ", paste(valid_states, collapse = ", ")))
    if (!col_name %in% names(data))
      stop(paste0("Column '", col_name, "' not found in data"))
    arr <- as.numeric(data[[col_name]])
    if (any(is.na(arr)))
      stop(paste0("NaN values found in column '", col_name, "'"))
    obs[[state_name]] <- arr
  }

  # Zero beetle count handling: add epsilon to avoid log(0) issues

  if (!is.null(obs[["A"]]) && any(obs[["A"]] <= 0)) {
    epsilon <- 1e-6
    obs[["A"]] <- pmax(obs[["A"]], epsilon)
    warning("State 'A' (beetle density) contained values <= 0; ",
            "replaced with epsilon = ", epsilon)
  }

  # Short series warning
  n_obs <- length(times)
  if (n_obs < 10) {
    warning("Short time series (n_obs = ", n_obs,
            "); parameter estimates may be unreliable")
  }

  # Gap detection in time series
  dt <- diff(times)
  median_dt <- stats::median(dt)
  gap_idx <- which(dt > 2 * median_dt)
  if (length(gap_idx) > 0) {
    warning("Detected ", length(gap_idx), " gap(s) in the time series ",
            "(intervals > 2x median spacing). Indices: ",
            paste(gap_idx, collapse = ", "))
  }

  list(times = times, obs = obs, timestep = timestep, n_obs = n_obs)
}

#' Fit model parameters to time series data.
#'
#' Estimates parameters by minimising the sum of squared residuals between
#' simulated and observed trajectories. Supports nonlinear least-squares
#' (\code{nls}), bounded L-BFGS-B optimisation (\code{optim}), and global
#' search via differential evolution (\code{de}).
#'
#' @param data Prepared data list (output of \code{\link{prepare_data}}).
#' @param fit_params Character vector of parameter names to estimate. If
#'   \code{NULL}, a default identifiable subset is used.
#' @param params Named list of parameters. If \code{NULL}, uses
#'   \code{\link{default_params}()}.
#' @param method Character: \code{"nls"} (default), \code{"optim"}, or \code{"de"}.
#' @param bounds Logical; if \code{TRUE} (default), enforce parameter bounds from
#'   the registry.
#' @return A list with components: \code{fitted_params} (named numeric vector),
#'   \code{residuals} (numeric vector), \code{r_squared} (numeric),
#'   \code{AIC} (numeric), \code{BIC} (numeric), \code{conf_intervals} (named
#'   list of length-2 vectors), \code{convergence} (list with optimizer details).
#' @examples
#' \dontrun{
#' params <- default_params()
#' sim <- simulate(params, A0 = 0.8, F0 = 0.1, K0 = 1.712, D0 = 0, n_years = 20)
#' prepared <- prepare_data(sim, time_col = "year")
#' result <- fit_model(prepared, fit_params = c("beta", "phi"))
#' }
#' @export
fit_model <- function(data, fit_params = NULL, params = NULL, method = "nls",
                      bounds = TRUE) {
  if (!method %in% c("nls", "optim", "de"))
    stop("method must be 'nls', 'optim', or 'de'")

  if (is.null(params)) params <- default_params()
  reg <- param_registry()

  if (is.null(fit_params))
    fit_params <- c("beta", "mu_S", "delta", "R_B", "phi", "kappa")

  x0 <- vapply(fit_params, function(n) params[[n]], numeric(1))

  if (bounds) {
    lb <- vapply(fit_params, function(n) reg[[n]]$min, numeric(1))
    ub <- vapply(fit_params, function(n) reg[[n]]$max, numeric(1))
  } else {
    lb <- rep(-Inf, length(fit_params))
    ub <- rep(Inf, length(fit_params))
  }

  # Residual function: returns residual vector
  resid_fn <- function(x) {
    p <- params
    for (i in seq_along(fit_params)) p[[fit_params[i]]] <- x[i]
    .compute_residuals(p, data)
  }

  # Sum-of-squares objective
  obj_fn <- function(x) sum(resid_fn(x)^2)

  if (method == "nls") {
    result <- tryCatch({
      opt <- stats::optim(
        par = x0, fn = obj_fn, method = "L-BFGS-B",
        lower = lb, upper = ub,
        control = list(maxit = 2000, factr = 1e7)
      )
      list(par = opt$par, value = opt$value, convergence = opt$convergence,
           message = opt$message %||% "")
    }, error = function(e) {
      list(par = x0, value = obj_fn(x0), convergence = 99,
           message = conditionMessage(e))
    })
  } else if (method == "optim") {
    opt <- stats::optim(
      par = x0, fn = obj_fn, method = "L-BFGS-B",
      lower = lb, upper = ub,
      control = list(maxit = 5000, factr = 1e7)
    )
    result <- list(par = opt$par, value = opt$value,
                   convergence = opt$convergence, message = opt$message %||% "")
  } else {
    # Differential evolution via DEoptim if available, else fall back to optim
    if (requireNamespace("DEoptim", quietly = TRUE)) {
      de_res <- DEoptim::DEoptim(
        fn = obj_fn, lower = lb, upper = ub,
        control = DEoptim::DEoptim.control(
          itermax = 300, trace = FALSE, seed = 42
        )
      )
      result <- list(par = de_res$optim$bestmem, value = de_res$optim$bestval,
                     convergence = 0, message = "DEoptim converged")
    } else {
      warning("DEoptim not available; falling back to L-BFGS-B")
      opt <- stats::optim(
        par = x0, fn = obj_fn, method = "L-BFGS-B",
        lower = lb, upper = ub,
        control = list(maxit = 5000)
      )
      result <- list(par = opt$par, value = opt$value,
                     convergence = opt$convergence, message = opt$message %||% "")
    }
  }

  fitted <- setNames(as.numeric(result$par), fit_params)
  residuals <- resid_fn(result$par)
  n <- length(residuals)
  k <- length(fit_params)

  ss_res <- sum(residuals^2)
  ss_tot <- sum((residuals - mean(residuals))^2) + ss_res
  r_squared <- 1 - ss_res / max(ss_tot, 1e-30)

  sigma2 <- ss_res / max(n - k, 1)
  log_lik <- -0.5 * n * (log(2 * pi * sigma2) + 1)
  aic <- -2 * log_lik + 2 * k
  bic <- -2 * log_lik + k * log(max(n, 1))

  # Confidence intervals from numerical Jacobian
  ci <- .compute_confidence_intervals(resid_fn, result$par, fit_params, sigma2)

  # Compute numerical gradient norm at solution
  gradient_norm <- tryCatch({
    grad <- vapply(seq_along(result$par), function(j) {
      h <- 1e-7 * max(abs(result$par[j]), 1)
      dx <- rep(0, length(result$par))
      dx[j] <- h
      (obj_fn(result$par + dx) - obj_fn(result$par - dx)) / (2 * h)
    }, numeric(1))
    sqrt(sum(grad^2))
  }, error = function(e) NA_real_)

  list(
    fitted_params = fitted,
    residuals = residuals,
    r_squared = r_squared,
    AIC = aic,
    BIC = bic,
    conf_intervals = ci,
    convergence = list(
      optimizer = method,
      convergence_code = result$convergence,
      cost = result$value,
      message = result$message,
      gradient_norm = gradient_norm
    )
  )
}

#' Project forward from a fitted model.
#'
#' Simulates the system for \code{n_years_ahead} beyond the fitting period using
#' the fitted parameters. Uncertainty bands are computed via Monte Carlo sampling
#' from the parameter covariance.
#'
#' @param fit_result List returned by \code{\link{fit_model}}.
#' @param n_years_ahead Integer number of years to project forward.
#' @param initial_state Named numeric vector \code{c(A=, F=, K=, D=)}. If
#'   \code{NULL}, uses sensible defaults from the parameter registry.
#' @return A data.frame with columns: year, A, F, K, D, and uncertainty bands
#'   A_lo, A_hi, F_lo, F_hi, K_lo, K_hi, D_lo, D_hi (2.5th and 97.5th
#'   percentiles from Monte Carlo).
#' @examples
#' \dontrun{
#' fit <- fit_model(prepared, fit_params = c("beta", "phi"))
#' pred <- predict_trajectory(fit, n_years_ahead = 10)
#' }
#' @export
predict_trajectory <- function(fit_result, n_years_ahead, initial_state = NULL) {
  params <- default_params()
  for (n in names(fit_result$fitted_params))
    params[[n]] <- fit_result$fitted_params[[n]]

  if (is.null(initial_state)) {
    K0 <- params[["K_0"]]
    initial_state <- c(A = K0 * 0.5, F = 0.1, K = K0, D = 0)
  }

  sim <- simulate(params, A0 = initial_state[["A"]], F0 = initial_state[["F"]],
                  K0 = initial_state[["K"]], D0 = initial_state[["D"]],
                  n_years = n_years_ahead)

  # Monte Carlo for uncertainty bands
  ci <- fit_result$conf_intervals
  pnames <- names(fit_result$fitted_params)
  means <- fit_result$fitted_params
  sds <- vapply(pnames, function(n) {
    max((ci[[n]][2] - ci[[n]][1]) / (2 * 1.96), 1e-12)
  }, numeric(1))

  reg <- param_registry()
  n_mc <- 100
  mc_A <- matrix(NA, nrow = n_mc, ncol = n_years_ahead + 1)
  mc_F <- matrix(NA, nrow = n_mc, ncol = n_years_ahead + 1)
  mc_K <- matrix(NA, nrow = n_mc, ncol = n_years_ahead + 1)
  mc_D <- matrix(NA, nrow = n_mc, ncol = n_years_ahead + 1)

  set.seed(0)
  valid <- 0
  for (j in seq_len(n_mc)) {
    p_mc <- params
    for (i in seq_along(pnames)) {
      val <- stats::rnorm(1, mean = means[[pnames[i]]], sd = sds[i])
      val <- max(min(val, reg[[pnames[i]]]$max), reg[[pnames[i]]]$min)
      p_mc[[pnames[i]]] <- val
    }
    tryCatch({
      s_mc <- simulate(p_mc, A0 = initial_state[["A"]], F0 = initial_state[["F"]],
                        K0 = initial_state[["K"]], D0 = initial_state[["D"]],
                        n_years = n_years_ahead)
      valid <- valid + 1
      mc_A[valid, ] <- s_mc$A
      mc_F[valid, ] <- s_mc$F
      mc_K[valid, ] <- s_mc$K
      mc_D[valid, ] <- s_mc$D
    }, error = function(e) NULL)
  }

  if (valid > 0) {
    q_lo <- function(m) apply(m[1:valid, , drop = FALSE], 2, stats::quantile, 0.025)
    q_hi <- function(m) apply(m[1:valid, , drop = FALSE], 2, stats::quantile, 0.975)
    sim$A_lo <- q_lo(mc_A); sim$A_hi <- q_hi(mc_A)
    sim$F_lo <- q_lo(mc_F); sim$F_hi <- q_hi(mc_F)
    sim$K_lo <- q_lo(mc_K); sim$K_hi <- q_hi(mc_K)
    sim$D_lo <- q_lo(mc_D); sim$D_hi <- q_hi(mc_D)
  } else {
    sim$A_lo <- sim$A; sim$A_hi <- sim$A
    sim$F_lo <- sim$F; sim$F_hi <- sim$F
    sim$K_lo <- sim$K; sim$K_hi <- sim$K
    sim$D_lo <- sim$D; sim$D_hi <- sim$D
  }

  sim
}

#' Determine the predicted regime class from fitted parameters.
#'
#' Classifies the long-term equilibrium regime implied by the fitted parameter
#' values, computes R_P and rho*, and returns a plain-language interpretation.
#'
#' @param fit_result List returned by \code{\link{fit_model}}.
#' @return A list with components: \code{equilibrium_class} (character),
#'   \code{R_P} (numeric), \code{rho_star} (numeric), and
#'   \code{interpretation} (character string in plain English).
#' @examples
#' \dontrun{
#' fit <- fit_model(prepared, fit_params = c("beta", "phi"))
#' regime <- forecast_regime(fit)
#' cat(regime$interpretation)
#' }
#' @export
forecast_regime <- function(fit_result) {
  params <- default_params()
  for (n in names(fit_result$fitted_params))
    params[[n]] <- fit_result$fitted_params[[n]]

  # Simulate to quasi-steady state
  K0 <- params[["K_0"]]
  sim <- simulate(params, A0 = K0 * 0.5, F0 = 0.1, K0 = K0, D0 = 0,
                  n_years = 50)
  n <- nrow(sim)
  A_end <- sim$A[n]; F_end <- sim$F[n]; K_end <- sim$K[n]; D_end <- sim$D[n]

  tol <- 1e-6
  if (A_end < tol) {
    eq_class <- "trivial"
  } else if (F_end < tol && D_end < tol) {
    eq_class <- "canopy_only"
  } else if (F_end < tol) {
    eq_class <- "parasitoid_free"
  } else {
    eq_class <- "coexistence"
  }

  R_P <- compute_RP(params)

  # Stability at endpoint
  rho_star <- tryCatch({
    jac <- jacobian_numerical(params, c(A_end, F_end, K_end, D_end))
    stab <- classify_stability(jac)
    stab$rho_star
  }, error = function(e) NA_real_)

  interpretation <- .build_regime_interpretation(eq_class, R_P, rho_star)

  list(
    equilibrium_class = eq_class,
    R_P = R_P,
    rho_star = rho_star,
    interpretation = interpretation
  )
}


#' Bootstrap confidence intervals for fitted parameters.
#'
#' Resamples around the fitted optimum by perturbing starting points and
#' refitting with L-BFGS-B, then reports percentile-based confidence intervals.
#'
#' @param fit_result List from \code{\link{fit_model}}.
#' @param data Prepared data list from \code{\link{prepare_data}}.
#' @param n_bootstrap Integer, number of resamples (default 200).
#' @param seed Integer random seed.
#' @return List with \code{ci} (named list of \code{c(lo, hi)}),
#'   \code{n_successful} (integer count of successful refits).
#' @export
bootstrap_ci <- function(fit_result, data, n_bootstrap = 200, seed = 42) {
  set.seed(seed)

  fit_params <- names(fit_result$fitted_params)
  x0 <- as.numeric(fit_result$fitted_params)
  params <- default_params()
  for (n in fit_params) params[[n]] <- fit_result$fitted_params[[n]]

  reg <- param_registry()
  lb <- vapply(fit_params, function(n) reg[[n]]$min, numeric(1))
  ub <- vapply(fit_params, function(n) reg[[n]]$max, numeric(1))

  # Residual-based objective
  resid_fn <- function(x) {
    p <- params
    for (i in seq_along(fit_params)) p[[fit_params[i]]] <- x[i]
    .compute_residuals(p, data)
  }
  obj_fn <- function(x) sum(resid_fn(x)^2)

  # Scale for perturbation: use CI width or fallback
  ci_orig <- fit_result$conf_intervals
  sds <- vapply(fit_params, function(n) {
    max((ci_orig[[n]][2] - ci_orig[[n]][1]) / (2 * 1.96), abs(x0[match(n, fit_params)]) * 0.05, 1e-8)
  }, numeric(1))

  collected <- matrix(NA_real_, nrow = n_bootstrap, ncol = length(fit_params))
  n_successful <- 0L

  for (b in seq_len(n_bootstrap)) {
    x_start <- x0 + stats::rnorm(length(x0)) * sds
    x_start <- pmax(pmin(x_start, ub), lb)

    result <- tryCatch({
      opt <- stats::optim(
        par = x_start, fn = obj_fn, method = "L-BFGS-B",
        lower = lb, upper = ub,
        control = list(maxit = 2000, factr = 1e7)
      )
      if (opt$convergence == 0) opt$par else NULL
    }, error = function(e) NULL)

    if (!is.null(result)) {
      n_successful <- n_successful + 1L
      collected[n_successful, ] <- result
    }
  }

  ci <- list()
  if (n_successful >= 2) {
    mat <- collected[seq_len(n_successful), , drop = FALSE]
    for (i in seq_along(fit_params)) {
      ci[[fit_params[i]]] <- as.numeric(stats::quantile(mat[, i], c(0.025, 0.975)))
    }
  } else {
    for (i in seq_along(fit_params)) {
      ci[[fit_params[i]]] <- c(x0[i], x0[i])
    }
  }

  list(ci = ci, n_successful = n_successful)
}

#' Compute residual diagnostics: ACF, QQ data, Durbin-Watson.
#'
#' Extracts the residual vector from a fitted model and computes autocorrelation,
#' quantile-quantile coordinates, and the Durbin-Watson statistic to assess
#' residual normality and independence.
#'
#' @param fit_result List from \code{\link{fit_model}}.
#' @return List with components \code{acf_values} (numeric vector),
#'   \code{acf_lags} (numeric vector), \code{qq_theoretical} (numeric vector),
#'   \code{qq_observed} (numeric vector), \code{durbin_watson} (numeric scalar).
#' @export
residual_diagnostics <- function(fit_result) {
  r <- fit_result$residuals

  # ACF
  acf_obj <- stats::acf(r, plot = FALSE)
  acf_values <- as.numeric(acf_obj$acf)
  acf_lags <- as.numeric(acf_obj$lag)

  # QQ
  qq <- stats::qqnorm(r, plot.it = FALSE)
  qq_theoretical <- qq$x
  qq_observed <- qq$y

  # Durbin-Watson statistic
  dr <- diff(r)
  durbin_watson <- sum(dr^2) / sum(r^2)

  list(
    acf_values = acf_values,
    acf_lags = acf_lags,
    qq_theoretical = qq_theoretical,
    qq_observed = qq_observed,
    durbin_watson = durbin_watson
  )
}

#' Compute parameter correlation matrix from fit result.
#'
#' Uses the numerical Jacobian of the residual function at the fitted optimum
#' to approximate the parameter covariance matrix (via \eqn{(J^T J)^{-1}}),
#' then normalises to a correlation matrix.
#'
#' @param fit_result List from \code{\link{fit_model}}.
#' @param data Prepared data list from \code{\link{prepare_data}}. Required to
#'   recompute the numerical Jacobian.
#' @return A correlation matrix with row and column names matching the fitted
#'   parameter names, or \code{NULL} if the matrix is not computable (e.g.
#'   singular Jacobian).
#' @export
parameter_correlation <- function(fit_result, data) {
  x_opt <- as.numeric(fit_result$fitted_params)
  param_names <- names(fit_result$fitted_params)
  k <- length(x_opt)

  params <- default_params()
  for (n in param_names) params[[n]] <- fit_result$fitted_params[[n]]

  # Rebuild residual function
  resid_fn <- function(x) {
    p <- params
    for (i in seq_along(param_names)) p[[param_names[i]]] <- x[i]
    .compute_residuals(p, data)
  }

  tryCatch({
    # Numerical Jacobian (same approach as .compute_confidence_intervals)
    r0 <- resid_fn(x_opt)
    n_res <- length(r0)
    jac <- matrix(0, nrow = n_res, ncol = k)

    for (j in seq_len(k)) {
      h <- 1e-7 * max(abs(x_opt[j]), 1)
      dx <- rep(0, k)
      dx[j] <- h
      r_plus <- resid_fn(x_opt + dx)
      r_minus <- resid_fn(x_opt - dx)
      jac[, j] <- (r_plus - r_minus) / (2 * h)
    }

    # Covariance: sigma^2 * (J^T J)^{-1}
    ss_res <- sum(r0^2)
    sigma2 <- ss_res / max(n_res - k, 1)
    jtj <- crossprod(jac)
    cov_mat <- solve(jtj) * sigma2

    # Normalise to correlation
    d <- sqrt(pmax(diag(cov_mat), 0))
    cor_mat <- cov_mat / outer(d, d)
    # Clamp diagonal to exactly 1
    diag(cor_mat) <- 1
    rownames(cor_mat) <- param_names
    colnames(cor_mat) <- param_names
    cor_mat
  }, error = function(e) NULL)
}

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

#' @noRd
.compute_residuals <- function(params, data) {
  obs <- data$obs
  observed_states <- names(obs)

  ic <- .initial_conditions_from_data(data, params)

  if (data$timestep == "annual") {
    n <- data$n_obs
    sim <- tryCatch(
      simulate(params, A0 = ic[["A"]], F0 = ic[["F"]],
               K0 = ic[["K"]], D0 = ic[["D"]],
               n_years = n - 1),
      error = function(e) NULL
    )
    if (is.null(sim)) return(rep(1e6, n * length(observed_states)))

    residuals <- numeric(0)
    for (s in observed_states) {
      sim_arr <- sim[[s]][seq_len(n)]
      obs_arr <- obs[[s]]
      scale <- max(stats::sd(obs_arr), 1e-12)
      residuals <- c(residuals, (sim_arr - obs_arr) / scale)
    }
    return(residuals)
  } else {
    # Seasonal
    sim <- tryCatch(
      integrate_season(params, S0 = ic[["A"]], I0 = 0, F0 = ic[["F"]],
                       D0 = ic[["D"]], times = data$times),
      error = function(e) NULL
    )
    if (is.null(sim)) return(rep(1e6, data$n_obs * length(observed_states)))

    state_idx <- c(A = "S", F = "F", K = NA, D = "D")
    residuals <- numeric(0)
    for (s in observed_states) {
      col <- state_idx[[s]]
      if (is.na(col)) next
      sim_arr <- sim$trajectory[[col]]
      obs_arr <- obs[[s]]
      scale <- max(stats::sd(obs_arr), 1e-12)
      residuals <- c(residuals, (sim_arr - obs_arr) / scale)
    }
    if (length(residuals) == 0) return(0)
    return(residuals)
  }
}

#' @noRd
.initial_conditions_from_data <- function(data, params) {
  K0 <- params[["K_0"]]
  ic <- list(A = K0 * 0.5, F = 0.1, K = K0, D = 0)
  for (s in c("A", "F", "K", "D")) {
    if (!is.null(data$obs[[s]])) ic[[s]] <- data$obs[[s]][1]
  }
  ic
}

#' @noRd
.compute_confidence_intervals <- function(resid_fn, x_opt, param_names, sigma2) {
  k <- length(x_opt)
  r0 <- resid_fn(x_opt)
  n_res <- length(r0)
  jac <- matrix(0, nrow = n_res, ncol = k)

  for (j in seq_len(k)) {
    h <- 1e-7 * max(abs(x_opt[j]), 1)
    dx <- rep(0, k)
    dx[j] <- h
    r_plus <- resid_fn(x_opt + dx)
    r_minus <- resid_fn(x_opt - dx)
    jac[, j] <- (r_plus - r_minus) / (2 * h)
  }

  ci <- list()
  tryCatch({
    jtj <- crossprod(jac)
    cov_mat <- solve(jtj) * sigma2
    se <- sqrt(pmax(diag(cov_mat), 0))
    for (i in seq_along(param_names)) {
      ci[[param_names[i]]] <- c(x_opt[i] - 1.96 * se[i],
                                 x_opt[i] + 1.96 * se[i])
    }
  }, error = function(e) {
    for (i in seq_along(param_names)) {
      ci[[param_names[i]]] <<- c(x_opt[i], x_opt[i])
    }
  })

  ci
}

#' @noRd
.build_regime_interpretation <- function(eq_class, R_P, rho_star) {
  lines <- paste0("Based on fitted parameters, the system is in the ",
                  toupper(eq_class), " regime (R_P = ", sprintf("%.2f", R_P), ").")

  if (eq_class == "coexistence" && R_P > 1) {
    lines <- paste(lines,
      "The parasitoid can persist and provides biological control.")
    if (!is.na(rho_star)) {
      stab_word <- if (rho_star < 0.5) "strong"
                   else if (rho_star < 0.9) "moderate"
                   else "weak"
      lines <- paste(lines,
        sprintf("The dominant eigenvalue rho* = %.2f indicates %s stability.",
                rho_star, stab_word),
        "Monitor beetle fecundity (R_B) and larval mortality (mu_S)",
        "as early warning indicators.")
    }
  } else if (eq_class == "parasitoid_free") {
    lines <- paste(lines,
      "The parasitoid cannot persist (R_P < 1). Consider parasitoid",
      "augmentation or habitat management to boost natural enemies.")
  } else if (eq_class == "trivial") {
    lines <- paste(lines,
      "Both beetle and parasitoid populations collapse.",
      "Verify data quality and parameter calibration.")
  } else if (eq_class == "canopy_only") {
    lines <- paste(lines,
      "Beetle population persists without significant parasitism.",
      "The canopy may be at risk of chronic defoliation.")
  }

  lines
}
