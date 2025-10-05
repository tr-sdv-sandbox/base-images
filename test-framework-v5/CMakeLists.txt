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

# Use pre-installed SDK
set(SDK_INCLUDE_DIR "/usr/local/include")
set(SDK_LIB_DIR "/usr/local/lib")

find_library(SDV_VSS_LIB sdv_vss PATHS ${SDK_LIB_DIR} REQUIRED)
find_library(SDV_TESTING_LIB sdv_testing PATHS ${SDK_LIB_DIR} REQUIRED)

# Include directories
include_directories(
    ${SDK_INCLUDE_DIR}
)

# Source files - just main.cpp now, everything else is in SDK
set(SOURCES
    src/main.cpp
)

# Build executable
add_executable(test-framework-v5 ${SOURCES})

# Link libraries
target_link_libraries(test-framework-v5
    ${SDV_TESTING_LIB}
    ${SDV_VSS_LIB}
    glog::glog
    ${YAMLCPP_LIBRARIES}
    gRPC::grpc++
    protobuf::libprotobuf
    Threads::Threads
)
