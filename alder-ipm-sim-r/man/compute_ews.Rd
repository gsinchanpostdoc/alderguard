\name{compute_ews}
\alias{compute_ews}
\title{Compute All Early Warning Signals}
\description{
Detrend a time series and compute rolling variance, autocorrelation,
and skewness in a single pass.
}
\usage{
compute_ews(ts, window = NULL, detrend = "gaussian")
}
\arguments{
\item{ts}{Numeric vector, the raw time series (e.g. annual beetle
  density).}
\item{window}{Integer window size for rolling statistics. If
  \code{NULL}, defaults to 50 percent of series length.}
\item{detrend}{Character detrending method (default \code{"gaussian"}).}
}
\value{
A data.frame with columns: \code{time} (integer index),
\code{variance}, \code{autocorrelation}, \code{skewness}.
}
\examples{
ews <- compute_ews(rnorm(50))
head(ews)
}
