#' @title Core ODE Model for the Alnus-Beetle-Parasitoid-Bird Ecoepidemic System
#' @description Within-season ODE, annual discrete map, multi-year simulation, and R_P computation.
#' @importFrom deSolve ode

#' Within-season ODE right-hand side (compatible with deSolve::ode).
#'
#' State vector y = c(S, I, F, D) where S = susceptible larvae, I = parasitised
#' larvae, F = adult parasitoid flies, D = cumulative defoliation.
#'
#' @param tau Time within season (days).
#' @param y Named numeric vector c(S=, I=, F=, D=).
#' @param params Named list of parameters (must include u_C and u_P for control inputs).
#' @return List containing the derivative vector, as required by deSolve::ode.
#' @export
within_season_ode <- function(tau, y, params) {
  S <- max(y[["S"]], 0)
  I <- max(y[["I"]], 0)
  F_ <- max(y[["F"]], 0)
  D <- y[["D"]]

  B_t <- params[["B_index"]]
  u_C <- if (!is.null(params[["u_C"]])) params[["u_C"]] else 0
  u_P <- if (!is.null(params[["u_P"]])) params[["u_P"]] else 0

  # Holling Type II parasitism
  parasitism <- params[["beta"]] * S * F_ / (1 + params[["h"]] * S)

  # Bird predation (Holling II on total larvae)
  total_larvae <- S + I
  bird_pred <- params[["c_B"]] * B_t * total_larvae / (1 + params[["a_B"]] * total_larvae)

  dS <- -parasitism - bird_pred - (params[["mu_S"]] + u_C) * S
  dI <-  parasitism - bird_pred - (params[["mu_I"]] + params[["delta"]] + u_C) * I
  dF <-  params[["eta"]] * params[["delta"]] * I - params[["mu_F"]] * F_ + u_P
  dD <-  params[["kappa"]] * total_larvae

  list(c(S = dS, I = dI, F = dF, D = dD))
}

#' Integrate the within-season ODE.
#'
#' @param params Named list of parameters.
#' @param S0 Initial susceptible larvae density.
#' @param I0 Initial parasitised larvae density.
#' @param F0 Initial parasitoid fly density.
#' @param D0 Initial cumulative defoliation.
#' @param times Numeric vector of output times. Defaults to seq(0, T, length.out=200).
#' @return A list with components \code{trajectory} (data.frame) and \code{end}
#'   (named list with S_T, I_T, F_T, D_T).
#' @export
integrate_season <- function(params, S0, I0, F0, D0, times = NULL) {
  if (is.null(times)) {
    times <- seq(0, params[["T"]], length.out = 200)
  }

  y0 <- c(S = S0, I = I0, F = F0, D = D0)

  sol <- deSolve::ode(
    y = y0,
    times = times,
    func = within_season_ode,
    parms = params,
    method = "lsoda",
    rtol = 1e-8,
    atol = 1e-10
  )

  traj <- as.data.frame(sol)
  n <- nrow(traj)

  end <- list(
    S_T = max(traj$S[n], 0),
    I_T = max(traj$I[n], 0),
    F_T = max(traj$F[n], 0),
    D_T = traj$D[n]
  )

  list(trajectory = traj, end = end)
}

#' Compute one step of the annual discrete map.
#'
#' Integrates the within-season ODE then applies Beverton-Holt recruitment,
#' overwinter survival, and carrying capacity update.
#'
#' @param params Named list of parameters.
#' @param A_t Adult beetle density entering the season.
#' @param F_t Parasitoid fly density entering the season.
#' @param K_t Current carrying capacity.
#' @param D_t Defoliation from previous year.
#' @return Named list with A_next, F_next, K_next, D_next, and within_season (trajectory).
#' @export
annual_map <- function(params, A_t, F_t, K_t, D_t) {
  # Beverton-Holt recruitment at season start (Eq. 5)
  S0 <- params[["R_B"]] * A_t / (1 + A_t / K_t)

  result <- integrate_season(params, S0 = S0, I0 = 0, F0 = F_t, D0 = 0)
  end <- result$end

  S_T <- end$S_T
  F_T <- end$F_T
  D_T <- end$D_T

  # Simple overwinter survival (Eq. 6)
  A_next <- params[["sigma_A"]] * S_T
  F_next <- params[["sigma_F"]] * F_T
  K_next <- params[["K_0"]] * exp(-params[["phi"]] * D_T)
  D_next <- D_T

  list(
    A_next = A_next,
    F_next = F_next,
    K_next = K_next,
    D_next = D_next,
    within_season = result$trajectory
  )
}

#' Run multi-year simulation of the annual map.
#'
#' @param params Named list of parameters.
#' @param A0 Initial adult beetle density.
#' @param F0 Initial parasitoid fly density.
#' @param K0 Initial carrying capacity.
#' @param D0 Initial defoliation.
#' @param n_years Number of annual cycles.
#' @return A data.frame with columns: year, A, F, K, D.
#' @export
simulate <- function(params, A0, F0, K0, D0, n_years) {
  A <- numeric(n_years + 1)
  F_ <- numeric(n_years + 1)
  K <- numeric(n_years + 1)
  D <- numeric(n_years + 1)

  A[1] <- A0; F_[1] <- F0; K[1] <- K0; D[1] <- D0

  for (t in seq_len(n_years)) {
    res <- annual_map(params, A[t], F_[t], K[t], D[t])
    A[t + 1]  <- res$A_next
    F_[t + 1] <- res$F_next
    K[t + 1]  <- res$K_next
    D[t + 1]  <- res$D_next
  }

  data.frame(
    year = 0:n_years,
    A = A,
    F = F_,
    K = K,
    D = D
  )
}

#' Compute parasitoid invasion reproduction number R_P.
#'
#' @param params Named list of parameters.
#' @param S_bar Equilibrium susceptible beetle density. If NULL, computed from
#'   parasitoid-free equilibrium by iterating the annual map with F=0.
#' @return Numeric scalar R_P.
#' @export
compute_RP <- function(params, S_bar = NULL) {
  if (is.null(S_bar)) {
    # Iterate parasitoid-free system to steady state
    p <- params
    p[["u_P"]] <- 0
    A_t <- p[["K_0"]] * 0.5
    K_t <- p[["K_0"]]
    end <- NULL

    for (i in seq_len(200)) {
      # Beverton-Holt at season start
      S0_bh <- p[["R_B"]] * A_t / (1 + A_t / K_t)
      result <- integrate_season(p, S0 = S0_bh, I0 = 0, F0 = 0, D0 = 0)
      end <- result$end
      S_T <- end$S_T
      D_T <- end$D_T
      A_next <- p[["sigma_A"]] * S_T
      K_next <- p[["K_0"]] * exp(-p[["phi"]] * D_T)
      if (abs(A_next - A_t) < 1e-10 && abs(K_next - K_t) < 1e-10) break
      A_t <- A_next
      K_t <- K_next
    }
    S_bar <- end$S_T
  }

  R_P <- (params[["beta"]] * params[["eta"]] * params[["delta"]] * params[["sigma_F"]]) /
    ((1 + params[["h"]] * S_bar) * params[["mu_F"]] * (params[["mu_I"]] + params[["delta"]]))

  R_P
}

#' Extract daily-resolution within-season trajectory for a specific year.
#'
#' Re-runs the within-season ODE for the specified year using the annual
#' state at that year from a previous simulation. Returns S, I, F, D at
#' daily resolution plus derived quantities (parasitism rate, defoliation
#' rate, peak events, and functional response data).
#'
#' @param params Named list of parameters.
#' @param sim_result Data frame from \code{simulate()} with columns year, A, F, K, D.
#' @param year Integer year index (0-based, matching the sim_result$year column).
#' @return A list with components:
#'   \describe{
#'     \item{trajectory}{Data frame with columns: time, S, I, F, D, parasitism_rate, defoliation_rate}
#'     \item{peak_parasitism_day}{Day of peak parasitism rate}
#'     \item{peak_parasitism_value}{Value at peak parasitism}
#'     \item{peak_defoliation_rate_day}{Day of peak defoliation rate}
#'     \item{peak_defoliation_rate_value}{Value at peak defoliation rate}
#'     \item{functional_response}{Data frame with S_range and fr columns}
#'   }
#' @export
season_trajectory <- function(params, sim_result, year) {
  # Find the row for the requested year
  idx <- which(sim_result$year == year)
  if (length(idx) == 0) stop("Year ", year, " not found in simulation result.")
  if (year >= max(sim_result$year)) stop("Cannot view within-season for the last year (no annual map step).")

  A_t <- sim_result$A[idx]
  F_t <- sim_result$F[idx]
  K_t <- sim_result$K[idx]

  # Beverton-Holt recruitment at season start
  S0 <- params[["R_B"]] * A_t / (1 + A_t / K_t)

  # High-resolution daily integration
  times <- seq(0, params[["T"]], length.out = 500)
  result <- integrate_season(params, S0 = S0, I0 = 0, F0 = F_t, D0 = 0, times = times)
  traj <- result$trajectory

  # Derived quantities
  traj$parasitism_rate <- params[["beta"]] * pmax(traj$S, 0) * pmax(traj$F, 0) /
    (1 + params[["h"]] * pmax(traj$S, 0))
  traj$defoliation_rate <- params[["kappa"]] * (pmax(traj$S, 0) + pmax(traj$I, 0))

  # Peak parasitism
  peak_par_idx <- which.max(traj$parasitism_rate)
  peak_par_day <- traj$time[peak_par_idx]
  peak_par_val <- traj$parasitism_rate[peak_par_idx]

  # Peak defoliation rate
  peak_def_idx <- which.max(traj$defoliation_rate)
  peak_def_day <- traj$time[peak_def_idx]
  peak_def_val <- traj$defoliation_rate[peak_def_idx]

  # Functional response curve
  S_max <- max(traj$S, na.rm = TRUE)
  S_range <- seq(0, S_max * 1.5 + 0.01, length.out = 200)
  fr <- params[["beta"]] * S_range / (1 + params[["h"]] * S_range)
  fr_df <- data.frame(S_range = S_range, fr = fr)

  list(
    trajectory = traj,
    peak_parasitism_day = peak_par_day,
    peak_parasitism_value = peak_par_val,
    peak_defoliation_rate_day = peak_def_day,
    peak_defoliation_rate_value = peak_def_val,
    functional_response = fr_df
  )
}

#' Compute resistance R1 (manuscript Section 2.4, Eq. R1).
#'
#' R1 = (x_ref - x_max_dev) / x_ref
#'
#' @param params Named list of parameters.
#' @param A_star Equilibrium beetle density (x_ref).
#' @param F_star Equilibrium parasitoid density.
#' @param K_star Equilibrium carrying capacity.
#' @param D_star Equilibrium defoliation.
#' @param perturbation_frac Fraction of A_star to perturb (default 0.2).
#' @param n_years Number of years to simulate after perturbation.
#' @return Numeric scalar R1 in [-1, 1].
#' @export
compute_R1 <- function(params, A_star, F_star, K_star, D_star,
                        perturbation_frac = 0.2, n_years = 50) {
  if (A_star < 1e-12) return(NA_real_)

  A0_pert <- A_star * (1 + perturbation_frac)
  sim <- simulate(params, A0 = A0_pert, F0 = F_star, K0 = K_star,
                  D0 = D_star, n_years = n_years)

  x_max_dev <- max(abs(sim$A - A_star))
  R1 <- (A_star - x_max_dev) / A_star
  max(min(R1, 1), -1)
}

#' Compute resilience R2 (manuscript Section 2.4, Eq. R2).
#'
#' R2 = (x_max_dev - x_Y) / x_max_dev
#'
#' @param params Named list of parameters.
#' @param A_star Equilibrium beetle density.
#' @param F_star Equilibrium parasitoid density.
#' @param K_star Equilibrium carrying capacity.
#' @param D_star Equilibrium defoliation.
#' @param perturbation_frac Fraction of A_star to perturb (default 0.2).
#' @param Y Recovery window in years (default 5).
#' @param n_years Total simulation years.
#' @return Numeric scalar R2.
#' @export
compute_R2 <- function(params, A_star, F_star, K_star, D_star,
                        perturbation_frac = 0.2, Y = 5, n_years = 50) {
  if (A_star < 1e-12) return(NA_real_)

  A0_pert <- A_star * (1 + perturbation_frac)
  sim <- simulate(params, A0 = A0_pert, F0 = F_star, K0 = K_star,
                  D0 = D_star, n_years = n_years)

  deviations <- abs(sim$A - A_star)
  max_dev_idx <- which.max(deviations)
  x_max_dev <- deviations[max_dev_idx]

  if (x_max_dev < 1e-12) return(1.0)

  y_idx <- min(max_dev_idx + Y, length(sim$A))
  x_Y <- abs(sim$A[y_idx] - A_star)
  (x_max_dev - x_Y) / x_max_dev
}

#' Sweep a parameter and compute R1, R2 at each value (adaptive stability profile).
#'
#' @param params Named list of parameters.
#' @param param_name Name of the parameter to sweep.
#' @param param_range Numeric vector of parameter values.
#' @param A_star Equilibrium beetle density.
#' @param F_star Equilibrium parasitoid density.
#' @param K_star Equilibrium carrying capacity.
#' @param D_star Equilibrium defoliation.
#' @param perturbation_frac Fraction of A_star to perturb (default 0.2).
#' @param Y Recovery window in years (default 5).
#' @param n_years Total simulation years (default 50).
#' @return A data.frame with columns: param_value, R1, R2.
#' @export
adaptive_stability <- function(params, param_name, param_range,
                                A_star = NULL, F_star = NULL,
                                K_star = NULL, D_star = NULL,
                                perturbation_frac = 0.2, Y = 5,
                                n_years = 50) {
  R1_arr <- numeric(length(param_range))
  R2_arr <- numeric(length(param_range))

  for (i in seq_along(param_range)) {
    p <- params
    p[[param_name]] <- param_range[i]

    # If equilibrium not supplied, find it
    a_s <- A_star
    f_s <- F_star
    k_s <- K_star
    d_s <- D_star

    if (is.null(a_s)) {
      tryCatch({
        fps <- find_fixed_points(p)
        coex <- fps[fps$class == "coexistence", ]
        if (nrow(coex) > 0) {
          a_s <- coex$A_star[1]
          f_s <- coex$F_star[1]
          k_s <- coex$K_star[1]
          d_s <- coex$D_star[1]
        } else {
          nontrivial <- fps[fps$A_star > 1e-8, ]
          if (nrow(nontrivial) > 0) {
            a_s <- nontrivial$A_star[1]
            f_s <- nontrivial$F_star[1]
            k_s <- nontrivial$K_star[1]
            d_s <- nontrivial$D_star[1]
          } else {
            R1_arr[i] <- NA_real_
            R2_arr[i] <- NA_real_
            next
          }
        }
      }, error = function(e) {
        R1_arr[i] <<- NA_real_
        R2_arr[i] <<- NA_real_
      })
      if (is.na(R1_arr[i])) next
    }

    tryCatch({
      R1_arr[i] <- compute_R1(p, a_s, f_s, k_s, d_s,
                               perturbation_frac = perturbation_frac,
                               n_years = n_years)
      R2_arr[i] <- compute_R2(p, a_s, f_s, k_s, d_s,
                               perturbation_frac = perturbation_frac,
                               Y = Y, n_years = n_years)
    }, error = function(e) {
      R1_arr[i] <<- NA_real_
      R2_arr[i] <<- NA_real_
    })
  }

  data.frame(
    param_value = param_range,
    R1 = R1_arr,
    R2 = R2_arr
  )
}

#' Compute latitude: maximum perturbation the system can absorb (Section 2.4).
#'
#' @param params Named list of parameters.
#' @param A_star Equilibrium beetle density.
#' @param F_star Equilibrium parasitoid density.
#' @param K_star Equilibrium carrying capacity.
#' @param D_star Equilibrium defoliation.
#' @param max_delta Maximum perturbation fraction to test (default 2.0).
#' @param n_steps Number of perturbation levels (default 50).
#' @param n_years Iterations for return test (default 50).
#' @param tol Relative tolerance for return (default 0.1).
#' @return Numeric scalar latitude (perturbation fraction).
#' @export
compute_latitude <- function(params, A_star, F_star, K_star, D_star,
                              max_delta = 2.0, n_steps = 50, n_years = 50,
                              tol = 0.1) {
  if (A_star < 1e-12) return(0)

  latitude <- 0
  for (i in seq_len(n_steps)) {
    delta <- (i / n_steps) * max_delta
    A0_pert <- A_star * (1 + delta)

    sim <- simulate(params, A0 = A0_pert, F0 = F_star, K0 = K_star,
                    D0 = D_star, n_years = n_years)

    A_final <- sim$A[length(sim$A)]
    returned <- abs(A_final - A_star) < tol * A_star

    if (returned) {
      latitude <- delta
    } else {
      break
    }
  }

  latitude
}
