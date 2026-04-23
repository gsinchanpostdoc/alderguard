# Tests for equilibrium analysis functions

test_that("find_fixed_points returns at least trivial equilibrium", {
  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  fps <- find_fixed_points(params, n_starts = 10)
  expect_true(is.data.frame(fps))
  expect_true(nrow(fps) >= 1)
  expect_true(all(c("A_star", "F_star", "K_star", "D_star", "class", "stable",
                     "rho_star", "bifurcation") %in% names(fps)))
})

test_that("jacobian_numerical returns 4x4 matrix with finite values", {
  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  state <- c(0.5, 0.05, 1.5, 0.1)
  jac <- jacobian_numerical(params, state)
  expect_equal(dim(jac), c(4, 4))
  expect_true(all(is.finite(jac)))
})

test_that("jacobian_numerical handles zero state without divide-by-zero", {
  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  state <- c(0, 0, 1.712, 0)
  jac <- jacobian_numerical(params, state)
  expect_equal(dim(jac), c(4, 4))
  expect_true(all(is.finite(jac)))
})

test_that("classify_stability correctly identifies stable equilibrium", {
  # Diagonal matrix with all eigenvalues < 1
  jac_stable <- diag(c(0.5, 0.3, 0.8, 0.2))
  result <- classify_stability(jac_stable)
  expect_true(result$stable)
  expect_equal(result$bifurcation_type, "stable")
  expect_true(result$rho_star < 1)
})

test_that("classify_stability correctly identifies unstable equilibrium", {
  # Diagonal matrix with one eigenvalue > 1
  jac_unstable <- diag(c(1.5, 0.3, 0.8, 0.2))
  result <- classify_stability(jac_unstable)
  expect_false(result$stable)
  expect_true(result$rho_star > 1)
  expect_equal(result$bifurcation_type, "fold")
})

test_that("classify_stability detects flip bifurcation", {
  jac_flip <- diag(c(-1.2, 0.3, 0.8, 0.2))
  result <- classify_stability(jac_flip)
  expect_false(result$stable)
  expect_equal(result$bifurcation_type, "flip")
})

test_that("coexistence equilibrium found with calibrated parameters", {
  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  fps <- find_fixed_points(params, n_starts = 20)
  coex <- fps[fps$class == "coexistence", ]
  # With default (calibrated) parameters, coexistence should exist
  expect_true(nrow(coex) >= 1, info = "Expected coexistence equilibrium at default params")
  if (nrow(coex) > 0) {
    expect_true(coex$A_star[1] > 0)
    expect_true(coex$F_star[1] > 0)
    expect_true(coex$K_star[1] > 0)
  }
})

test_that("find_fixed_points returns valid rho_star values", {
  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  fps <- find_fixed_points(params, n_starts = 10)
  # rho_star should be non-negative where not NA
  valid_rho <- fps$rho_star[!is.na(fps$rho_star)]
  expect_true(all(valid_rho >= 0))
})
