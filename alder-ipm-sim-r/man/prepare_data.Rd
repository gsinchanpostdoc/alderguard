\name{prepare_data}
\alias{prepare_data}
\title{Prepare and Validate Data for Model Fitting}
\description{
Validate a data.frame for model fitting: checks time ordering,
NaN values, and maps user-supplied column names to the internal
state variable convention (A, F, K, D).
}
\usage{
prepare_data(data, time_col = "year", state_cols = NULL,
             timestep = "annual")
}
\arguments{
\item{data}{A data.frame containing time series observations.}
\item{time_col}{Character string naming the time column (default
  \code{"year"}).}
\item{state_cols}{Named character vector mapping state variable names
  to column names, e.g. \code{c(A = "beetle_density")}. If \code{NULL},
  looks for columns named A, F, K, D directly.}
\item{timestep}{Character, either \code{"annual"} (default) or
  \code{"seasonal"}.}
}
\value{
A list with components \code{times} (numeric vector), \code{obs}
(named list of numeric vectors keyed by state name), \code{timestep}
(character), and \code{n_obs} (integer).
}
\examples{
df <- data.frame(year = 1:10, A = runif(10), D = runif(10, 0, 0.5))
prepared <- prepare_data(df)
prepared$n_obs
}
