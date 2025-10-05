cmake_minimum_required(VERSION 3.16)

# Find Google Test
find_package(GTest REQUIRED)

# Create test executable
add_executable(climate_control_gtest
    climate_control_gtest.cpp
    ${CMAKE_CURRENT_SOURCE_DIR}/../src/climate_control.cpp  # Include app source
)

# Include directories
target_include_directories(climate_control_gtest PRIVATE
    ${SDK_INCLUDE_DIR}
    ${CMAKE_CURRENT_SOURCE_DIR}/..
)

# Link libraries
target_link_libraries(climate_control_gtest
    PRIVATE
        sdv_testing
        sdv_state_machine
        sdv_vss
        GTest::gtest
        GTest::gtest_main
        gRPC::grpc++
        protobuf::libprotobuf
        Threads::Threads
        glog
)

# Copy test resources to build directory
configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/simple_ac_test.yaml
    ${CMAKE_BINARY_DIR}/tests/simple_ac_test.yaml
    COPYONLY
)

configure_file(
    ${CMAKE_CURRENT_SOURCE_DIR}/vss_extensions.json
    ${CMAKE_BINARY_DIR}/tests/vss_extensions.json
    COPYONLY
)

# Enable testing
enable_testing()
add_test(NAME ClimateControlTests COMMAND climate_control_gtest)
