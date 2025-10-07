group "default" {
  targets = [
    "cpp-build",
    "cpp-alpine-build",
    "cpp-runtime",
    "cpp-alpine-runtime",
    "python-runtime"
  ]
}

target "cpp-build" {
  context = "."
  contexts = {
    src = "../sdk-x"
  }
  dockerfile = "dockerfiles/build/cpp-build.Dockerfile"
  tags = ["sdv-cpp-build:latest"]
}

target "cpp-alpine-build" {
  context = "."
  dockerfile = "dockerfiles/build/cpp-alpine-build.Dockerfile"
  tags = ["sdv-cpp-alpine-build:latest"]
}

target "cpp-runtime" {
  context = "."
  dockerfile = "dockerfiles/runtime/cpp-runtime.Dockerfile"
  tags = ["sdv-cpp-runtime:latest"]
}

target "cpp-alpine-runtime" {
  context = "."
  dockerfile = "dockerfiles/runtime/cpp-alpine-runtime.Dockerfile"
  tags = ["sdv-cpp-alpine-runtime:latest"]
}

target "python-runtime" {
  context = "."
  dockerfile = "dockerfiles/runtime/python-runtime.Dockerfile"
  tags = ["sdv-python-runtime:latest"]
}
