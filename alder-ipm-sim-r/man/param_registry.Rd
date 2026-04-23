\name{param_registry}
\alias{param_registry}
\title{Full Parameter Registry for the Alnus-Beetle-Parasitoid-Bird Model}
\description{
Return the full parameter registry as a named list of lists. Each element
contains metadata fields: symbol, default, min, max, unit, description,
module, and category. Values are identical to the Python
\code{PARAM_REGISTRY}.
}
\usage{
param_registry()
}
\value{
A named list where each element is itself a list with fields
\code{symbol}, \code{default}, \code{min}, \code{max}, \code{unit},
\code{description}, \code{module}, and \code{category}.
}
\examples{
reg <- param_registry()
names(reg)
reg$beta$default
}
