test_that("detrend removes linear trend", {
  n <- 100
  trend <- seq(0, 10, length.out = n)
  noise <- rnorm(n, sd = 0.1)
  ts <- trend + noise
  residuals <- detrend_ts(ts, method = "linear")
  expect_length(residuals, n)
  # Residuals should have near-zero mean

  expect_equal(mean(residuals), 0, tolerance = 0.05)
  # Residuals should be much smaller than original range
  expect_true(sd(residuals) < sd(ts))
})

test_that("detrend gaussian method works", {
  ts <- sin(seq(0, 4 * pi, length.out = 50)) + rnorm(50, sd = 0.1)
  residuals <- detrend_ts(ts, method = "gaussian")
  expect_length(residuals, 50)
})

test_that("detrend errors on short series", {
  expect_error(detrend_ts(c(1, 2)), "at least 3")
})

test_that("detrend errors on unknown method", {
  expect_error(detrend_ts(rnorm(10), method = "foo"), "Unknown")
})

test_that("rolling variance of constant is zero", {
  ts <- rep(5, 50)
  rv <- rolling_variance(ts, window = 10)
  expect_true(all(abs(rv) < 1e-15))
})

test_that("rolling variance length is correct", {
  n <- 50
  w <- 10
  rv <- rolling_variance(rnorm(n), window = w)
  expect_length(rv, n - w + 1)
})

test_that("rolling variance is non-negative", {
  rv <- rolling_variance(rnorm(50), window = 10)
  expect_true(all(rv >= 0))
})

test_that("rolling autocorrelation of constant is zero", {
  ts <- rep(3, 50)
  rac <- rolling_autocorrelation(ts, window = 10, lag = 1)
  expect_true(all(abs(rac) < 1e-10))
})

test_that("rolling autocorrelation bounded between -1 and 1", {
  rac <- rolling_autocorrelation(rnorm(50), window = 10, lag = 1)
  expect_true(all(rac >= -1 - 1e-10))
  expect_true(all(rac <= 1 + 1e-10))
})

test_that("rolling skewness length is correct", {
  n <- 50
  w <- 10
  rs <- rolling_skewness(rnorm(n), window = w)
  expect_length(rs, n - w + 1)
})

test_that("compute_ews returns expected columns", {
  ews <- compute_ews(rnorm(50), window = 10)
  expect_true(is.data.frame(ews))
  expect_true(all(c("time", "variance", "autocorrelation", "skewness") %in%
                    names(ews)))
})

test_that("kendall_trend returns tau and p_value", {
  result <- kendall_trend(cumsum(rnorm(30)))
  expect_true("tau" %in% names(result))
  expect_true("p_value" %in% names(result))
  expect_true(abs(result$tau) <= 1)
  expect_true(result$p_value >= 0 && result$p_value <= 1)
})

test_that("alert green for stable data", {
  set.seed(123)
  stable_ts <- rnorm(100, mean = 5, sd = 0.1)
  result <- detect_warnings(stable_ts, window = 20)
  expect_true(result$alert_level %in% c("green", "yellow", "red"))
  # Stable iid noise should generally yield green
  expect_equal(result$alert_level, "green")
})

test_that("detect_warnings returns required components", {
  result <- detect_warnings(rnorm(50), window = 10)
  expect_true(all(c("indicators", "kendall_results", "alert_level",
                     "interpretation") %in% names(result)))
  expect_true(is.data.frame(result$indicators))
  expect_true(is.character(result$interpretation))
})

# ── LHS-PRCC Sensitivity Analysis Tests ──────────────────────────────

test_that("lhs_param_names returns 9 parameters", {
  pn <- lhs_param_names()
  expect_length(pn, 9)
  expect_true("phi" %in% pn)
  expect_true("beta" %in% pn)
})

test_that("lhs_param_ranges returns named list", {
  ranges <- lhs_param_ranges()
  pn <- lhs_param_names()
  for (nm in pn) {
    expect_true(nm %in% names(ranges))
    expect_length(ranges[[nm]], 2)
    expect_true(ranges[[nm]][1] < ranges[[nm]][2])
  }
})

test_that("latin_hypercube_sample shape and bounds", {
  samples <- latin_hypercube_sample(n_samples = 20, seed = 42)
  expect_equal(nrow(samples), 20)
  expect_equal(ncol(samples), 9)
  ranges <- lhs_param_ranges()
  pn <- lhs_param_names()
  for (j in seq_along(pn)) {
    rng <- ranges[[pn[j]]]
    expect_true(all(samples[, j] >= rng[1] - 1e-10))
    expect_true(all(samples[, j] <= rng[2] + 1e-10))
  }
})

test_that("latin_hypercube_sample reproducible with seed", {
  s1 <- latin_hypercube_sample(n_samples = 10, seed = 99)
  s2 <- latin_hypercube_sample(n_samples = 10, seed = 99)
  expect_equal(s1, s2)
})

test_that("compute_prcc output shape and bounds", {
  set.seed(42)
  samples <- matrix(runif(100), ncol = 5)
  colnames(samples) <- paste0("X", 1:5)
  output <- runif(20)
  result <- compute_prcc(samples, output)
  expect_true(is.data.frame(result))
  expect_equal(nrow(result), 5)
  expect_true(all(c("parameter", "prcc", "p_value") %in% names(result)))
  expect_true(all(abs(result$prcc) <= 1 + 1e-10))
})

test_that("compute_prcc detects known correlation", {
  set.seed(42)
  n <- 100
  x1 <- runif(n)
  x2 <- runif(n)
  y <- x1 * 3 + rnorm(n, sd = 0.01)
  samples <- cbind(x1 = x1, x2 = x2)
  result <- compute_prcc(samples, y)
  expect_true(result$prcc[1] > 0.9)
  expect_true(result$p_value[1] < 0.01)
})

test_that("regime_shift_probability correct", {
  expect_equal(regime_shift_probability(rep("coexistence", 10)), 0)
  expect_equal(regime_shift_probability(rep("parasitoid_free", 10)), 1)
  expect_equal(regime_shift_probability(c(rep("coexistence", 7),
                                          rep("parasitoid_free", 3))), 0.3)
  expect_equal(regime_shift_probability(character(0)), 0)
})
