\name{classify_stability}
\alias{classify_stability}
\title{Classify Stability from Jacobian Eigenvalues}
\description{
Determine the stability classification and bifurcation type from
the eigenvalues of a 4x4 Jacobian matrix.
}
\usage{
classify_stability(jac)
}
\arguments{
\item{jac}{A 4x4 numeric Jacobian matrix.}
}
\value{
A named list with components:
\item{rho_star}{Spectral radius (maximum absolute eigenvalue).}
\item{stable}{Logical; \code{TRUE} if the spectral radius is less than 1.}
\item{bifurcation_type}{Character: \code{"stable"}, \code{"fold"},
  \code{"flip"}, or \code{"neimark_sacker"}.}
}
\examples{
jac <- matrix(c(0.5, 0.1, 0, 0,
                0.2, 0.3, 0, 0,
                0, 0, 0.9, 0,
                0.1, 0, 0, 0.4), nrow = 4, byrow = TRUE)
classify_stability(jac)
}
