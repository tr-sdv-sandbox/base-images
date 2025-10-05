# Tests for SDV SDK

# Find Google Test
find_package(GTest REQUIRED)

# ============================================================================
# State Machine Tests
# ============================================================================

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

# ============================================================================
# Testing Framework Tests
# ============================================================================

if(WITH_TESTING AND WITH_VSS)
    add_executable(testing_framework_tests
        test_testing_framework.cpp
    )

    target_link_libraries(testing_framework_tests
        PRIVATE
            sdv::testing
            sdv::vss
            GTest::gtest
            GTest::gtest_main
    )

    gtest_discover_tests(testing_framework_tests)
endif()

# ============================================================================
# VSS Client Tests (Unit Tests - No Docker Required)
# ============================================================================

if(WITH_VSS)
    add_executable(vss_client_tests
        test_vss_client.cpp
    )

    target_link_libraries(vss_client_tests
        PRIVATE
            sdv::vss
            GTest::gtest
            GTest::gtest_main
    )

    gtest_discover_tests(vss_client_tests)
endif()

# ============================================================================
# VSS Integration Tests (Requires Docker + KUKSA Databroker)
# ============================================================================

if(WITH_VSS)
    add_executable(vss_integration_tests
        test_vss_integration.cpp
    )

    target_link_libraries(vss_integration_tests
        PRIVATE
            sdv::vss
            GTest::gtest
            GTest::gtest_main
    )

    # Don't auto-discover these tests with CTest - they require Docker
    # Run manually with: ./tests/vss_integration_tests
    # Or add to CTest with: gtest_discover_tests(vss_integration_tests)
endif()

# ============================================================================
# Register Tests
# ============================================================================

include(GoogleTest)
gtest_discover_tests(state_machine_tests)

enable_testing()