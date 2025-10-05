/**
 * Integration tests for VSS Client and Provider with real KUKSA databroker
 * Requires Docker to be available and running
 */

#include <sdv/vss/client.hpp>
#include <sdv/vss/provider.hpp>
#include <sdv/vss/types.hpp>
#include <gtest/gtest.h>
#include <glog/logging.h>
#include <thread>
#include <chrono>
#include <atomic>
#include <cstdlib>

using namespace sdv::vss;

class VSSIntegrationTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Start KUKSA databroker in Docker
        LOG(INFO) << "Starting KUKSA databroker container...";

        // Stop any existing container
        std::system("docker rm -f kuksa-databroker-test 2>/dev/null");

        // Start databroker
        std::string cmd =
            "docker run -d --name kuksa-databroker-test "
            "-p 55555:55555 "
            "ghcr.io/eclipse-kuksa/kuksa-databroker:0.6.0 "
            "--insecure";

        int result = std::system(cmd.c_str());
        ASSERT_EQ(result, 0) << "Failed to start KUKSA databroker container";

        // Wait for databroker to be ready
        LOG(INFO) << "Waiting for databroker to be ready...";
        std::this_thread::sleep_for(std::chrono::seconds(3));

        // Verify it's running
        result = std::system("docker ps | grep kuksa-databroker-test > /dev/null");
        ASSERT_EQ(result, 0) << "KUKSA databroker container not running";

        LOG(INFO) << "KUKSA databroker ready";
    }

    void TearDown() override {
        LOG(INFO) << "Stopping KUKSA databroker container...";
        std::system("docker rm -f kuksa-databroker-test 2>/dev/null");
    }
};

// ============================================================================
// VSSClient Integration Tests
// ============================================================================

TEST_F(VSSIntegrationTest, ClientCanConnect) {
    VSSClient client("localhost:55555");

    bool connected = client.connect();
    EXPECT_TRUE(connected);
    EXPECT_TRUE(client.is_connected());

    client.disconnect();
    EXPECT_FALSE(client.is_connected());
}

TEST_F(VSSIntegrationTest, ClientCanPublishSensorValue) {
    VSSClient client("localhost:55555");
    ASSERT_TRUE(client.connect());

    Sensor<float> speed("Vehicle.Speed");

    // Publish a value
    bool published = client.publish(speed, 50.5f);
    EXPECT_TRUE(published);

    // Give it a moment to process
    std::this_thread::sleep_for(std::chrono::milliseconds(100));

    // Read it back
    auto value = client.get(speed);
    ASSERT_TRUE(value.has_value());
    EXPECT_FLOAT_EQ(value.value(), 50.5f);
}

TEST_F(VSSIntegrationTest, ClientCanSubscribeToSensorUpdates) {
    VSSClient client("localhost:55555");
    ASSERT_TRUE(client.connect());

    Sensor<float> battery("Vehicle.Powertrain.TractionBattery.StateOfCharge.Current");

    std::atomic<bool> callback_called{false};
    std::atomic<float> received_value{0.0f};

    // Subscribe
    client.subscribe(battery, [&](float value) {
        LOG(INFO) << "Received battery update: " << value;
        callback_called = true;
        received_value = value;
    });

    client.start_subscriptions();

    // Publish a value (simulating sensor update)
    client.publish(battery, 75.5f);

    // Wait for callback
    std::this_thread::sleep_for(std::chrono::milliseconds(500));

    EXPECT_TRUE(callback_called);
    EXPECT_FLOAT_EQ(received_value.load(), 75.5f);
}

TEST_F(VSSIntegrationTest, ClientCanSetActuatorTarget) {
    VSSClient client("localhost:55555");
    ASSERT_TRUE(client.connect());

    Actuator<bool> ac("Vehicle.Cabin.HVAC.IsAirConditioningActive");

    // This will fail without a provider, but should not crash
    bool result = client.set_target(ac, true);

    // The call itself should succeed (sent to databroker)
    // Whether actuation succeeds depends on provider being registered
    // We're just testing the API works
    EXPECT_NO_THROW(client.set_target(ac, true));
}

// ============================================================================
// ActuatorProvider Integration Tests
// ============================================================================

TEST_F(VSSIntegrationTest, ProviderCanConnect) {
    ActuatorProvider provider("localhost:55555");

    bool connected = provider.connect();
    EXPECT_TRUE(connected);
    EXPECT_TRUE(provider.is_connected());

    provider.disconnect();
    EXPECT_FALSE(provider.is_connected());
}

TEST_F(VSSIntegrationTest, ProviderCanRegisterActuators) {
    ActuatorProvider provider("localhost:55555");
    ASSERT_TRUE(provider.connect());

    std::vector<std::string> actuators = {
        "Vehicle.Cabin.HVAC.IsAirConditioningActive"
    };

    bool registered = provider.provide_actuators(actuators);
    EXPECT_TRUE(registered);
}

TEST_F(VSSIntegrationTest, ProviderReceivesActuationRequests) {
    // Create provider
    ActuatorProvider provider("localhost:55555");
    ASSERT_TRUE(provider.connect());

    // Register callback
    std::atomic<bool> actuation_received{false};
    std::atomic<bool> actuation_value{false};

    provider.on_actuate_request([&](const ActuationRequest& req) {
        LOG(INFO) << "Provider received actuation: " << req.path;
        actuation_received = true;
        if (std::holds_alternative<bool>(req.value)) {
            actuation_value = std::get<bool>(req.value);
            // Mirror the command back as actual value
            provider.publish_actual<bool>(req.path, actuation_value);
        }
    });

    // Register actuator
    std::vector<std::string> actuators = {
        "Vehicle.Cabin.HVAC.IsAirConditioningActive"
    };
    ASSERT_TRUE(provider.provide_actuators(actuators));

    // Start provider stream
    provider.start();

    // Give provider time to start
    std::this_thread::sleep_for(std::chrono::milliseconds(500));

    // Create client to send actuation command
    VSSClient client("localhost:55555");
    ASSERT_TRUE(client.connect());

    Actuator<bool> ac("Vehicle.Cabin.HVAC.IsAirConditioningActive");
    client.set_target(ac, true);

    // Wait for provider to receive actuation
    std::this_thread::sleep_for(std::chrono::seconds(2));

    EXPECT_TRUE(actuation_received);
    EXPECT_TRUE(actuation_value);

    provider.stop();
}

TEST_F(VSSIntegrationTest, ProviderPublishesActualValues) {
    ActuatorProvider provider("localhost:55555");
    ASSERT_TRUE(provider.connect());

    // Publish actual value
    provider.publish_actual<float>("Vehicle.Speed", 60.0f);

    // Give it time to process
    std::this_thread::sleep_for(std::chrono::milliseconds(200));

    // Read back with client
    VSSClient client("localhost:55555");
    ASSERT_TRUE(client.connect());

    Sensor<float> speed("Vehicle.Speed");
    auto value = client.get(speed);

    ASSERT_TRUE(value.has_value());
    EXPECT_FLOAT_EQ(value.value(), 60.0f);
}

// ============================================================================
// End-to-End Integration Tests
// ============================================================================

TEST_F(VSSIntegrationTest, EndToEnd_ClientProviderActuation) {
    // This test demonstrates the full KUKSA v2 provider pattern:
    // 1. Provider owns actuator
    // 2. Client sends actuation command
    // 3. Provider receives command via stream
    // 4. Provider publishes actual value
    // 5. Client observes actual value

    // Setup provider
    ActuatorProvider provider("localhost:55555");
    ASSERT_TRUE(provider.connect());

    std::atomic<bool> provider_received_command{false};

    provider.on_actuate_request([&](const ActuationRequest& req) {
        LOG(INFO) << "Provider executing actuation: " << req.path;
        provider_received_command = true;

        // Simulate hardware delay
        std::this_thread::sleep_for(std::chrono::milliseconds(100));

        // Publish actual value (mirror command)
        if (std::holds_alternative<bool>(req.value)) {
            provider.publish_actual<bool>(req.path, std::get<bool>(req.value));
        }
    });

    std::vector<std::string> actuators = {
        "Vehicle.Body.Doors.Row1.DriverSide.IsOpen"
    };
    ASSERT_TRUE(provider.provide_actuators(actuators));
    provider.start();

    std::this_thread::sleep_for(std::chrono::milliseconds(500));

    // Setup client with subscription
    VSSClient client("localhost:55555");
    ASSERT_TRUE(client.connect());

    Sensor<bool> door_actual("Vehicle.Body.Doors.Row1.DriverSide.IsOpen");
    std::atomic<bool> client_observed_change{false};
    std::atomic<bool> final_value{false};

    client.subscribe(door_actual, [&](bool value) {
        LOG(INFO) << "Client observed door change: " << value;
        client_observed_change = true;
        final_value = value;
    });

    client.start_subscriptions();

    // Send actuation command
    Actuator<bool> door_target("Vehicle.Body.Doors.Row1.DriverSide.IsOpen");
    bool sent = client.set_target(door_target, true);
    EXPECT_TRUE(sent);

    // Wait for full round-trip
    std::this_thread::sleep_for(std::chrono::seconds(2));

    // Verify
    EXPECT_TRUE(provider_received_command) << "Provider should receive actuation command";
    EXPECT_TRUE(client_observed_change) << "Client should observe actual value change";
    EXPECT_TRUE(final_value) << "Final value should match command";

    provider.stop();
}

TEST_F(VSSIntegrationTest, EndToEnd_MultipleSensors) {
    VSSClient client("localhost:55555");
    ASSERT_TRUE(client.connect());

    Sensor<float> speed("Vehicle.Speed");
    Sensor<float> battery("Vehicle.Powertrain.TractionBattery.StateOfCharge.Current");
    Sensor<bool> moving("Vehicle.IsMoving");

    std::atomic<int> updates_received{0};

    client.subscribe(speed, [&](float value) {
        LOG(INFO) << "Speed update: " << value;
        updates_received++;
    });

    client.subscribe(battery, [&](float value) {
        LOG(INFO) << "Battery update: " << value;
        updates_received++;
    });

    client.subscribe(moving, [&](bool value) {
        LOG(INFO) << "Moving update: " << value;
        updates_received++;
    });

    client.start_subscriptions();

    // Publish values
    client.publish(speed, 80.0f);
    client.publish(battery, 65.0f);
    client.publish(moving, true);

    // Wait for all updates
    std::this_thread::sleep_for(std::chrono::seconds(1));

    EXPECT_GE(updates_received, 3) << "Should receive all 3 updates";
}

int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    google::InitGoogleLogging(argv[0]);
    FLAGS_logtostderr = 1;
    FLAGS_minloglevel = google::GLOG_INFO;

    return RUN_ALL_TESTS();
}
