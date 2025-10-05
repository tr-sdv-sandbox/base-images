/**
 * Example Google Test using SDK testing library with YAML test definitions.
 *
 * This demonstrates the recommended testing approach:
 * - YAML defines declarative test steps (fixtures, inject, expect, wait)
 * - Google Test manages lifecycle (databroker, fixtures, your code)
 * - Your application runs in the test process (fully debuggable!)
 * - Set breakpoints, inspect variables, step through code
 *
 * To run:
 *   1. Build: cd build && cmake .. && make
 *   2. Run tests: ./climate_control_gtest
 *   3. Debug: Run in IDE debugger - breakpoints work!
 */

#include <sdv/testing/gtest_integration.hpp>
#include "../src/climate_control.hpp"  // Your application code
#include <memory>
#include <thread>

using namespace sdv::testing;

/**
 * Test fixture for Climate Control application.
 *
 * This manages the lifecycle:
 * 1. SetUp() starts: Docker (databroker + fixtures)
 * 2. StartTestSubject() starts your app natively (debuggable!)
 * 3. Tests run using YAML steps
 * 4. TearDown() cleans up everything
 */
class ClimateControlTest : public YamlTestFixture {
protected:
    void StartTestSubject() override {
        // Start your application code HERE
        // It runs in this process - fully debuggable!
        climate_control_ = std::make_unique<RemoteClimateControl>("localhost:55555");

        // Start in background thread
        climate_thread_ = std::thread([this]() {
            climate_control_->run();
        });

        // Give it time to connect and register
        std::this_thread::sleep_for(std::chrono::seconds(2));
    }

    void StopTestSubject() override {
        if (climate_control_) {
            climate_control_->stop();
        }

        if (climate_thread_.joinable()) {
            climate_thread_.join();
        }
    }

private:
    std::unique_ptr<RemoteClimateControl> climate_control_;
    std::thread climate_thread_;
};

/**
 * Run all test cases from YAML file.
 *
 * The YAML file defines:
 * - fixtures: Hardware simulators (battery sensor, etc)
 * - test_cases: Each with setup, steps, expectations
 *
 * Benefits:
 * - Declarative test definition (YAML)
 * - Your code runs natively (set breakpoints!)
 * - Same YAML works for CI (Docker-only mode)
 */
TEST_F(ClimateControlTest, RunAllYamlTests) {
    RunYamlTestSuite("simple_ac_test.yaml");
}

/**
 * Run a specific test case by name.
 *
 * Useful for:
 * - Debugging one failing test
 * - Faster iteration during development
 */
TEST_F(ClimateControlTest, ACActivation) {
    RunYamlTestCase("simple_ac_test.yaml", "AC Activation");
}

TEST_F(ClimateControlTest, ACDeactivation) {
    RunYamlTestCase("simple_ac_test.yaml", "AC Deactivation");
}

TEST_F(ClimateControlTest, LowBatteryProtection) {
    RunYamlTestCase("simple_ac_test.yaml", "Low Battery Protection");
}

/**
 * Advanced: Manual test using SDK APIs directly.
 *
 * Sometimes you need more control than YAML provides.
 * You can still use the SDK testing APIs directly.
 */
TEST_F(ClimateControlTest, ManualTest_HighBatteryEnablesAC) {
    auto kuksa = GetKuksaClient();

    // Inject high battery level
    kuksa->inject("Vehicle.Powertrain.TractionBattery.StateOfCharge.Current",
                  80.0f, sdv::vss::ActuatorMode::ACTUAL);

    // Request AC activation
    kuksa->inject("Vehicle.Cabin.HVAC.IsAirConditioningActive",
                  true, ActuatorMode::TARGET);

    // Wait for state machine transition
    std::this_thread::sleep_for(std::chrono::seconds(2));

    // Verify AC is actually on
    auto result = kuksa->get("Vehicle.Cabin.HVAC.IsAirConditioningActive");
    ASSERT_TRUE(result.has_value());

    bool ac_active = std::get<bool>(result.value());
    EXPECT_TRUE(ac_active) << "AC should be active with high battery";
}

int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    google::InitGoogleLogging(argv[0]);
    FLAGS_logtostderr = 1;

    return RUN_ALL_TESTS();
}
