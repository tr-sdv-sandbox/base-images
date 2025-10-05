/**
 * @file provider.hpp
 * @brief VSS Actuator Provider - Ownership and control of actuators
 */

#pragma once

#include <sdv/vss/types.hpp>
#include <string>
#include <vector>
#include <functional>
#include <memory>

namespace sdv::vss {

/**
 * @brief Actuation request from databroker
 *
 * When a consumer calls Actuate(), the databroker routes the request
 * to the registered provider via OpenProviderStream.
 */
struct ActuationRequest {
    std::string path;           // VSS signal path (e.g., "Vehicle.Private.HVAC.ACRequest")
    int32_t signal_id;          // Databroker's internal signal ID
    Value value;                // Commanded value (variant type from types.hpp)
};

/**
 * @brief Provider for actuators and sensors
 *
 * Implements the kuksa.val.v2 provider pattern using OpenProviderStream.
 * Providers own actuators/sensors and are responsible for:
 * - Claiming ownership via ProvideActuationRequest
 * - Receiving actuation commands via BatchActuateStreamRequest
 * - Publishing actual values via PublishValuesRequest
 *
 * Example usage:
 * @code
 * ActuatorProvider provider("databroker:55555");
 * provider.connect();
 *
 * // Claim ownership of actuators
 * provider.provide_actuators({
 *     "Vehicle.Private.HVAC.ACRequest",
 *     "Vehicle.Cabin.HVAC.Station.Row1.Driver.Temperature"
 * });
 *
 * // Handle actuation requests
 * provider.on_actuate_request([&](const ActuationRequest& req) {
 *     LOG(INFO) << "Actuating " << req.path;
 *
 *     // Simulate hardware delay
 *     std::this_thread::sleep_for(std::chrono::milliseconds(500));
 *
 *     // Publish actual value (mirror the command)
 *     provider.publish_actual(req.path, req.value);
 * });
 *
 * // Start provider stream (blocks or runs in background)
 * provider.start();
 * @endcode
 */
class ActuatorProvider {
public:
    /**
     * @brief Callback type for actuation requests
     *
     * Called when databroker sends an actuation command.
     * The callback should:
     * 1. Execute hardware command (or simulate it)
     * 2. Call publish_actual() with the achieved value
     */
    using ActuationCallback = std::function<void(const ActuationRequest&)>;

    /**
     * @brief Create actuator provider
     * @param databroker_address Address of KUKSA databroker (e.g., "databroker:55555")
     */
    explicit ActuatorProvider(const std::string& databroker_address);
    ~ActuatorProvider();

    // Prevent copying
    ActuatorProvider(const ActuatorProvider&) = delete;
    ActuatorProvider& operator=(const ActuatorProvider&) = delete;

    /**
     * @brief Connect to databroker
     * @return true if connection successful
     */
    bool connect();

    /**
     * @brief Disconnect from databroker and close provider stream
     */
    void disconnect();

    /**
     * @brief Check if connected
     */
    bool is_connected() const;

    /**
     * @brief Register actuators this provider owns
     *
     * Must be called before start(). Sends ProvideActuationRequest to claim ownership.
     * The databroker will reject the claim if another provider already owns any actuator.
     *
     * @param paths List of VSS paths to claim ownership
     * @return true if ownership claimed successfully
     */
    bool provide_actuators(const std::vector<std::string>& paths);

    /**
     * @brief Register callback for actuation requests
     *
     * The callback will be invoked on a background thread when the databroker
     * sends a BatchActuateStreamRequest (because a consumer called Actuate()).
     *
     * @param callback Function to call for each actuation request
     */
    void on_actuate_request(ActuationCallback callback);

    /**
     * @brief Publish actual value (after hardware executes)
     *
     * Sends PublishValuesRequest on the provider stream to report the
     * actual value achieved by the hardware.
     *
     * Thread-safe: Can be called from actuation callback or other threads.
     *
     * @param path VSS signal path
     * @param value Actual value achieved by hardware
     */
    template<typename T>
    void publish_actual(const std::string& path, T value);

    /**
     * @brief Publish actual value using variant type
     *
     * Internal method used by template specializations.
     *
     * @param path VSS signal path
     * @param value Actual value as variant
     */
    void publish_actual_value(const std::string& path, const Value& value);

    /**
     * @brief Start provider stream
     *
     * Opens OpenProviderStream bidirectional gRPC connection and:
     * 1. Sends ProvideActuationRequest to claim registered actuators
     * 2. Starts background thread to receive BatchActuateStreamRequest
     * 3. Processes actuation requests via registered callback
     *
     * This method starts background threads and returns immediately.
     * Call stop() to terminate the provider stream.
     */
    void start();

    /**
     * @brief Stop provider stream
     *
     * Closes the OpenProviderStream connection and stops background threads.
     * Blocks until all threads have exited.
     */
    void stop();

private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};

// Template specializations for common types
template<>
void ActuatorProvider::publish_actual<bool>(const std::string& path, bool value);

template<>
void ActuatorProvider::publish_actual<int32_t>(const std::string& path, int32_t value);

template<>
void ActuatorProvider::publish_actual<float>(const std::string& path, float value);

template<>
void ActuatorProvider::publish_actual<double>(const std::string& path, double value);

template<>
void ActuatorProvider::publish_actual<std::string>(const std::string& path, std::string value);

// Additional integer type specializations for compatibility
template<>
void ActuatorProvider::publish_actual<long>(const std::string& path, long value);

template<>
void ActuatorProvider::publish_actual<unsigned int>(const std::string& path, unsigned int value);

template<>
void ActuatorProvider::publish_actual<unsigned long>(const std::string& path, unsigned long value);

} // namespace sdv::vss
