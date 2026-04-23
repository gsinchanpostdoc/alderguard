\name{predict_trajectory}
\alias{predict_trajectory}
\title{Project Forward from a Fitted Model}
\description{
Simulate the system forward from a fitted model for a given number of
years. Uncertainty bands are computed via Monte Carlo sampling from the
parameter covariance.
}
\usage{
predict_trajectory(fit_result, n_years_ahead, initial_state = NULL)
}
\arguments{
\item{fit_result}{List returned by \code{\link{fit_model}}.}
\item{n_years_ahead}{Integer number of years to project forward.}
\item{initial_state}{Named numeric vector \code{c(A=, F=, K=, D=)}.
  If \code{NULL}, uses sensible defaults.}
}
\value{
A data.frame with columns: year, A, F, K, D, and uncertainty bands
A_lo, A_hi, F_lo, F_hi, K_lo, K_hi, D_lo, D_hi (2.5th and 97.5th
percentiles from Monte Carlo).
}
\examples{
\dontrun{
fit <- fit_model(prepared, fit_params = c("beta", "phi"))
pred <- predict_trajectory(fit, n_years_ahead = 10)
}
}
