cmake_minimum_required(VERSION 3.16)
project(climate_control)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Set default build type to Release if not specified
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Set optimization flags
set(CMAKE_CXX_FLAGS_RELEASE "-O2 -DNDEBUG")
set(CMAKE_CXX_FLAGS_DEBUG "-O0 -g")

# Find required packages
find_package(Threads REQUIRED)
find_package(Protobuf REQUIRED)
find_package(gRPC CONFIG REQUIRED)

# SDK path - check if SDK is installed or needs to be built from source
if(EXISTS "/usr/local/lib/libsdv_vss.a")
    # Production mode - SDK is pre-installed (Docker)
    message(STATUS "Using pre-installed SDK from /usr/local")
    set(SDK_INCLUDE_DIR /usr/local/include)
else()
    # Development mode - build SDK from source
    if(NOT DEFINED SDK_PATH)
        set(SDK_PATH "${CMAKE_CURRENT_SOURCE_DIR}/../../sdk/cpp")
    endif()
    message(STATUS "Building SDK from source: ${SDK_PATH}")
    add_subdirectory(${SDK_PATH} ${CMAKE_CURRENT_BINARY_DIR}/sdk)
    set(SDK_INCLUDE_DIR ${SDK_PATH}/include)
endif()

# Create executable
add_executable(climate_control
        src/climate_control.hpp
        src/climate_control.cpp
        src/main.cpp
)

# Include directories
target_include_directories(climate_control PRIVATE
    ${SDK_INCLUDE_DIR}
)

# Link libraries
target_link_libraries(climate_control
    PRIVATE
        sdv_state_machine
        sdv_vss
        gRPC::grpc++
        protobuf::libprotobuf
        Threads::Threads
        glog
)

# Set runtime path
set_target_properties(climate_control PROPERTIES
    INSTALL_RPATH_USE_LINK_PATH TRUE
)

# Optional: Build tests if Google Test is available
find_package(GTest QUIET)
if(GTest_FOUND)
    message(STATUS "Google Test found - building tests")
    enable_testing()
    add_subdirectory(tests)
else()
    message(STATUS "Google Test not found - skipping tests")
endif()
