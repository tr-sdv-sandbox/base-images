cmake_minimum_required(VERSION 3.16)
project(fixture-runner)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

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
        # Check local path first
        set(LOCAL_SDK_PATH "$ENV{HOME}/tr-sdv-sandbox/sdk-x/cpp")
        if(EXISTS "${LOCAL_SDK_PATH}/CMakeLists.txt")
            set(SDK_PATH "${LOCAL_SDK_PATH}")
            message(STATUS "Found local SDK at: ${SDK_PATH}")
        else()
            # Download from GitHub if not found locally
            message(STATUS "Local SDK not found, downloading from GitHub")
            include(FetchContent)
            FetchContent_Declare(
                sdk_x
                GIT_REPOSITORY https://github.com/tr-sdv-sandbox/sdk-x.git
                GIT_TAG main
                SOURCE_SUBDIR cpp
            )
            FetchContent_MakeAvailable(sdk_x)
            set(SDK_PATH "${sdk_x_SOURCE_DIR}/cpp")
        endif()
    endif()
    message(STATUS "Building SDK from source: ${SDK_PATH}")
    set(WITH_STATE_MACHINE OFF CACHE BOOL "Disable state machine" FORCE)
    set(BUILD_TESTS OFF CACHE BOOL "Disable SDK tests" FORCE)
    set(BUILD_EXAMPLES OFF CACHE BOOL "Disable SDK examples" FORCE)
    add_subdirectory(${SDK_PATH} ${CMAKE_CURRENT_BINARY_DIR}/sdk)
    set(SDK_INCLUDE_DIR ${SDK_PATH}/include)
endif()

# JSON library
include(FetchContent)
FetchContent_Declare(
    json
    URL https://github.com/nlohmann/json/releases/download/v3.11.2/json.tar.xz
)
FetchContent_MakeAvailable(json)

# Fixture runner executable
add_executable(fixture-runner
    src/fixture_runner.cpp
)

# Include directories
target_include_directories(fixture-runner PRIVATE
    ${SDK_INCLUDE_DIR}
)

# Link libraries
target_link_libraries(fixture-runner
    PRIVATE
        sdv_vss
        gRPC::grpc++
        protobuf::libprotobuf
        Threads::Threads
        glog
        nlohmann_json::nlohmann_json
)
