\name{fit_model}
\alias{fit_model}
\title{Fit Model Parameters to Time Series Data}
\description{
Estimate parameters by minimising the sum of squared residuals between
simulated and observed trajectories. Supports bounded L-BFGS-B
optimisation and global search via differential evolution.
}
\usage{
fit_model(data, fit_params = NULL, params = NULL,
          method = "nls", bounds = TRUE)
}
\arguments{
\item{data}{Prepared data list (output of \code{\link{prepare_data}}).}
\item{fit_params}{Character vector of parameter names to estimate.
  If \code{NULL}, a default identifiable subset is used.}
\item{params}{Named list of parameters. If \code{NULL}, uses
  \code{\link{default_params}()}.}
\item{method}{Character: \code{"nls"} (default), \code{"optim"}, or
  \code{"de"}.}
\item{bounds}{Logical; if \code{TRUE} (default), enforce parameter
  bounds from the registry.}
}
\value{
A list with components: \code{fitted_params} (named numeric vector),
\code{residuals} (numeric vector), \code{r_squared} (numeric),
\code{AIC} (numeric), \code{BIC} (numeric), \code{conf_intervals}
(named list of length-2 vectors), \code{convergence} (list with
optimizer details).
}
\examples{
\dontrun{
params <- default_params()
sim <- simulate(as.list(params), A0 = 0.8, F0 = 0.1,
                K0 = 1.712, D0 = 0, n_years = 20)
prepared <- prepare_data(sim, time_col = "year")
result <- fit_model(prepared, fit_params = c("beta", "phi"))
}
}
