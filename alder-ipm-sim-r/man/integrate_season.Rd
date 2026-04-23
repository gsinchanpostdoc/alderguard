\name{integrate_season}
\alias{integrate_season}
\title{Integrate the Within-Season ODE}
\description{
Numerically integrate the within-season ODE system over the larval
vulnerability window using \code{deSolve::ode} with the LSODA method.
}
\usage{
integrate_season(params, S0, I0, F0, D0, times = NULL)
}
\arguments{
\item{params}{Named list of parameters.}
\item{S0}{Initial susceptible larvae density.}
\item{I0}{Initial parasitised larvae density.}
\item{F0}{Initial parasitoid fly density.}
\item{D0}{Initial cumulative defoliation.}
\item{times}{Numeric vector of output times. Defaults to
  \code{seq(0, T, length.out = 200)}.}
}
\value{
A list with components \code{trajectory} (data.frame with columns
time, S, I, F, D) and \code{end} (named list with S_T, I_T, F_T, D_T).
}
\examples{
params <- as.list(default_params())
params$u_C <- 0
params$u_P <- 0
result <- integrate_season(params, S0 = 0.8, I0 = 0, F0 = 0.1, D0 = 0)
tail(result$trajectory, 3)
}
