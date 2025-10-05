/**
 * @file types.hpp
 * @brief VSS type definitions and abstractions
 */

#pragma once

#include <string>
#include <functional>
#include <variant>
#include <optional>
#include <cstdint>

namespace sdv::vss {

/**
 * @brief VSS value types
 */
using Value = std::variant<bool, int32_t, uint32_t, int64_t, uint64_t, float, double, std::string>;

/**
 * @brief Actuator mode - Target (command) or Actual (feedback)
 */
enum class ActuatorMode {
    TARGET,  // Command/request sent to hardware
    ACTUAL   // Actual hardware state/feedback
};

/**
 * @brief Base signal definition
 */
class Signal {
public:
    explicit Signal(std::string path) : path_(std::move(path)) {}
    virtual ~Signal() = default;

    const std::string& path() const { return path_; }

protected:
    std::string path_;
};

/**
 * @brief Actuator signal - has both Target and Actual values
 * Applications can:
 * - Subscribe to Target (receive commands)
 * - Set Target (send commands)
 * - Subscribe to Actual (observe hardware feedback)
 */
template<typename T>
class Actuator : public Signal {
public:
    explicit Actuator(std::string path) : Signal(std::move(path)) {}

    using TargetCallback = std::function<void(T value)>;
    using ActualCallback = std::function<void(T value)>;
};

/**
 * @brief Sensor signal - read-only, dynamic values
 * Examples: speed, temperature, battery level
 */
template<typename T>
class Sensor : public Signal {
public:
    explicit Sensor(std::string path) : Signal(std::move(path)) {}

    using Callback = std::function<void(T value)>;
};

/**
 * @brief Attribute signal - static/semi-static vehicle metadata
 * Examples: VIN, brand, model, door count, body type
 * These are typically set once and rarely (or never) change
 */
template<typename T>
class Attribute : public Signal {
public:
    explicit Attribute(std::string path) : Signal(std::move(path)) {}

    using Callback = std::function<void(T value)>;
};

} // namespace sdv::vss
