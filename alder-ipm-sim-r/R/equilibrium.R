#' @title Fixed-Point Finding and Stability Analysis
#' @description Find equilibria of the annual map and classify their stability.
#' @importFrom stats runif

#' Find fixed points of the annual map from multiple starting points.
#'
#' Uses \code{rootSolve::multiroot} from randomised initial conditions to find
#' states x* satisfying G(x*) = x* where G is the annual map.
#'
#' @param params Named list of parameters.
#' @param n_starts Number of random starting points (default 20).
#' @param tol Tolerance for zero-checking and deduplication (default 1e-8).
#' @return A data.frame with columns: A_star, F_star, K_star, D_star, class,
#'   stable, rho_star, bifurcation.
#' @examples
#' params <- as.list(default_params())
#' params$u_C <- 0; params$u_P <- 0
#' fps <- find_fixed_points(params, n_starts = 5)
#' print(fps)
#' @export
find_fixed_points <- function(params, n_starts = 20, tol = 1e-8) {
  K0 <- params[["K_0"]]

  residual_fn <- function(x) {
    x <- pmax(x, 0)
    x[3] <- max(x[3], 1e-12)
    res <- annual_map(params, A_t = x[1], F_t = x[2], K_t = x[3], D_t = x[4])
    c(res$A_next - x[1], res$F_next - x[2], res$K_next - x[3], res$D_next - x[4])
  }

  # Latin hypercube-like random starts
  set.seed(42)
  ics <- matrix(nrow = n_starts + 4, ncol = 4)
  for (i in seq_len(n_starts)) {
    ics[i, ] <- c(
      stats::runif(1, 0, 2 * K0),
      stats::runif(1, 0, K0),
      stats::runif(1, 0.1 * K0, K0),
      stats::runif(1, 0, 5)
    )
  }
  # Special initial conditions
  ics[n_starts + 1, ] <- c(0, 0, K0, 0)
  ics[n_starts + 2, ] <- c(K0 * 0.5, 0, K0, 0)
  ics[n_starts + 3, ] <- c(K0, K0 * 0.3, K0, 1)
  ics[n_starts + 4, ] <- c(K0 * 0.1, K0 * 0.1, K0, 0.5)

  raw_fps <- list()

  for (i in seq_len(nrow(ics))) {
    tryCatch({
      sol <- rootSolve::multiroot(
        f = residual_fn,
        start = ics[i, ],
        maxiter = 500,
        rtol = 1e-10,
        atol = 1e-10
      )
      if (max(abs(sol$f.root)) > 1e-6) next
      fp <- pmax(sol$root, 0)
      if (any(is.nan(fp)) || any(is.infinite(fp))) next
      raw_fps[[length(raw_fps) + 1]] <- fp
    }, error = function(e) NULL)
  }

  # Deduplicate
  unique_fps <- list()
  for (fp in raw_fps) {
    is_dup <- FALSE
    for (ufp in unique_fps) {
      if (all(abs(fp - ufp) < tol * 100)) {
        is_dup <- TRUE
        break
      }
    }
    if (!is_dup) unique_fps[[length(unique_fps) + 1]] <- fp
  }

  if (length(unique_fps) == 0) {
    return(data.frame(
      A_star = numeric(0), F_star = numeric(0),
      K_star = numeric(0), D_star = numeric(0),
      class = character(0), stable = logical(0),
      rho_star = numeric(0), bifurcation = character(0),
      stringsAsFactors = FALSE
    ))
  }

  # Classify each fixed point
  results <- vector("list", length(unique_fps))
  for (i in seq_along(unique_fps)) {
    fp <- unique_fps[[i]]
    A <- fp[1]; F_ <- fp[2]; K <- fp[3]; D <- fp[4]

    # Classify equilibrium type
    if (A < tol) {
      eq_class <- "trivial"
    } else if (F_ < tol && D < tol) {
      eq_class <- "canopy_only"
    } else if (F_ < tol) {
      eq_class <- "parasitoid_free"
    } else {
      eq_class <- "coexistence"
    }

    tryCatch({
      jac <- jacobian_numerical(params, c(A, F_, K, D))
      stab <- classify_stability(jac)
      results[[i]] <- data.frame(
        A_star = A, F_star = F_, K_star = K, D_star = D,
        class = eq_class, stable = stab$stable,
        rho_star = stab$rho_star, bifurcation = stab$bifurcation_type,
        stringsAsFactors = FALSE
      )
    }, error = function(e) {
      results[[i]] <<- data.frame(
        A_star = A, F_star = F_, K_star = K, D_star = D,
        class = eq_class, stable = FALSE,
        rho_star = NA_real_, bifurcation = "unknown",
        stringsAsFactors = FALSE
      )
    })
  }

  do.call(rbind, results)
}

#' Numerical Jacobian of the annual map via central differences.
#'
#' @param params Named list of parameters.
#' @param state Numeric vector c(A, F, K, D).
#' @param eps Perturbation size (default 1e-6).
#' @return 4x4 numeric matrix (Jacobian).
#' @examples
#' params <- as.list(default_params())
#' params$u_C <- 0; params$u_P <- 0
#' jac <- jacobian_numerical(params, c(0.5, 0.05, 1.5, 0.1))
#' print(round(jac, 4))
#' @export
jacobian_numerical <- function(params, state, eps = 1e-6) {
  map_vec <- function(x) {
    x <- pmax(x, 0)
    x[3] <- max(x[3], 1e-12)
    res <- annual_map(params, A_t = x[1], F_t = x[2], K_t = x[3], D_t = x[4])
    c(res$A_next, res$F_next, res$K_next, res$D_next)
  }

  jac <- matrix(0, nrow = 4, ncol = 4)
  x0 <- as.numeric(state)

  for (j in 1:4) {
    h <- eps * max(abs(x0[j]), 1)
    x_plus <- x0; x_minus <- x0
    x_plus[j] <- x_plus[j] + h
    x_minus[j] <- x_minus[j] - h
    x_plus <- pmax(x_plus, 0); x_minus <- pmax(x_minus, 0)
    x_plus[3] <- max(x_plus[3], 1e-12); x_minus[3] <- max(x_minus[3], 1e-12)
    f_plus <- map_vec(x_plus)
    f_minus <- map_vec(x_minus)
    denom <- x_plus[j] - x_minus[j]
    if (abs(denom) < .Machine$double.eps) denom <- 2 * h
    jac[, j] <- (f_plus - f_minus) / denom
  }

  jac
}

#' Classify stability from the Jacobian eigenvalues.
#'
#' @param jac 4x4 numeric Jacobian matrix.
#' @return Named list with rho_star (spectral radius), stable (logical),
#'   bifurcation_type ("stable", "fold", "flip", or "neimark_sacker").
#' @examples
#' # Stable diagonal matrix
#' classify_stability(diag(c(0.5, 0.3, 0.8, 0.2)))
#' # Unstable
#' classify_stability(diag(c(1.5, 0.3, 0.8, 0.2)))
#' @export
classify_stability <- function(jac) {
  eigvals <- eigen(jac, only.values = TRUE)$values
  abs_eigvals <- Mod(eigvals)
  rho_star <- max(abs_eigvals)
  stable <- rho_star < 1

  if (stable) {
    bif_type <- "stable"
  } else {
    crossing <- which(abs_eigvals >= 1)
    crossing_eigs <- eigvals[crossing]
    has_complex <- any(abs(Im(crossing_eigs)) > 1e-8)
    if (has_complex) {
      bif_type <- "neimark_sacker"
    } else {
      real_crossing <- Re(crossing_eigs[abs(Im(crossing_eigs)) <= 1e-8])
      if (any(real_crossing < 0)) {
        bif_type <- "flip"
      } else {
        bif_type <- "fold"
      }
    }
  }

  list(rho_star = rho_star, stable = stable, bifurcation_type = bif_type)
}

#' Compute a 1-D bifurcation diagram by sweeping a parameter.
#'
#' For each value in \code{param_range}, finds all fixed points, classifies
#' equilibrium type and stability, and computes R_P.  Returns a list with
#' structured data for plotting (manuscript Figs. 2-3).
#'
#' @param params Named list of base parameters.
#' @param param_name Character string: name of parameter to sweep.
#' @param param_range Numeric vector of parameter values.
#' @return A list with components: \code{param_values}, \code{equilibria}
#'   (list of data.frames), \code{R_P} (numeric vector).
#' @export
bifurcation_diagram <- function(params, param_name, param_range) {
  original_val <- params[[param_name]]
  n <- length(param_range)
  equilibria <- vector("list", n)
  R_P <- rep(NA_real_, n)

  for (i in seq_len(n)) {
    params[[param_name]] <- param_range[i]
    tryCatch({
      equilibria[[i]] <- find_fixed_points(params, n_starts = 10)
    }, error = function(e) {
      equilibria[[i]] <<- data.frame(
        A_star = numeric(0), F_star = numeric(0),
        K_star = numeric(0), D_star = numeric(0),
        class = character(0), stable = logical(0),
        rho_star = numeric(0), bifurcation = character(0),
        stringsAsFactors = FALSE
      )
    })
    tryCatch({
      R_P[i] <- compute_RP(params)
    }, error = function(e) NULL)
  }

  params[[param_name]] <- original_val

  list(
    param_values = param_range,
    equilibria = equilibria,
    R_P = R_P
  )
}

#' Compute R_P over a 2-D parameter grid.
#'
#' Returns R_P values on a meshgrid so the R_P = 1 contour
#' (transcritical bifurcation boundary) can be plotted.
#'
#' @param params Named list of base parameters.
#' @param param1_name Character: first parameter name (x-axis).
#' @param param1_range Numeric vector.
#' @param param2_name Character: second parameter name (y-axis).
#' @param param2_range Numeric vector.
#' @return A list with \code{param1_values}, \code{param2_values},
#'   \code{R_P_grid} (matrix of dim length(param1_range) x length(param2_range)).
#' @export
rp_boundary <- function(params, param1_name, param1_range,
                         param2_name, param2_range) {
  orig_v1 <- params[[param1_name]]
  orig_v2 <- params[[param2_name]]

  n1 <- length(param1_range)
  n2 <- length(param2_range)
  R_P_grid <- matrix(NA_real_, nrow = n1, ncol = n2)

  for (i in seq_len(n1)) {
    params[[param1_name]] <- param1_range[i]
    for (j in seq_len(n2)) {
      params[[param2_name]] <- param2_range[j]
      tryCatch({
        R_P_grid[i, j] <- compute_RP(params)
      }, error = function(e) NULL)
    }
  }

  params[[param1_name]] <- orig_v1
  params[[param2_name]] <- orig_v2

  list(
    param1_values = param1_range,
    param2_values = param2_range,
    R_P_grid = R_P_grid
  )
}
