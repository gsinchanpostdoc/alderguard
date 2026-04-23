test_that("all parameters present", {
  reg <- param_registry()
  expected <- c("beta", "h", "c_B", "a_B", "mu_S", "mu_I", "delta", "eta",
                "mu_F", "kappa", "T", "B_index", "R_B", "sigma_A", "sigma_F",
                "K_0", "phi")
  expect_true(all(expected %in% names(reg)))
})

test_that("registry has 23 parameters", {
  reg <- param_registry()
  expect_equal(length(reg), 23)
})

test_that("each parameter has required fields", {
  reg <- param_registry()
  required_fields <- c("symbol", "default", "min", "max", "unit",
                       "description", "module", "category")
  for (nm in names(reg)) {
    for (field in required_fields) {
      expect_true(!is.null(reg[[nm]][[field]]),
                  info = paste0("Parameter '", nm, "' missing field '", field, "'"))
    }
  }
})

test_that("defaults within bounds", {
  reg <- param_registry()
  for (nm in names(reg)) {
    meta <- reg[[nm]]
    expect_true(meta$default >= meta$min,
                info = paste0(nm, " default below min"))
    expect_true(meta$default <= meta$max,
                info = paste0(nm, " default above max"))
  }
})

test_that("default_params returns named numeric vector", {
  dp <- default_params()
  expect_type(dp, "double")
  expect_true(length(dp) == 23)
  expect_true(!is.null(names(dp)))
})

test_that("default_params values match registry", {
  dp <- default_params()
  reg <- param_registry()
  for (nm in names(dp)) {
    expect_equal(dp[[nm]], reg[[nm]]$default, tolerance = 1e-12,
                 info = paste0("Mismatch for ", nm))
  }
})

test_that("validate_params catches out-of-bounds", {
  dp <- default_params()
  dp[["beta"]] <- 999
  expect_warning(validate_params(dp), "beta")
})

test_that("validate_params silent for valid params", {
  dp <- default_params()
  expect_silent(validate_params(dp))
})

test_that("validate_params catches multiple violations", {
  dp <- default_params()
  dp[["beta"]] <- 999
  dp[["mu_S"]] <- -1
  warns <- capture_warnings(validate_params(dp))
  expect_true(length(warns) >= 2)
})

test_that("print_params runs without error", {
  expect_output(print_params(), "Name")
})

test_that("print_params filters by category", {
  output <- capture.output(print_params(category = "mortality"))
  # Should have fewer rows than the full set
  full <- capture.output(print_params())
  expect_true(length(output) < length(full))
})
