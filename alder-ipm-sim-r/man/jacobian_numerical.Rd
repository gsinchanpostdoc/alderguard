\name{jacobian_numerical}
\alias{jacobian_numerical}
\title{Numerical Jacobian of the Annual Map}
\description{
Compute the 4x4 Jacobian matrix of the annual map at a given state
using central finite differences.
}
\usage{
jacobian_numerical(params, state, eps = 1e-6)
}
\arguments{
\item{params}{Named list of parameters.}
\item{state}{Numeric vector \code{c(A, F, K, D)}.}
\item{eps}{Perturbation size (default 1e-6).}
}
\value{
A 4x4 numeric matrix (Jacobian).
}
\examples{
\dontrun{
params <- as.list(default_params())
params$u_C <- 0
params$u_P <- 0
jac <- jacobian_numerical(params, c(0.5, 0.1, 1.7, 0.3))
eigen(jac)$values
}
}
