#include "Statistics.h"

#include <algorithm>
#include <cmath>

namespace {

double percentile(const uint16_t* sortedValues, size_t count, double probability) {
  if (count == 0) {
    return NAN;
  }
  if (count == 1) {
    return sortedValues[0];
  }

  const double position = probability * static_cast<double>(count - 1);
  const size_t lower = static_cast<size_t>(floor(position));
  const size_t upper = static_cast<size_t>(ceil(position));
  const double fraction = position - static_cast<double>(lower);

  return static_cast<double>(sortedValues[lower]) +
         fraction * (static_cast<double>(sortedValues[upper]) -
                     static_cast<double>(sortedValues[lower]));
}

}  // namespace

StatisticsResult computeStatistics(uint16_t* values, size_t count) {
  StatisticsResult result;
  if (values == nullptr || count == 0) {
    return result;
  }

  std::sort(values, values + count);

  // Welford evita perdita di precisione nel calcolo della varianza.
  double runningMean = 0.0;
  double m2 = 0.0;
  for (size_t i = 0; i < count; ++i) {
    const double value = values[i];
    const double delta = value - runningMean;
    runningMean += delta / static_cast<double>(i + 1);
    const double delta2 = value - runningMean;
    m2 += delta * delta2;
  }

  result.available = true;
  result.mean = runningMean;
  result.median = percentile(values, count, 0.50);
  // Deviazione standard campionaria (denominatore n-1).
  result.standardDeviation = count > 1 ? sqrt(m2 / static_cast<double>(count - 1)) : 0.0;
  result.minimum = values[0];
  result.p05 = percentile(values, count, 0.05);
  result.p25 = percentile(values, count, 0.25);
  result.p75 = percentile(values, count, 0.75);
  result.p95 = percentile(values, count, 0.95);
  result.maximum = values[count - 1];
  return result;
}
