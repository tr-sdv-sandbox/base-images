/**
 * @file client.hpp
 * @brief VSS Client SDK - Clean abstraction over KUKSA Databroker
 */

#pragma once

#include "types.hpp"
#include <memory>
#include <string>
#include <functional>
#include <map>
#include <mutex>

namespace sdv::vss {

/**
 * @brief VSS Client for interacting with KUKSA Databroker
 *
 * This client provides a clean, type-safe API for:
 * - Subscribing to sensor values
 * - Subscribing to actuator Target values (commands)
 * - Setting actuator Target values (commands)
 * - Subscribing to actuator Actual values (hardware feedback)
 *
 * Note: Applications should NEVER set Actual values - that's the job
 * of real hardware or a separate simulator.
 */
class VSSClient {
public:
    /**
     * @brief Create VSS client
     * @param databroker_address Address of KUKSA databroker (e.g., "databroker:55555")
     */
    explicit VSSClient(const std::string& databroker_address);
    ~VSSClient();

    // Prevent copying
    VSSClient(const VSSClient&) = delete;
    VSSClient& operator=(const VSSClient&) = delete;

    /**
     * @brief Connect to databroker
     * @return true if connection successful
     */
    bool connect();

    /**
     * @brief Disconnect from databroker
     */
    void disconnect();

    /**
     * @brief Check if connected
     */
    bool is_connected() const;

    /**
     * @brief Start subscription processing
     *
     * Call this after registering all subscriptions to start receiving updates.
     * Subscriptions registered before calling this will all be included in a
     * single gRPC stream, avoiding race conditions.
     *
     * If not called explicitly, subscriptions will auto-start on the first
     * subscribe() call (for convenience, but may miss early subscriptions).
     */
    void start_subscriptions();

    // ========================================================================
    // SENSOR API - Read dynamic sensor values
    // ========================================================================

    /**
     * @brief Subscribe to sensor value changes
     * @param sensor Sensor definition
     * @param callback Called when sensor value changes
     */
    template<typename T>
    void subscribe(const Sensor<T>& sensor, typename Sensor<T>::Callback callback);

    /**
     * @brief Get current sensor value
     * @param sensor Sensor definition
     * @return Current value, or nullopt if not available
     */
    template<typename T>
    std::optional<T> get(const Sensor<T>& sensor);

    // ========================================================================
    // ATTRIBUTE API - Read static vehicle metadata
    // ========================================================================

    /**
     * @brief Get attribute value (static, can be cached)
     * Attributes are constant and don't change during runtime
     *
     * @param attribute Attribute definition
     * @return Current value, or nullopt if not available
     */
    template<typename T>
    std::optional<T> get(const Attribute<T>& attribute);

    // ========================================================================
    // ACTUATOR API - KUKSA v2 Provider Pattern
    // ========================================================================
    //
    // IMPORTANT: In KUKSA v2, actuators are owned by providers.
    //
    // If you want to OWN an actuator (receive commands):
    //   - Use ActuatorProvider class
    //   - Call provide_actuators() to claim ownership
    //   - Implement on_actuate_request() callback
    //   - Publish actual values via publish_actual()
    //
    // If you want to COMMAND an actuator:
    //   - Use set_target() to send actuation requests
    //   - The databroker will route to the provider
    //
    // If you want to OBSERVE published values:
    //   - Use subscribe() to monitor sensor values
    //   - Providers publish actual values which appear as sensor updates
    //
    // ========================================================================

    /**
     * @brief Send actuation command to an actuator (KUKSA v2 Actuate RPC)
     *
     * This sends an Actuate() RPC to the databroker, which routes the command
     * to the registered provider for this actuator.
     *
     * @param actuator Actuator definition
     * @param value Desired target value
     * @return true if actuation request was accepted by databroker
     */
    template<typename T>
    bool set_target(const Actuator<T>& actuator, T value);

    /**
     * @brief Publish a sensor value (standalone PublishValue RPC)
     *
     * This uses the standalone PublishValue() RPC to publish sensor values.
     * Use this when you need to publish values without using a provider stream.
     *
     * @param sensor Sensor definition
     * @param value Value to publish
     * @return true if publish was successful
     */
    template<typename T>
    bool publish(const Sensor<T>& sensor, T value);

private:
    class Impl;
    std::unique_ptr<Impl> impl_;
};

} // namespace sdv::vss
