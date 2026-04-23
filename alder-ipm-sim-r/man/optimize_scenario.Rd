\name{optimize_scenario}
\alias{optimize_scenario}
\title{Optimize Control for a Management Scenario}
\description{
Minimise a cost functional that penalises defoliation, larval density,
and control effort over a multi-year horizon. Three scenarios are
available: A (parasitoid augmentation only), B (parasitoid + bird
habitat), C (full integrated control).
}
\usage{
optimize_scenario(params, scenario = "C", initial_state, n_years = 50)
}
\arguments{
\item{params}{Named list of parameters.}
\item{scenario}{Character: \code{"A"}, \code{"B"}, or \code{"C"}.}
\item{initial_state}{Named numeric vector \code{c(A=, F=, K=, D=)}.}
\item{n_years}{Integer simulation horizon (default 50).}
}
\value{
A list with components: \code{scenario}, \code{optimal_controls},
\code{cost}, \code{final_equilibrium}, \code{D_star}, \code{K_star},
\code{rho_star}, \code{feasible}, \code{violations}.
}
\examples{
\dontrun{
params <- as.list(default_params())
ic <- c(A = 0.8, F = 0.1, K = 1.712, D = 0)
result <- optimize_scenario(params, scenario = "C", initial_state = ic)
}
}
