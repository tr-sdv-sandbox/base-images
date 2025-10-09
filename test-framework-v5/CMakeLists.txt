cmake_minimum_required(VERSION 3.14)
project(TestFrameworkV5)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find required packages
find_package(Threads REQUIRED)
find_package(gRPC REQUIRED)
find_package(Protobuf REQUIRED)
find_package(glog REQUIRED)
find_package(PkgConfig REQUIRED)
pkg_check_modules(YAMLCPP REQUIRED yaml-cpp)

# Include FetchContent for fetching SDK from GitHub if needed
include(FetchContent)

# Try to find SDK at local path first
set(SDK_LOCAL_PATH "$ENV{HOME}/tr-sdv-sandbox/sdk-x/cpp")

if(EXISTS "${SDK_LOCAL_PATH}")
    message(STATUS "Found SDK at: ${SDK_LOCAL_PATH}")
    add_subdirectory(${SDK_LOCAL_PATH} ${CMAKE_BINARY_DIR}/sdk-x-build)
else()
    message(STATUS "SDK not found locally, fetching from GitHub...")

    # Clone the SDK repository to build directory
    FetchContent_Declare(
        sdk-x
        GIT_REPOSITORY https://github.com/tr-sdv-sandbox/sdk-x
        GIT_TAG main
    )

    FetchContent_MakeAvailable(sdk-x)

    FetchContent_GetProperties(sdk-x SOURCE_DIR SDK_SOURCE_DIR)
    message(STATUS "SDK cloned to build directory: ${SDK_SOURCE_DIR}")
    add_subdirectory(${SDK_SOURCE_DIR}/cpp ${CMAKE_BINARY_DIR}/sdk-x-build)
endif()

# Source files - just main.cpp now, everything else is in SDK
set(SOURCES
    src/main.cpp
)

# Build executable
add_executable(test-framework-v5 ${SOURCES})

# Link libraries
target_link_libraries(test-framework-v5
    sdv::testing
    sdv::vss
    glog::glog
    ${YAMLCPP_LIBRARIES}
    gRPC::grpc++
    protobuf::libprotobuf
    Threads::Threads
)
