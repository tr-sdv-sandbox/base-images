#!/bin/bash
set -e

# Climate control functional tests with state machine verification
./run-tests-v4.sh --image sdv-cpp-climate-control:latest --tests examples/cpp-climate-control/tests/simple_ac_test.yaml

