/**
 * @file vss.hpp
 * @brief Main VSS SDK header - include this to use the VSS client and provider
 */

#pragma once

#include "types.hpp"
#include "client.hpp"
#include "provider.hpp"

/**
 * @brief SDV VSS Client SDK
 *
 * Example usage:
 *
 * @code
 * using namespace sdv::vss;
 *
 * // Create client
 * VSSClient client("databroker:55555");
 * client.connect();
 *
 * // Define signals
 * Actuator<bool> ac_signal("Vehicle.Cabin.HVAC.IsAirConditioningActive");
 * Sensor<float> battery_signal("Vehicle.Powertrain.TractionBattery.StateOfCharge.Current");
 *
 * // Subscribe to user commands (Target values)
 * client.on_target(ac_signal, [](bool requested) {
 *     LOG(INFO) << "User requested AC: " << (requested ? "ON" : "OFF");
 *     // Process the command...
 * });
 *
 * // Send commands to hardware (set Target)
 * client.set_target(ac_signal, true);
 *
 * // Observe hardware feedback (Actual values)
 * client.on_actual(ac_signal, [](bool actual) {
 *     LOG(INFO) << "Hardware reports AC is: " << (actual ? "ON" : "OFF");
 * });
 *
 * // Read sensor values
 * client.subscribe(battery_signal, [](float soc) {
 *     LOG(INFO) << "Battery: " << soc << "%";
 * });
 * @endcode
 */

namespace sdv {
    using namespace sdv::vss;
}
