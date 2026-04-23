\name{rolling_autocorrelation}
\alias{rolling_autocorrelation}
\title{Rolling Lag-k Autocorrelation}
\description{
Compute rolling-window lag-k autocorrelation of a time series.
Increasing AR(1) reflects growing system memory near a bifurcation.
}
\usage{
rolling_autocorrelation(ts, window = NULL, lag = 1)
}
\arguments{
\item{ts}{Numeric vector, the raw time series.}
\item{window}{Integer window size. If \code{NULL}, defaults to 50
  percent of series length.}
\item{lag}{Integer autocorrelation lag (default 1).}
}
\value{
Numeric vector of rolling autocorrelation values.
}
\examples{
rac <- rolling_autocorrelation(rnorm(50), window = 10, lag = 1)
}
