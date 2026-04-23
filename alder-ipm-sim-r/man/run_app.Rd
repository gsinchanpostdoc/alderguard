\name{run_app}
\alias{run_app}
\title{Launch the AlderIPM-Sim Shiny Application}
\description{
Start the interactive Shiny web dashboard for simulating, fitting,
analysing early warnings, and evaluating management strategies.
}
\usage{
run_app(port = 3838, launch.browser = TRUE)
}
\arguments{
\item{port}{Integer port number (default 3838).}
\item{launch.browser}{Logical; open the app in the default browser
  (default \code{TRUE}).}
}
\value{
Called for its side effect of launching the Shiny app. Returns
invisibly.
}
\examples{
\dontrun{
run_app()
}
}
