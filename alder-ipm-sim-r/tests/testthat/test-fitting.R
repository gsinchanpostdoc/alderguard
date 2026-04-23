test_that("prepare_data validates input", {
  # Not a data.frame
  expect_error(prepare_data("not a df"), "data.frame")

  # Missing time column
  df <- data.frame(t = 1:5, A = runif(5))
  expect_error(prepare_data(df, time_col = "year"), "not found")

  # Non-increasing time
  df <- data.frame(year = c(1, 3, 2), A = runif(3))
  expect_error(prepare_data(df), "strictly increasing")

  # Invalid timestep
  df <- data.frame(year = 1:5, A = runif(5))
  expect_error(prepare_data(df, timestep = "monthly"), "annual.*seasonal")
})

test_that("prepare_data returns correct structure", {
  df <- data.frame(year = 1:10, A = runif(10), D = runif(10, 0, 0.5))
  result <- prepare_data(df)
  expect_true(is.list(result))
  expect_true(all(c("times", "obs", "timestep", "n_obs") %in% names(result)))
  expect_equal(result$n_obs, 10)
  expect_equal(result$timestep, "annual")
  expect_true("A" %in% names(result$obs))
  expect_true("D" %in% names(result$obs))
})

test_that("prepare_data respects state_cols mapping", {
  df <- data.frame(year = 1:5, beetle = runif(5), defol = runif(5, 0, 0.5))
  result <- prepare_data(df, state_cols = c(A = "beetle", D = "defol"))
  expect_true("A" %in% names(result$obs))
  expect_true("D" %in% names(result$obs))
})

test_that("fit recovers known parameters", {
  skip_on_cran()

  # Generate synthetic data from known parameters
  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  K0 <- params$K_0
  sim <- simulate(params, A0 = K0 * 0.5, F0 = 0.1, K0 = K0, D0 = 0,
                  n_years = 30)

  # Prepare data
  prepared <- prepare_data(sim, time_col = "year")

  # Fit just two parameters to keep it fast
  fit_names <- c("beta", "phi")
  result <- fit_model(prepared, fit_params = fit_names, params = params,
                      method = "optim")

  expect_true(is.list(result))
  expect_true(all(c("fitted_params", "residuals", "r_squared", "AIC", "BIC",
                     "conf_intervals", "convergence") %in% names(result)))

  # Fitted values should be close to true values (within 50% for this
  # synthetic perfect-data scenario)
  for (nm in fit_names) {
    true_val <- params[[nm]]
    fitted_val <- result$fitted_params[[nm]]
    expect_equal(fitted_val, true_val, tolerance = true_val * 0.5,
                 info = paste0("Parameter ", nm, " not recovered"))
  }

  # R-squared should be high for noise-free data
  expect_true(result$r_squared > 0.9)
})

test_that("forecast_regime returns valid structure", {
  skip_on_cran()

  params <- as.list(default_params())
  params$u_C <- 0
  params$u_P <- 0
  K0 <- params$K_0
  sim <- simulate(params, A0 = K0 * 0.5, F0 = 0.1, K0 = K0, D0 = 0,
                  n_years = 20)
  prepared <- prepare_data(sim, time_col = "year")
  fit <- fit_model(prepared, fit_params = c("beta"), params = params,
                   method = "optim")

  regime <- forecast_regime(fit)
  expect_true(is.list(regime))
  expect_true(regime$equilibrium_class %in%
                c("trivial", "canopy_only", "parasitoid_free", "coexistence"))
  expect_true(is.numeric(regime$R_P))
  expect_true(is.character(regime$interpretation))
})
