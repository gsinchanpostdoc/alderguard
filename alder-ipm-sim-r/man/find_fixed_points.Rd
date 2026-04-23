\name{find_fixed_points}
\alias{find_fixed_points}
\title{Find Fixed Points of the Annual Map}
\description{
Find equilibria of the annual map from multiple randomised starting
points using \code{rootSolve::multiroot}. Each fixed point is
classified by type and stability.
}
\usage{
find_fixed_points(params, n_starts = 20, tol = 1e-8)
}
\arguments{
\item{params}{Named list of parameters.}
\item{n_starts}{Number of random starting points (default 20).}
\item{tol}{Tolerance for zero-checking and deduplication (default 1e-8).}
}
\value{
A data.frame with columns: \code{A_star}, \code{F_star}, \code{K_star},
\code{D_star}, \code{class}, \code{stable}, \code{rho_star},
\code{bifurcation}.
}
\examples{
\dontrun{
params <- as.list(default_params())
params$u_C <- 0
params$u_P <- 0
fps <- find_fixed_points(params, n_starts = 5)
print(fps)
}
}
