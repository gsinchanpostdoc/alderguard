\name{print_params}
\alias{print_params}
\title{Pretty-Print Parameter Table}
\description{
Print a formatted table of parameter names, symbols, values, bounds,
units, and modules to the console.
}
\usage{
print_params(params = NULL, category = NULL)
}
\arguments{
\item{params}{Named numeric vector of parameter values. If \code{NULL},
  uses defaults.}
\item{category}{Optional category filter (e.g. \code{"biotic_rate"},
  \code{"mortality"}).}
}
\value{
\code{NULL}, invisibly. Called for its side effect of printing to the
console.
}
\examples{
print_params()
print_params(category = "mortality")
}
