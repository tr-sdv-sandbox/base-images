# SDV Base Images and Test Framework

A comprehensive framework for building and testing Software-Defined Vehicle (SDV) user functions that interact with KUKSA.val databroker.

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Quick Start](#quick-start)
- [Base Images](#base-images)
- [Creating User Functions](#creating-user-functions)
- [Testing Framework](#testing-framework)
- [Examples](#examples)
- [CI/CD Integration](#cicd-integration)
- [Development Guidelines](#development-guidelines)

## Overview

This project provides:
- **Optimized base Docker images** for building SDV applications
- **Comprehensive test framework** for validating user functions
- **Example implementations** in Python and C++
- **CI/CD ready** test automation tools

### Key Features
- Layered architecture with separate build and runtime images
- Support for both Debian and Alpine Linux
- Minimal runtime images (39MB Alpine, 108MB Debian)
- YAML-based test specifications
- VSS signal injection and validation
- Requirements tracking

## Architecture

### Layered Image Architecture

```
┌─────────────────────┐     ┌─────────────────────┐
│   User Function 1   │     │   User Function 2   │
│  (Python/C++ App)   │     │  (Python/C++ App)   │
│ ┌─────────────────┐ │     │ ┌─────────────────┐ │
│ │ Runtime Base    │ │     │ │ Runtime Base    │ │ 
│ │ + KUKSA Client  │ │     │ │ + KUKSA Client  │ │
│ └─────────────────┘ │     │ └─────────────────┘ │
└──────────┬──────────┘     └──────────┬──────────┘
           │                           │
           │         gRPC              │
           └───────────┬───────────────┘
                       │
                ┌──────┴──────┐
                │   KUKSA     │
                │ Databroker  │
                └─────────────┘
```

### Test Architecture

```
┌─────────────────┐      ┌──────────────────┐      ┌─────────────────┐
│                 │      │                  │      │                 │
│   Test Runner   │─────▶│  Test Framework  │─────▶│   User Function │
│  (run-tests.sh) │      │    Container     │      │    Container    │
│                 │      │                  │      │                 │
└─────────────────┘      └────────┬─────────┘      └────────┬────────┘
                                  │                          │
                                  │  Signal Injection        │
                                  │  & Log Capture           │
                                  ▼                          ▼
                         ┌─────────────────┐        ┌─────────────────┐
                         │                 │        │                 │
                         │ KUKSA Databroker│◀──────▶│    Test Logs    │
                         │                 │        │                 │
                         └─────────────────┘        └─────────────────┘
```

### Dockerfile Organization

```
dockerfiles/
├── build/                           # Build environment images
│   ├── cpp-build.Dockerfile         # Debian-based C++ build environment
│   └── cpp-alpine-build.Dockerfile  # Alpine-based C++ build environment
└── runtime/                         # Runtime base images
    ├── cpp-runtime.Dockerfile       # Minimal Debian C++ runtime
    ├── cpp-alpine-runtime.Dockerfile # Minimal Alpine C++ runtime  
    └── python-runtime.Dockerfile     # Python runtime with KUKSA client
```

## Quick Start

### 1. Build Base Images

```bash
./build-base-images.sh
```

### 2. Build Example Applications

```bash
./build-examples.sh
```

### 3. Run Tests

Test a specific image:
```bash
./run-tests-v2.sh --image sdv-speed-monitor:latest --tests examples/python-speed-monitor/tests/
```

Test all examples:
```bash
./run-example-tests.sh
```

## Base Images

### Build Images (Development)
| Image | Size | Purpose |
|-------|------|---------|
| `sdv-cpp-build` | ~559MB | Debian-based C++ development with all tools |
| `sdv-cpp-alpine-build` | ~514MB | Alpine-based C++ development |

### Runtime Images (Production)
| Image | Size | Purpose |
|-------|------|---------|
| `sdv-cpp-runtime` | ~108MB | Minimal Debian runtime for C++ |
| `sdv-cpp-alpine-runtime` | ~39MB | Minimal Alpine runtime for C++ |
| `sdv-python-runtime` | ~176MB | Python runtime with KUKSA client |

## Creating User Functions

### C++ Application (Debian)

```dockerfile
# Build stage
FROM sdv-cpp-build:latest AS builder
COPY . /app/
WORKDIR /app
RUN mkdir -p build && cd build && \
    cmake -DCMAKE_BUILD_TYPE=Release .. && \
    make -j$(nproc) && \
    strip --strip-all myapp

# Runtime stage
FROM sdv-cpp-runtime:latest
COPY --from=builder /app/build/myapp /usr/local/bin/
ENV KUKSA_ADDRESS=kuksa-databroker \
    KUKSA_PORT=55555
CMD ["myapp"]
```

### C++ Application (Alpine - Minimal)

```dockerfile
# Build stage
FROM sdv-cpp-alpine-build:latest AS builder
USER root
COPY . /app/
WORKDIR /app
RUN mkdir -p build && cd build && \
    cmake -DCMAKE_BUILD_TYPE=Release .. && \
    make -j$(nproc) && \
    strip --strip-all myapp

# Runtime stage
FROM sdv-cpp-alpine-runtime:latest
COPY --from=builder /app/build/myapp /usr/local/bin/
CMD ["myapp"]
```

### Python Application

```dockerfile
FROM sdv-python-runtime:latest
USER root
COPY myapp.py requirements.txt /app/
RUN if [ -s /app/requirements.txt ]; then \
        pip install --no-cache-dir -r /app/requirements.txt; \
    fi
USER sdvuser
CMD ["python", "-u", "myapp.py"]
```

### CMake Optimization (C++)

```cmake
# Set default build type to Release
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Set optimization flags
set(CMAKE_CXX_FLAGS_RELEASE "-O2 -DNDEBUG")
set(CMAKE_CXX_FLAGS_DEBUG "-O0 -g")
```

## Testing Framework

### Test Runner Usage

```bash
Usage: ./run-tests-v2.sh [OPTIONS] --image <docker-image> --tests <path>

Required Arguments:
    -i, --image     Docker image to test
    -t, --tests     Path to test file or directory

Optional Arguments:
    -p, --pattern   File pattern when testing directory (default: "*.yaml")
    -e, --env       Environment variable (can be used multiple times)
    --tag           Run only tests with specific tag
    --fail-fast     Stop on first test failure
    -h, --help      Show this help message
```

### YAML Test Specification

```yaml
name: "Speed Monitor Test Suite"
description: "Test vehicle speed monitoring functionality"
requirements:
  - REQ-001: Monitor vehicle speed
  - REQ-002: Alert on high speed

setup:
  - action: set_signal
    signal: Vehicle.Speed
    value: 0

tests:
  - name: "Normal Speed Operation"
    description: "Test normal speed monitoring"
    requirements: ["REQ-001"]
    tags: ["smoke", "integration"]
    steps:
      - action: set_signal
        signal: Vehicle.Speed
        value: 50.0
      - action: wait
        duration: 2
      - action: check_log
        pattern: "Current speed: 50"
        timeout: 5

  - name: "High Speed Alert"
    description: "Test speed limit alerting"
    requirements: ["REQ-002"]
    tags: ["integration", "safety"]
    steps:
      - action: set_signal
        signal: Vehicle.Speed
        value: 150.0
      - action: wait
        duration: 1
      - action: check_log
        pattern: "HIGH SPEED WARNING"
        count: 1
        timeout: 3

teardown:
  - action: set_signal
    signal: Vehicle.Speed
    value: 0
```

### Test Actions

| Action | Purpose | Parameters |
|--------|---------|------------|
| `set_signal` | Inject VSS signal | `signal`, `value` |
| `wait` | Pause execution | `duration` (seconds) |
| `check_log` | Verify log output | `pattern`, `timeout`, `count` |
| `run_command` | Execute command | `command` |

## Examples

### Python Speed Monitor
Monitors vehicle speed and generates warnings for high speeds.

```bash
cd examples/python-speed-monitor
docker build -t sdv-speed-monitor:latest .
./run-tests-v2.sh -i sdv-speed-monitor:latest -t tests/
```

### C++ Engine Monitor
Monitors engine RPM and temperature with configurable thresholds.

```bash
cd examples/cpp-engine-monitor
# Debian version
docker build -t sdv-engine-monitor:latest .
# Alpine version (minimal)
docker build -f Dockerfile.alpine -t sdv-engine-monitor:alpine .
./run-tests-v2.sh -i sdv-engine-monitor:alpine -t tests/
```

## CI/CD Integration

### GitHub Actions

```yaml
name: SDV Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      
      - name: Build base images
        run: ./build-base-images.sh
      
      - name: Build application
        run: docker build -t myapp:latest .
      
      - name: Run tests
        run: ./run-tests-v2.sh -i myapp:latest -t tests/ --fail-fast
      
      - name: Upload test results
        if: always()
        uses: actions/upload-artifact@v2
        with:
          name: test-results
          path: test-results/
```

### GitLab CI

```yaml
stages:
  - build
  - test

variables:
  IMAGE_TAG: $CI_COMMIT_REF_SLUG

build:
  stage: build
  script:
    - ./build-base-images.sh
    - docker build -t myapp:$IMAGE_TAG .

test:
  stage: test
  script:
    - ./run-tests-v2.sh -i myapp:$IMAGE_TAG -t tests/ --fail-fast
  artifacts:
    when: always
    paths:
      - test-results/
    expire_in: 1 week
```

## Development Guidelines

### Best Practices

1. **Image Optimization**
   - Use Alpine-based images for production (39MB vs 108MB)
   - Always strip binaries in C++ builds
   - Use `-O2` optimization for release builds
   - Use multi-stage builds to minimize final image size

2. **Testing**
   - Write tests for all VSS signal interactions
   - Use tags to organize test suites
   - Include smoke tests for CI/CD pipelines
   - Track requirements coverage

3. **Security**
   - Run as non-root user (sdvuser)
   - Don't include build tools in runtime images
   - Keep base images updated
   - Scan images for vulnerabilities

4. **Maintainability**
   - Use the layered architecture for better caching
   - Document all environment variables
   - Include health checks in Dockerfiles
   - Follow consistent naming conventions

### Project Structure (External Projects)

```
my-sdv-function/
├── Dockerfile
├── Dockerfile.alpine       # Optional Alpine variant
├── src/                   # Application source code
├── tests/                 # Test specifications
│   ├── smoke.yaml        # Quick validation tests
│   ├── integration.yaml  # Full integration tests
│   └── regression.yaml   # Regression test suite
├── scripts/
│   └── run-tests.sh      # Wrapper for test framework
└── README.md
```

### Environment Variables

All base images include:
- `KUKSA_ADDRESS` - KUKSA databroker address (default: `kuksa-databroker`)
- `KUKSA_PORT` - KUKSA databroker port (default: `55555`)

Applications can add their own:
- `LOG_LEVEL` - Logging verbosity
- `UPDATE_INTERVAL` - Signal polling frequency
- Application-specific thresholds and limits


