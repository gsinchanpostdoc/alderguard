\name{detrend_ts}
\alias{detrend_ts}
\title{Remove a Slow Trend from a Time Series}
\description{
Detrend a time series before computing early warning signals. Supports
Gaussian kernel smoothing, linear regression, and LOESS.
}
\usage{
detrend_ts(ts, method = "gaussian", bandwidth = NULL)
}
\arguments{
\item{ts}{Numeric vector, the raw 1-D time series.}
\item{method}{Character: \code{"gaussian"} (default), \code{"linear"},
  or \code{"loess"}.}
\item{bandwidth}{Numeric kernel bandwidth for Gaussian smoothing.
  If \code{NULL}, defaults to \code{length(ts) / 8}.}
}
\value{
Numeric vector of residuals (same length as \code{ts}).
}
\examples{
residuals <- detrend_ts(sin(1:50) + rnorm(50, sd = 0.1), method = "gaussian")
}
