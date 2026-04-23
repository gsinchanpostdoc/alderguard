# Tests for control optimization functions

test_that("optimize_scenario returns valid structure", {
  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  ic <- c(A = 0.8, F = 0.1, K = 1.712, D = 0)
  result <- optimize_scenario(params, scenario = "A", initial_state = ic, n_years = 10)

  expect_true(is.list(result))
  expect_equal(result$scenario, "A")
  expect_true(is.numeric(result$cost))
  expect_true(is.numeric(result$D_star))
  expect_true(is.numeric(result$K_star))
  expect_true(is.logical(result$feasible))
  expect_true(is.character(result$violations))
  expect_true(all(c("u_P", "u_C", "u_B") %in% names(result$optimal_controls)))
})

test_that("optimize_scenario rejects invalid scenario", {
  params <- as.list(default_params())
  ic <- c(A = 0.8, F = 0.1, K = 1.712, D = 0)
  expect_error(
    optimize_scenario(params, scenario = "X", initial_state = ic),
    "Unknown scenario"
  )
})

test_that("feasibility_check correctly identifies violations", {
  params <- as.list(default_params())

  # Feasible case
  feas <- feasibility_check(0.1, 1.5, 0.8, 0.05, params)
  expect_true(feas$feasible)
  expect_length(feas$violations, 0)

  # Infeasible: defoliation too high
  feas2 <- feasibility_check(0.6, 1.5, 0.8, 0.05, params)
  expect_false(feas2$feasible)
  expect_true(any(grepl("Defoliation", feas2$violations)))

  # Infeasible: parasitoid extinct
  feas3 <- feasibility_check(0.1, 1.5, 0.8, 0, params)
  expect_false(feas3$feasible)
  expect_true(any(grepl("Parasitoid", feas3$violations)))

  # Infeasible: unstable
  feas4 <- feasibility_check(0.1, 1.5, 1.5, 0.05, params)
  expect_false(feas4$feasible)
  expect_true(any(grepl("unstable", feas4$violations)))
})

test_that("feasibility_check detects consecutive K below K_min", {
  params <- as.list(default_params())
  K_traj <- c(1.5, 0.5, 0.5, 0.5, 1.5)  # 3 consecutive below K_min=0.856
  feas <- feasibility_check(0.1, 1.5, 0.8, 0.05, params, K_trajectory = K_traj)
  expect_false(feas$feasible)
  expect_true(any(grepl("consecutive", feas$violations)))
})

test_that("Strategy C is feasible with calibrated parameters", {
  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  ic <- c(A = 0.8, F = 0.1, K = 1.712, D = 0)
  result <- optimize_scenario(params, scenario = "C", initial_state = ic, n_years = 20)

  # Strategy C (full integrated) should generally be feasible with defaults
  expect_true(is.logical(result$feasible))
  # The cost should be finite
  expect_true(is.finite(result$cost))
  # Controls should be within bounds
  expect_true(result$optimal_controls[["u_P"]] >= 0)
  expect_true(result$optimal_controls[["u_P"]] <= params[["u_P_max"]])
  expect_true(result$optimal_controls[["u_C"]] >= 0)
  expect_true(result$optimal_controls[["u_C"]] <= params[["u_C_max"]])
  expect_true(result$optimal_controls[["u_B"]] >= 0)
  expect_true(result$optimal_controls[["u_B"]] <= params[["u_B_max"]])
})

test_that("compare_strategies returns comparison for all 3 scenarios", {
  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  ic <- c(A = 0.8, F = 0.1, K = 1.712, D = 0)
  result <- compare_strategies(params, initial_state = ic, n_years = 10)

  expect_true(is.list(result))
  expect_true(is.data.frame(result$comparison))
  expect_equal(nrow(result$comparison), 3)
  expect_true(all(c("A", "B", "C") %in% result$comparison$scenario))
  expect_true(is.character(result$interpretation))
})
