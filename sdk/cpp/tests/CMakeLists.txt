# Tests for SDV State Machine SDK

# Find Google Test
find_package(GTest REQUIRED)

# Test executable
add_executable(state_machine_tests
    test_state_machine.cpp
    test_transitions.cpp
    test_hierarchical.cpp
)

target_link_libraries(state_machine_tests
    PRIVATE
        sdv::state_machine
        GTest::gtest
        GTest::gtest_main
)

# Add tests
include(GoogleTest)
gtest_discover_tests(state_machine_tests)

# Enable testing
enable_testing()