\name{feasibility_check}
\alias{feasibility_check}
\title{Check Feasibility of a Management Outcome}
\description{
Evaluate whether all ecological and stability criteria are satisfied
for a management outcome.
}
\usage{
feasibility_check(D_star, K_star, rho_star, F_star, params)
}
\arguments{
\item{D_star}{Numeric equilibrium defoliation.}
\item{K_star}{Numeric equilibrium carrying capacity.}
\item{rho_star}{Numeric spectral radius of the Jacobian.}
\item{F_star}{Numeric equilibrium parasitoid density.}
\item{params}{Named list of parameters (needs D_crit and K_min).}
}
\value{
A list with components \code{feasible} (logical) and
\code{violations} (character vector).
}
\examples{
params <- as.list(default_params())
feas <- feasibility_check(0.3, 1.5, 0.8, 0.05, params)
feas$feasible
}
