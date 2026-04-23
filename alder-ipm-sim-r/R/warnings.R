#' @title Early Warning Signal Detection for Regime Shifts
#' @description Compute rolling-window early warning signals (EWS) for detecting
#'   critical slowing down in ecological time series from the Alnus-beetle-
#'   parasitoid-bird ecoepidemic system.

#' Remove a slow trend from a time series.
#'
#' Detrending is essential before computing rolling EWS because a deterministic
#' trend would inflate variance and autocorrelation estimates even in the absence
#' of critical slowing down.
#'
#' @param ts Numeric vector, the raw 1-D time series.
#' @param method Character: \code{"gaussian"} (default), \code{"linear"}, or
#'   \code{"loess"}.
#' @param bandwidth Numeric kernel bandwidth for Gaussian smoothing. If
#'   \code{NULL}, defaults to \code{length(ts) / 8}.
#' @return Numeric vector of residuals (same length as \code{ts}).
#' @examples
#' residuals <- detrend_ts(sin(1:50) + rnorm(50, sd = 0.1), method = "gaussian")
#' @export
detrend_ts <- function(ts, method = "gaussian", bandwidth = NULL) {
  ts <- as.numeric(ts)
  n <- length(ts)
  if (n < 3) stop("Time series must have at least 3 observations")

  if (is.null(bandwidth)) bandwidth <- max(n %/% 8, 1)

  if (method == "gaussian") {
    x_grid <- seq_len(n)
    trend <- stats::ksmooth(x_grid, ts, kernel = "normal",
                            bandwidth = bandwidth * 2, x.points = x_grid)$y
    return(ts - trend)
  }

  if (method == "linear") {
    t_idx <- seq_len(n)
    fit <- stats::lm(ts ~ t_idx)
    return(as.numeric(stats::residuals(fit)))
  }

  if (method == "loess") {
    t_idx <- seq_len(n)
    span <- min(max(bandwidth / n, 0.2), 1)
    fit <- stats::loess(ts ~ t_idx, span = span)
    return(as.numeric(stats::residuals(fit)))
  }

  stop(paste0("Unknown detrend method: '", method, "'. Use 'gaussian', 'linear', or 'loess'."))
}

#' Compute rolling variance of a time series.
#'
#' Rising variance is a hallmark of critical slowing down: as the dominant
#' eigenvalue rho* approaches 1, the system amplifies noise.
#'
#' @param ts Numeric vector, the raw time series.
#' @param window Integer window size. If \code{NULL}, defaults to 50\% of
#'   series length.
#' @return Numeric vector of rolling variance values (length =
#'   \code{length(ts) - window + 1}).
#' @examples
#' rv <- rolling_variance(rnorm(50), window = 10)
#' @export
rolling_variance <- function(ts, window = NULL) {
  ts <- as.numeric(ts)
  n <- length(ts)
  if (is.null(window)) window <- max(as.integer(n * 0.5), 3)
  if (window > n) window <- n

  vapply(seq_len(n - window + 1), function(i) {
    stats::var(ts[i:(i + window - 1)])
  }, numeric(1))
}

#' Compute rolling lag-k autocorrelation.
#'
#' Increasing AR(1) reflects the system's growing "memory" as recovery from
#' perturbations slows near a bifurcation.
#'
#' @param ts Numeric vector, the raw time series.
#' @param window Integer window size. If \code{NULL}, defaults to 50\% of
#'   series length.
#' @param lag Integer autocorrelation lag (default 1).
#' @return Numeric vector of rolling autocorrelation values.
#' @examples
#' rac <- rolling_autocorrelation(rnorm(50), window = 10, lag = 1)
#' @export
rolling_autocorrelation <- function(ts, window = NULL, lag = 1) {
  ts <- as.numeric(ts)
  n <- length(ts)
  if (is.null(window)) window <- max(as.integer(n * 0.5), 3)
  if (window > n) window <- n

  vapply(seq_len(n - window + 1), function(i) {
    segment <- ts[i:(i + window - 1)]
    if (stats::sd(segment) < 1e-15) return(0)
    x <- segment[1:(window - lag)]
    y <- segment[(1 + lag):window]
    if (length(x) < 3) return(0)
    corr <- stats::cor(x, y)
    if (is.na(corr) || !is.finite(corr)) 0 else corr
  }, numeric(1))
}

#' Compute rolling skewness.
#'
#' Increased skewness can indicate that the state-variable distribution is
#' becoming asymmetric, a sign of flickering between basins of attraction.
#'
#' @param ts Numeric vector, the raw time series.
#' @param window Integer window size. If \code{NULL}, defaults to 50\% of
#'   series length.
#' @return Numeric vector of rolling skewness values.
#' @examples
#' rs <- rolling_skewness(rnorm(50), window = 10)
#' @export
rolling_skewness <- function(ts, window = NULL) {
  ts <- as.numeric(ts)
  n <- length(ts)
  if (is.null(window)) window <- max(as.integer(n * 0.5), 3)
  if (window > n) window <- n

  vapply(seq_len(n - window + 1), function(i) {
    segment <- ts[i:(i + window - 1)]
    m <- mean(segment)
    s <- stats::sd(segment)
    if (s < 1e-15) return(0)
    w <- length(segment)
    # Unbiased sample skewness
    (w / ((w - 1) * (w - 2))) * sum(((segment - m) / s)^3)
  }, numeric(1))
}

#' Compute all early warning signals.
#'
#' Detrends the time series and computes rolling variance, autocorrelation, and
#' skewness in a single pass.
#'
#' @param ts Numeric vector, the raw time series (e.g. annual beetle density).
#' @param window Integer window size for rolling statistics. If \code{NULL},
#'   defaults to 50\% of series length.
#' @param detrend Character detrending method (default \code{"gaussian"}).
#' @return A data.frame with columns: \code{time} (integer index),
#'   \code{variance}, \code{autocorrelation}, \code{skewness}.
#' @examples
#' ews <- compute_ews(rnorm(50))
#' @export
compute_ews <- function(ts, window = NULL, detrend = "gaussian") {
  ts <- as.numeric(ts)
  residuals <- detrend_ts(ts, method = detrend)
  n <- length(residuals)
  if (is.null(window)) window <- max(as.integer(n * 0.5), 3)
  if (window > n) window <- n

  var_vals <- rolling_variance(residuals, window)
  ac_vals  <- rolling_autocorrelation(residuals, window, lag = 1)
  sk_vals  <- rolling_skewness(residuals, window)

  m <- length(var_vals)
  data.frame(
    time = seq_len(m),
    variance = var_vals,
    autocorrelation = ac_vals,
    skewness = sk_vals
  )
}

#' Kendall tau trend test for an EWS indicator.
#'
#' A significantly positive Kendall tau for variance or autocorrelation is the
#' canonical statistical test for critical slowing down.
#'
#' @param indicator Numeric vector of a rolling EWS indicator.
#' @return A list with components \code{tau} (numeric) and \code{p_value}
#'   (numeric).
#' @examples
#' result <- kendall_trend(cumsum(rnorm(30)))
#' @export
kendall_trend <- function(indicator) {
  indicator <- as.numeric(indicator)
  mask <- is.finite(indicator)
  indicator <- indicator[mask]
  if (length(indicator) < 3) return(list(tau = 0, p_value = 1))

  time_index <- seq_along(indicator)
  ct <- stats::cor.test(time_index, indicator, method = "kendall")
  list(tau = as.numeric(ct$estimate), p_value = as.numeric(ct$p.value))
}

#' Full early warning signal detection pipeline.
#'
#' Detrends the time series, computes all rolling-window EWS indicators, tests
#' each for an increasing trend via Kendall's tau, and assigns a traffic-light
#' alert level based on joint significance.
#'
#' @param ts Numeric vector, 1-D time series of a state variable (typically
#'   beetle density A_t).
#' @param window Integer window size. If \code{NULL}, defaults to 50\% of
#'   series length.
#' @param detrend Character detrending method (default \code{"gaussian"}).
#' @param var_threshold Numeric minimum Kendall tau to flag variance (default 0.3).
#' @param ac_threshold Numeric minimum Kendall tau to flag autocorrelation
#'   (default 0.3).
#' @return A list with components: \code{indicators} (data.frame from
#'   \code{\link{compute_ews}}), \code{kendall_results} (named list of
#'   tau/p_value lists), \code{alert_level} (\code{"green"}, \code{"yellow"},
#'   or \code{"red"}), and \code{interpretation} (character string in plain
#'   English).
#' @examples
#' # Simulate a time series and check for warnings
#' ts_data <- cumsum(rnorm(50, sd = 0.1)) + seq(0, 2, length.out = 50)
#' result <- detect_warnings(ts_data, window = 15)
#' cat(result$alert_level, "\n")
#' @export
detect_warnings <- function(ts, window = NULL, detrend = "gaussian",
                            var_threshold = 0.3, ac_threshold = 0.3) {
  indicators <- compute_ews(ts, window = window, detrend = detrend)

  kendall_results <- list(
    variance        = kendall_trend(indicators$variance),
    autocorrelation = kendall_trend(indicators$autocorrelation),
    skewness        = kendall_trend(indicators$skewness)
  )

  var_tau <- kendall_results$variance$tau
  var_p   <- kendall_results$variance$p_value
  ac_tau  <- kendall_results$autocorrelation$tau
  ac_p    <- kendall_results$autocorrelation$p_value

  var_sig <- var_p < 0.05 && var_tau > var_threshold
  ac_sig  <- ac_p < 0.05 && ac_tau > ac_threshold

  if (var_sig && ac_sig) {
    alert_level <- "red"
    interpretation <- paste(
      "RED ALERT: Both variance and autocorrelation of beetle larval density",
      "are increasing, indicating critical slowing down. The system may be",
      "approaching a regime shift from coexistence to parasitoid-free state.",
      "Recommended action: evaluate integrated control Strategy C (parasitoid",
      "augmentation + direct larval removal + bird habitat enhancement)."
    )
  } else if (var_sig || ac_sig) {
    alert_level <- "yellow"
    which_sig <- if (var_sig) "variance" else "autocorrelation"
    kt <- kendall_results[[which_sig]]
    interpretation <- paste0(
      "YELLOW ALERT: ", tools::toTitleCase(which_sig),
      " of beetle larval density shows a significant increasing trend (tau=",
      sprintf("%.3f", kt$tau), ", p=", sprintf("%.4f", kt$p_value),
      "). This is a potential early indicator of critical slowing down.",
      " Recommended action: increase monitoring frequency and prepare",
      " contingency plans for parasitoid augmentation."
    )
  } else {
    alert_level <- "green"
    interpretation <- paste(
      "GREEN: No significant increasing trends detected in variance or",
      "autocorrelation of beetle larval density. The system appears to be",
      "in a stable regime. Continue routine monitoring."
    )
  }

  list(
    indicators = indicators,
    kendall_results = kendall_results,
    alert_level = alert_level,
    interpretation = interpretation
  )
}


# ---------------------------------------------------------------------------
# LHS-PRCC Sensitivity Analysis
# ---------------------------------------------------------------------------

#' Default parameter names for LHS-PRCC analysis.
#' @return Character vector of the 9 phenological parameter names.
#' @export
lhs_param_names <- function() {
  c("T", "sigma_A", "sigma_F", "delta", "mu_S",
    "B_index", "phi", "beta", "R_B")
}

#' Default parameter ranges for LHS-PRCC analysis.
#' @return Named list of (min, max) pairs from the parameter registry.
#' @export
lhs_param_ranges <- function() {
  reg <- param_registry()
  pnames <- lhs_param_names()
  ranges <- list()
  for (pn in pnames) {
    meta <- reg[[pn]]
    ranges[[pn]] <- c(meta$min_val, meta$max_val)
  }
  ranges
}

#' Latin Hypercube Sampling for model parameters.
#'
#' Generates a space-filling design across the given parameters using
#' a simple LHS algorithm (random permutation per dimension).
#'
#' @param n_samples Integer number of samples (default 500).
#' @param param_names Character vector of parameter names.
#' @param param_ranges Named list of c(min, max) per parameter.
#' @param seed Integer random seed (optional).
#' @return A data.frame with columns named after the parameters.
#' @export
latin_hypercube_sample <- function(n_samples = 500,
                                   param_names = lhs_param_names(),
                                   param_ranges = lhs_param_ranges(),
                                   seed = NULL) {
  if (!is.null(seed)) set.seed(seed)

  d <- length(param_names)
  # Simple LHS: for each dimension, create a random permutation of
  # intervals and sample uniformly within each interval
  unit_samples <- matrix(0, nrow = n_samples, ncol = d)
  for (j in seq_len(d)) {
    perm <- sample.int(n_samples)
    unit_samples[, j] <- (perm - stats::runif(n_samples)) / n_samples
  }

  # Scale to parameter ranges
  result <- matrix(0, nrow = n_samples, ncol = d)
  for (j in seq_len(d)) {
    rng <- param_ranges[[param_names[j]]]
    result[, j] <- rng[1] + (rng[2] - rng[1]) * unit_samples[, j]
  }

  df <- as.data.frame(result)
  names(df) <- param_names
  df
}

#' Compute Partial Rank Correlation Coefficients (PRCC).
#'
#' Rank-transforms all variables, then for each input parameter computes
#' the partial correlation with the output by regressing out the effects
#' of all other parameters.
#'
#' @param samples Data.frame or matrix of input parameter values (n x d).
#' @param output Numeric vector of response values (length n).
#' @return A data.frame with columns: \code{parameter}, \code{prcc}, \code{p_value}.
#' @export
compute_prcc <- function(samples, output) {
  samples <- as.matrix(samples)
  n <- nrow(samples)
  d <- ncol(samples)
  pnames <- colnames(samples)
  if (is.null(pnames)) pnames <- paste0("X", seq_len(d))

  # Rank-transform
  ranked_X <- apply(samples, 2, rank)
  ranked_Y <- rank(output)

  prcc_vals <- numeric(d)
  p_vals <- numeric(d)

  for (j in seq_len(d)) {
    others <- setdiff(seq_len(d), j)
    if (length(others) == 0) {
      ct <- stats::cor.test(ranked_X[, j], ranked_Y, method = "pearson")
      prcc_vals[j] <- ct$estimate
      p_vals[j] <- ct$p.value
      next
    }

    Z <- ranked_X[, others, drop = FALSE]

    # Regress ranked X_j on Z -> residuals
    fit_x <- stats::lm(ranked_X[, j] ~ Z)
    e_x <- stats::residuals(fit_x)

    # Regress ranked Y on Z -> residuals
    fit_y <- stats::lm(ranked_Y ~ Z)
    e_y <- stats::residuals(fit_y)

    # PRCC = Pearson correlation of residuals
    if (stats::sd(e_x) < 1e-15 || stats::sd(e_y) < 1e-15) {
      prcc_vals[j] <- 0
      p_vals[j] <- 1
    } else {
      ct <- stats::cor.test(e_x, e_y, method = "pearson")
      prcc_vals[j] <- ct$estimate
      p_vals[j] <- ct$p.value
    }
  }

  data.frame(
    parameter = pnames,
    prcc = prcc_vals,
    p_value = p_vals,
    stringsAsFactors = FALSE
  )
}

#' Compute regime shift probability.
#'
#' @param eq_classes Character vector of equilibrium classifications.
#' @param reference Character reference class (default "coexistence").
#' @return Numeric fraction of samples that differ from the reference.
#' @export
regime_shift_probability <- function(eq_classes,
                                     reference = "coexistence") {
  if (length(eq_classes) == 0) return(0)
  sum(eq_classes != reference) / length(eq_classes)
}

#' Full LHS-PRCC sensitivity analysis.
#'
#' For each Latin Hypercube sample: simulate to quasi-steady state, compute
#' the dominant eigenvalue rho*, classify the equilibrium. Then compute
#' PRCC of each parameter with rho* and the regime shift probability.
#'
#' @param params Named list of baseline parameters.
#' @param n_samples Integer number of LHS samples (default 500).
#' @param param_names Character vector of parameters to sample.
#' @param param_ranges Named list of c(min, max) per parameter.
#' @param n_years Integer simulation years per sample (default 100).
#' @param seed Integer random seed.
#' @return A list with components: \code{prcc_table} (data.frame),
#'   \code{regime_shift_prob} (numeric), \code{samples} (data.frame),
#'   \code{rho_star} (numeric vector), \code{eq_classes} (character vector).
#' @export
lhs_prcc <- function(params = default_params(),
                     n_samples = 500,
                     param_names = lhs_param_names(),
                     param_ranges = lhs_param_ranges(),
                     n_years = 100,
                     seed = NULL) {
  samples <- latin_hypercube_sample(n_samples, param_names, param_ranges, seed)

  rho_star <- rep(NA_real_, n_samples)
  eq_classes <- rep("unknown", n_samples)

  for (i in seq_len(n_samples)) {
    tryCatch({
      p <- params
      for (j in seq_along(param_names)) {
        p[[param_names[j]]] <- samples[i, j]
      }

      K0 <- p[["K_0"]]
      sim <- simulate(p, A0 = K0 * 0.5, F0 = K0 * 0.1, K0 = K0, D0 = 0, n_years = n_years)
      n_t <- length(sim$A)
      A_end <- sim$A[n_t]
      F_end <- sim$F_[n_t]
      K_end <- sim$K[n_t]
      D_end <- sim$D[n_t]

      jac <- jacobian_numerical(p, c(A_end, F_end, K_end, D_end))
      eigvals <- eigen(jac, only.values = TRUE)$values
      rho_star[i] <- max(Mod(eigvals))

      # Classify
      tol <- 1e-6
      if (A_end < tol) {
        eq_classes[i] <- "trivial"
      } else if (F_end < tol && D_end < tol) {
        eq_classes[i] <- "canopy_only"
      } else if (F_end < tol) {
        eq_classes[i] <- "parasitoid_free"
      } else {
        eq_classes[i] <- "coexistence"
      }
    }, error = function(e) {
      rho_star[i] <<- NA_real_
      eq_classes[i] <<- "unknown"
    })
  }

  # Filter valid samples for PRCC
  valid <- is.finite(rho_star)
  if (sum(valid) < 10) {
    prcc_table <- data.frame(
      parameter = param_names,
      prcc = rep(0, length(param_names)),
      p_value = rep(1, length(param_names)),
      stringsAsFactors = FALSE
    )
  } else {
    prcc_table <- compute_prcc(samples[valid, , drop = FALSE], rho_star[valid])
  }

  shift_prob <- regime_shift_probability(eq_classes)

  list(
    prcc_table = prcc_table,
    regime_shift_prob = shift_prob,
    samples = samples,
    rho_star = rho_star,
    eq_classes = eq_classes
  )
}
