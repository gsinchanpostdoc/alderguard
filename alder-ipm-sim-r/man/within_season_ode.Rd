\name{within_season_ode}
\alias{within_season_ode}
\title{Within-Season ODE Right-Hand Side}
\description{
Compute the derivatives for the within-season ODE system. The state
vector \code{y = c(S, I, F, D)} represents susceptible larvae,
parasitised larvae, adult parasitoid flies, and cumulative defoliation.
Compatible with \code{deSolve::ode}.
}
\usage{
within_season_ode(tau, y, params)
}
\arguments{
\item{tau}{Time within the season (days).}
\item{y}{Named numeric vector \code{c(S=, I=, F=, D=)}.}
\item{params}{Named list of parameters (must include \code{u_C} and
  \code{u_P} for control inputs).}
}
\value{
A list containing the derivative vector, as required by
\code{deSolve::ode}.
}
\examples{
params <- as.list(default_params())
params$u_C <- 0
params$u_P <- 0
y0 <- c(S = 0.8, I = 0, F = 0.1, D = 0)
derivs <- within_season_ode(0, y0, params)
}
