\name{rolling_variance}
\alias{rolling_variance}
\title{Rolling Variance of a Time Series}
\description{
Compute the rolling-window variance of a time series. Rising variance
is a hallmark of critical slowing down.
}
\usage{
rolling_variance(ts, window = NULL)
}
\arguments{
\item{ts}{Numeric vector, the raw time series.}
\item{window}{Integer window size. If \code{NULL}, defaults to 50
  percent of series length.}
}
\value{
Numeric vector of rolling variance values (length =
\code{length(ts) - window + 1}).
}
\examples{
rv <- rolling_variance(rnorm(50), window = 10)
}
