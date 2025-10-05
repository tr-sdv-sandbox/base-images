/**
 * Unit tests for the VSS/KUKSA Client SDK
 * Tests type safety, API correctness, and basic functionality (without requiring KUKSA connection)
 */

#include <sdv/vss/client.hpp>
#include <sdv/vss/provider.hpp>
#include <sdv/vss/types.hpp>
#include <sdv/vss/vss.hpp>
#include <gtest/gtest.h>
#include <glog/logging.h>
#include <thread>
#include <chrono>

using namespace sdv::vss;

// ============================================================================
// VSS Types Tests
// ============================================================================

TEST(VSSTypesTest, SensorTypeDefinition) {
    Sensor<float> speed("Vehicle.Speed");
    EXPECT_EQ(speed.path(), "Vehicle.Speed");
}

TEST(VSSTypesTest, ActuatorTypeDefinition) {
    Actuator<bool> ac("Vehicle.Cabin.HVAC.IsAirConditioningActive");
    EXPECT_EQ(ac.path(), "Vehicle.Cabin.HVAC.IsAirConditioningActive");
}

TEST(VSSTypesTest, AttributeTypeDefinition) {
    Attribute<std::string> vin("Vehicle.VehicleIdentification.VIN");
    EXPECT_EQ(vin.path(), "Vehicle.VehicleIdentification.VIN");
}

TEST(VSSTypesTest, SensorWithDifferentTypes) {
    Sensor<bool> bool_sensor("Vehicle.IsMoving");
    Sensor<int32_t> int_sensor("Vehicle.Passengers");
    Sensor<float> float_sensor("Vehicle.Speed");
    Sensor<double> double_sensor("Vehicle.Latitude");
    Sensor<std::string> string_sensor("Vehicle.Status");

    EXPECT_EQ(bool_sensor.path(), "Vehicle.IsMoving");
    EXPECT_EQ(int_sensor.path(), "Vehicle.Passengers");
    EXPECT_EQ(float_sensor.path(), "Vehicle.Speed");
    EXPECT_EQ(double_sensor.path(), "Vehicle.Latitude");
    EXPECT_EQ(string_sensor.path(), "Vehicle.Status");
}

TEST(VSSTypesTest, ValueVariant) {
    Value val;

    // Test bool
    val = true;
    EXPECT_TRUE(std::holds_alternative<bool>(val));
    EXPECT_TRUE(std::get<bool>(val));

    // Test int32_t
    val = int32_t(42);
    EXPECT_TRUE(std::holds_alternative<int32_t>(val));
    EXPECT_EQ(std::get<int32_t>(val), 42);

    // Test float
    val = 3.14f;
    EXPECT_TRUE(std::holds_alternative<float>(val));
    EXPECT_FLOAT_EQ(std::get<float>(val), 3.14f);

    // Test double
    val = 2.71828;
    EXPECT_TRUE(std::holds_alternative<double>(val));
    EXPECT_DOUBLE_EQ(std::get<double>(val), 2.71828);

    // Test string
    val = std::string("test");
    EXPECT_TRUE(std::holds_alternative<std::string>(val));
    EXPECT_EQ(std::get<std::string>(val), "test");
}

// ============================================================================
// VSSClient Tests (without actual connection)
// ============================================================================

TEST(VSSClientTest, Construction) {
    // Should not throw on construction
    EXPECT_NO_THROW({
        VSSClient client("localhost:55555");
    });
}

TEST(VSSClientTest, DisconnectBeforeConnect) {
    VSSClient client("localhost:55555");
    // Should not crash when disconnecting before connecting
    EXPECT_NO_THROW(client.disconnect());
    EXPECT_FALSE(client.is_connected());
}

TEST(VSSClientTest, InitiallyNotConnected) {
    VSSClient client("localhost:55555");
    EXPECT_FALSE(client.is_connected());
}

TEST(VSSClientTest, ConnectFailsWithoutDatabroker) {
    VSSClient client("localhost:12345"); // Port that's not running

    // Connection should fail gracefully
    bool connected = client.connect();
    EXPECT_FALSE(connected);
    EXPECT_FALSE(client.is_connected());
}

// ============================================================================
// ActuatorProvider Tests (without actual connection)
// ============================================================================

TEST(ActuatorProviderTest, Construction) {
    EXPECT_NO_THROW({
        ActuatorProvider provider("localhost:55555");
    });
}

TEST(ActuatorProviderTest, DisconnectBeforeConnect) {
    ActuatorProvider provider("localhost:55555");
    EXPECT_NO_THROW(provider.disconnect());
    EXPECT_FALSE(provider.is_connected());
}

TEST(ActuatorProviderTest, InitiallyNotConnected) {
    ActuatorProvider provider("localhost:55555");
    EXPECT_FALSE(provider.is_connected());
}

TEST(ActuatorProviderTest, ConnectFailsWithoutDatabroker) {
    ActuatorProvider provider("localhost:12345"); // Port that's not running

    bool connected = provider.connect();
    EXPECT_FALSE(connected);
    EXPECT_FALSE(provider.is_connected());
}

TEST(ActuatorProviderTest, CallbackRegistration) {
    ActuatorProvider provider("localhost:55555");

    bool callback_registered = false;

    EXPECT_NO_THROW({
        provider.on_actuate_request([&callback_registered](const ActuationRequest& req) {
            callback_registered = true;
        });
    });
}

TEST(ActuatorProviderTest, PublishActualWithoutConnection) {
    ActuatorProvider provider("localhost:55555");

    // Should not crash even if not connected
    EXPECT_NO_THROW({
        provider.publish_actual<bool>("Vehicle.AC.IsActive", true);
        provider.publish_actual<int32_t>("Vehicle.Speed", 50);
        provider.publish_actual<float>("Vehicle.Temperature", 22.5f);
        provider.publish_actual<double>("Vehicle.Latitude", 37.7749);
        provider.publish_actual<std::string>("Vehicle.Status", "OK");
    });
}

// ============================================================================
// VSS Namespace Tests (convenience helpers)
// ============================================================================

TEST(VSSNamespaceTest, CommonSensorDefinitions) {
    // Test that we can define common VSS signals
    auto speed = Sensor<float>("Vehicle.Speed");
    auto battery = Sensor<float>("Vehicle.Powertrain.TractionBattery.StateOfCharge.Current");
    auto door_open = Sensor<bool>("Vehicle.Body.Doors.Row1.DriverSide.IsOpen");

    EXPECT_EQ(speed.path(), "Vehicle.Speed");
    EXPECT_EQ(battery.path(), "Vehicle.Powertrain.TractionBattery.StateOfCharge.Current");
    EXPECT_EQ(door_open.path(), "Vehicle.Body.Doors.Row1.DriverSide.IsOpen");
}

TEST(VSSNamespaceTest, CommonActuatorDefinitions) {
    auto ac_active = Actuator<bool>("Vehicle.Cabin.HVAC.IsAirConditioningActive");
    auto target_temp = Actuator<float>("Vehicle.Cabin.HVAC.Station.Row1.Driver.Temperature");

    EXPECT_EQ(ac_active.path(), "Vehicle.Cabin.HVAC.IsAirConditioningActive");
    EXPECT_EQ(target_temp.path(), "Vehicle.Cabin.HVAC.Station.Row1.Driver.Temperature");
}

// ============================================================================
// ActuationRequest Tests
// ============================================================================

TEST(ActuationRequestTest, Construction) {
    ActuationRequest req;
    req.path = "Vehicle.AC.IsActive";
    req.signal_id = 123;
    req.value = true;

    EXPECT_EQ(req.path, "Vehicle.AC.IsActive");
    EXPECT_EQ(req.signal_id, 123);
    EXPECT_TRUE(std::holds_alternative<bool>(req.value));
    EXPECT_TRUE(std::get<bool>(req.value));
}

TEST(ActuationRequestTest, WithDifferentTypes) {
    ActuationRequest req1;
    req1.value = true;
    EXPECT_TRUE(std::holds_alternative<bool>(req1.value));

    ActuationRequest req2;
    req2.value = int32_t(42);
    EXPECT_TRUE(std::holds_alternative<int32_t>(req2.value));

    ActuationRequest req3;
    req3.value = 3.14f;
    EXPECT_TRUE(std::holds_alternative<float>(req3.value));

    ActuationRequest req4;
    req4.value = std::string("test");
    EXPECT_TRUE(std::holds_alternative<std::string>(req4.value));
}

// ============================================================================
// Integration-style Tests (API usage patterns)
// ============================================================================

TEST(VSSIntegrationTest, ClientSubscriptionPattern) {
    // This tests the API pattern, not actual functionality
    VSSClient client("localhost:55555");

    Sensor<float> speed("Vehicle.Speed");

    bool callback_called = false;
    float received_value = 0.0f;

    // Subscribe pattern should compile and not crash
    EXPECT_NO_THROW({
        client.subscribe(speed, [&](float value) {
            callback_called = true;
            received_value = value;
        });
    });
}

TEST(VSSIntegrationTest, ProviderPattern) {
    ActuatorProvider provider("localhost:55555");

    std::vector<std::string> actuators = {
        "Vehicle.Cabin.HVAC.IsAirConditioningActive",
        "Vehicle.Cabin.HVAC.Station.Row1.Driver.Temperature"
    };

    // Pattern should compile
    EXPECT_NO_THROW({
        provider.on_actuate_request([&](const ActuationRequest& req) {
            // Simulate handling actuation
            if (std::holds_alternative<bool>(req.value)) {
                provider.publish_actual<bool>(req.path, std::get<bool>(req.value));
            }
        });
    });
}

TEST(VSSIntegrationTest, TypeSafety) {
    VSSClient client("localhost:55555");

    // These should all compile with correct types
    Sensor<bool> bool_sensor("Vehicle.IsMoving");
    client.subscribe(bool_sensor, [](bool val) { /* callback */ });

    Sensor<float> float_sensor("Vehicle.Speed");
    client.subscribe(float_sensor, [](float val) { /* callback */ });

    Actuator<bool> bool_actuator("Vehicle.AC.Active");
    client.set_target(bool_actuator, true);

    Actuator<float> float_actuator("Vehicle.Temperature");
    client.set_target(float_actuator, 22.5f);
}

// ============================================================================
// Error Handling Tests
// ============================================================================

TEST(VSSErrorHandlingTest, InvalidAddress) {
    // Invalid address format
    EXPECT_NO_THROW({
        VSSClient client("invalid:address:format");
    });
}

TEST(VSSErrorHandlingTest, MultipleConnections) {
    VSSClient client("localhost:55555");

    // First connection attempt
    client.connect();

    // Second connection attempt should be safe
    EXPECT_NO_THROW(client.connect());
}

TEST(VSSErrorHandlingTest, MultipleDisconnects) {
    VSSClient client("localhost:55555");

    client.disconnect();
    // Second disconnect should be safe
    EXPECT_NO_THROW(client.disconnect());
}

int main(int argc, char **argv) {
    ::testing::InitGoogleTest(&argc, argv);
    google::InitGoogleLogging(argv[0]);
    FLAGS_logtostderr = 1;
    FLAGS_minloglevel = google::GLOG_WARNING; // Reduce log noise in tests

    return RUN_ALL_TESTS();
}
