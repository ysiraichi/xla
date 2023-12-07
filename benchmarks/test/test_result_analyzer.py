import argparse
import unittest
import numpy

from result_analyzer import ResultAnalyzer, parse_args

fns_whole = (numpy.min, numpy.median, numpy.max)
fns_skip_head = (numpy.mean, numpy.std)
fns_all = fns_whole + fns_skip_head


def apply(fn, data):
  return fn(data)


def apply_skip_head(fn, data):
  return fn(data[1:])


class TestResultAnalyzer(unittest.TestCase):

  def _key(self, fn, metric):
    return f"{fn.__name__}_{metric}"

  def _check(self, dataline, output, fns, metric, output_value_fn):
    for fn in fns:
      key = self._key(fn, metric)
      self.assertIn(key, output)
      self.assertEqual(output[key],
                       output_value_fn(fn, dataline["metrics"][metric]))

  def _test_calculate_metrics(self, dynamo):
    xla = "PJRT" if dynamo == "openxla" else ""

    dataline = {
        "experiment": {
            "xla": xla,
            "dynamo": dynamo,
        },
        "metrics": {
            "total_time": [1, 2, 3, 4],
            "single_value": [1],
            "trace_per_iter_time": [1, 2],
        }
    }

    r = ResultAnalyzer(parse_args())
    output = r.get_calculated_metrics({}, dataline)

    # Check that output has data for each metric, summarized by
    # each of its corresponding summary functions.

    # - total_time
    self._check(dataline, output, fns_whole, "total_time", apply)
    self._check(dataline, output, fns_skip_head, "total_time", apply_skip_head)

    # - single_value: since it has only one value, we only check it for
    #   fns_whole set of statistical functions
    self._check(dataline, output, fns_whole, "single_value", apply)

    # Check that there are is no mean and std for single-valued timings.
    for fn in fns_skip_head:
      self.assertNotIn(self._key(fn, "single_value"), output)

    return output, dataline

  def test_calculate_metrics_inductor(self):
    output, _ = self._test_calculate_metrics(dynamo="inductor")

    # There should be a dynamo_compile_time key, if it's not an XLA run.
    self.assertIn("dynamo_compile_time", output)

    # For all trace_per_iter_time summary data inside output, all of them
    # should be -1.
    for fn in fns_all:
      k = self._key(fn, "trace_per_iter_time")

      # It's ok not to have it in output, since it's not an XLA data anyway.
      if k in output:
        self.assertEqual(output[k], -1)

  def test_calculate_metrics_xla(self):
    output, dataline = self._test_calculate_metrics(dynamo="openxla")

    # There should be an xla_compile_time key.
    self.assertIn("xla_compile_time", output)

    # The trace_per_iter_time summary data should be populated.
    self._check(dataline, output, fns_whole, "trace_per_iter_time", apply)
    self._check(dataline, output, fns_skip_head, "trace_per_iter_time",
                apply_skip_head)


if __name__ == "__main__":
  unittest.main()
