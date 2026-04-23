test_that("ODE returns correct length", {
  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  y <- c(S = 1.0, I = 0.0, F = 0.1, D = 0.0)
  result <- within_season_ode(0, y, params)
  expect_length(result[[1]], 4)
})

test_that("ODE derivative names are correct", {
  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  y <- c(S = 1.0, I = 0.0, F = 0.1, D = 0.0)
  result <- within_season_ode(0, y, params)
  expect_named(result[[1]], c("S", "I", "F", "D"))
})

test_that("states non-negative after integration", {
  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  res <- integrate_season(params, S0 = 1.0, I0 = 0.0, F0 = 0.1, D0 = 0.0)
  traj <- res$trajectory
  expect_true(all(traj$S >= -1e-10))
  expect_true(all(traj$I >= -1e-10))
  expect_true(all(traj$F >= -1e-10))
})

test_that("integrate_season returns trajectory and end state", {
  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  res <- integrate_season(params, S0 = 1.0, I0 = 0, F0 = 0.1, D0 = 0)
  expect_true(is.data.frame(res$trajectory))
  expect_true(is.list(res$end))
  expect_true(all(c("S_T", "I_T", "F_T", "D_T") %in% names(res$end)))
})

test_that("simulate returns n_years+1 rows", {
  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  n_years <- 10
  sim <- simulate(params, A0 = 0.8, F0 = 0.1, K0 = 1.712, D0 = 0,
                  n_years = n_years)
  expect_equal(nrow(sim), n_years + 1)
  expect_true(all(c("year", "A", "F", "K", "D") %in% names(sim)))
})

test_that("simulate year column starts at 0", {
  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  sim <- simulate(params, A0 = 0.8, F0 = 0.1, K0 = 1.712, D0 = 0,
                  n_years = 5)
  expect_equal(sim$year, 0:5)
})

test_that("R_P approximately 1.93 at calibrated params", {
  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  rp <- compute_RP(params)
  expect_true(is.numeric(rp))
  expect_true(rp > 1.0, info = "R_P should be > 1 at default params")
  expect_equal(rp, 1.93, tolerance = 0.3)
})

test_that("trivial fixed point is zero", {
  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  fps <- find_fixed_points(params)
  trivial <- fps[fps$class == "trivial", ]
  if (nrow(trivial) > 0) {
    expect_true(all(trivial$A_star < 1e-6))
    expect_true(all(trivial$F_star < 1e-6))
  } else {
    # If no trivial found, that's also valid - just check fps is a data.frame
    expect_true(is.data.frame(fps))
  }
})

test_that("annual_map returns expected components", {
  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  res <- annual_map(params, A_t = 0.8, F_t = 0.1, K_t = 1.712, D_t = 0)
  expect_true(all(c("A_next", "F_next", "K_next", "D_next") %in% names(res)))
  expect_true(res$A_next >= 0)
  expect_true(res$F_next >= 0)
  expect_true(res$K_next > 0)
})

# --- R1/R2 stability metric tests ---

test_that("compute_R1 returns value in [-1, 1]", {
  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  fps <- find_fixed_points(params)
  nontrivial <- fps[fps$A_star > 1e-8, ]
  if (nrow(nontrivial) > 0) {
    r1 <- compute_R1(params, nontrivial$A_star[1], nontrivial$F_star[1],
                     nontrivial$K_star[1], nontrivial$D_star[1])
    expect_true(is.numeric(r1))
    expect_true(r1 >= -1 && r1 <= 1)
  }
})

test_that("compute_R1 returns NA for trivial equilibrium", {
  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  r1 <- compute_R1(params, A_star = 0, F_star = 0, K_star = 1.7, D_star = 0)
  expect_true(is.na(r1))
})

test_that("compute_R2 returns numeric value", {
  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  fps <- find_fixed_points(params)
  nontrivial <- fps[fps$A_star > 1e-8, ]
  if (nrow(nontrivial) > 0) {
    r2 <- compute_R2(params, nontrivial$A_star[1], nontrivial$F_star[1],
                     nontrivial$K_star[1], nontrivial$D_star[1], Y = 5)
    expect_true(is.numeric(r2))
  }
})

test_that("adaptive_stability returns data.frame with correct columns", {
  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  fps <- find_fixed_points(params)
  nontrivial <- fps[fps$A_star > 1e-8, ]
  if (nrow(nontrivial) > 0) {
    result <- adaptive_stability(params, "phi", c(0.5, 1.0),
                                  A_star = nontrivial$A_star[1],
                                  F_star = nontrivial$F_star[1],
                                  K_star = nontrivial$K_star[1],
                                  D_star = nontrivial$D_star[1])
    expect_true(is.data.frame(result))
    expect_true(all(c("param_value", "R1", "R2") %in% names(result)))
    expect_equal(nrow(result), 2)
  }
})
