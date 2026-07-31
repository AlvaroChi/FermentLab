#pragma once

#include <Arduino.h>

struct StatisticsResult {
  bool available = false;
  double mean = NAN;
  double median = NAN;
  double standardDeviation = NAN;
  double minimum = NAN;
  double p05 = NAN;
  double p25 = NAN;
  double p75 = NAN;
  double p95 = NAN;
  double maximum = NAN;
};

// Ordina il buffer in-place e calcola statistiche campionarie.
// I percentili usano interpolazione lineare sulla posizione p*(n-1),
// equivalente al metodo predefinito di NumPy/Pandas.
StatisticsResult computeStatistics(uint16_t* values, size_t count);
