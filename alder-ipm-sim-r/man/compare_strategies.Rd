\name{compare_strategies}
\alias{compare_strategies}
\title{Compare All Three Management Strategies}
\description{
Run \code{\link{optimize_scenario}} for scenarios A, B, and C, and
return a comparison table with a recommended strategy.
}
\usage{
compare_strategies(params, initial_state, n_years = 50)
}
\arguments{
\item{params}{Named list of parameters.}
\item{initial_state}{Named numeric vector \code{c(A=, F=, K=, D=)}.}
\item{n_years}{Integer simulation horizon (default 50).}
}
\value{
A list with components: \code{comparison} (data.frame with one row per
scenario), \code{recommended} (character scenario label or \code{NA}),
and \code{interpretation} (character string).
}
\examples{
\dontrun{
params <- as.list(default_params())
ic <- c(A = 0.8, F = 0.1, K = 1.712, D = 0)
comp <- compare_strategies(params, initial_state = ic)
print(comp$comparison)
}
}
