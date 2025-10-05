/**
 * @file climate_control.cpp
 * @brief Remote Climate Control with VSS integration
 *
 * Integrates state machine with KUKSA VSS databroker using VSS SDK
 */

#include "climate_control.hpp"
#include <sdv/state_machine/state_machine.hpp>
#include <sdv/vss/vss.hpp>
#include <iostream>
#include <memory>
#include <thread>
#include <chrono>
#include <atomic>
#include <cstdlib>
#include <glog/logging.h>


using namespace sdv::vss;

// String representation for logging
std::string climate_state_name(ClimateState state) {
    switch (state) {
        case ClimateState::CLIMATE_OFF:             return "CLIMATE_OFF";
        case ClimateState::CLIMATE_ON:              return "CLIMATE_ON";
        case ClimateState::CLIMATE_OFF_LOW_BATTERY: return "CLIMATE_OFF_LOW_BATTERY";
        default:                                     return "UNKNOWN";
    }
}

RemoteClimateControl::RemoteClimateControl(const std::string& kuksa_url)
        : state_machine_("RemoteClimateControlStateMachine", ClimateState::CLIMATE_OFF),
          vss_client_(kuksa_url),
          ac_provider_(kuksa_url),  // Provider for AC actuator
          running_(true),
          // Define VSS signals
          battery_sensor_("Vehicle.Powertrain.TractionBattery.StateOfCharge.Current"),
          min_battery_attr_("Vehicle.Private.HVAC.MinimumBatteryLevelForAC") {

        state_machine_.set_state_name_function(climate_state_name);
        setup_states();
        setup_transitions();
    }

    bool RemoteClimateControl::connect() {
        LOG(INFO) << "Connecting to KUKSA databroker";
        if (!vss_client_.connect()) {
            LOG(ERROR) << "Failed to connect to VSS databroker";
            return false;
        }
        LOG(INFO) << "Connected to KUKSA databroker";

        // Connect AC provider
        if (!ac_provider_.connect()) {
            LOG(ERROR) << "Failed to connect AC provider";
            return false;
        }
        LOG(INFO) << "AC provider connected";

        // Set up actuation callback BEFORE providing actuators
        ac_provider_.on_actuate_request([this](const ActuationRequest& req) {
            if (req.path == "Vehicle.Cabin.HVAC.IsAirConditioningActive") {
                bool requested = std::get<bool>(req.value);
                LOG(INFO) << "Received AC actuation request: " << (requested ? "ON" : "OFF");
                handle_ac_request(requested);
            }
        });

        // Claim ownership of IsAirConditioningActive
        if (!ac_provider_.provide_actuators({"Vehicle.Cabin.HVAC.IsAirConditioningActive"})) {
            LOG(ERROR) << "Failed to provide AC actuator";
            return false;
        }
        LOG(INFO) << "AC provider registered for IsAirConditioningActive";

        // Start provider stream
        ac_provider_.start();
        LOG(INFO) << "AC provider stream started";

        // Read minimum battery level attribute (static value)
        auto min_battery = vss_client_.get(min_battery_attr_);
        if (min_battery.has_value()) {
            min_battery_level_ = static_cast<float>(min_battery.value());
            LOG(INFO) << "Minimum battery level: " << min_battery_level_ << "%";
        }

        return true;
    }

    void RemoteClimateControl::run() {
        if (!connect()) {
            LOG(ERROR) << "Failed to connect to KUKSA";
            return;
        }

        // Wait for required actuator providers to be ready
        wait_for_actuator_providers();

        LOG(INFO) << "Starting climate control monitoring...";
        subscribe_to_signals();

        // Keep running
        while (running_) {
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }
    }

    void RemoteClimateControl::wait_for_actuator_providers() {
        LOG(INFO) << "Waiting for hardware actuator providers to be ready...";

        // Try to actuate ACRequest - this will fail if provider doesn't exist
        // Keep retrying until provider is ready
        int attempts = 0;
        const int max_attempts = 30; // 30 seconds timeout
        Actuator<bool> ac_request("Vehicle.Private.HVAC.ACRequest");

        while (attempts < max_attempts) {
            if (vss_client_.set_target(ac_request, false)) {
                LOG(INFO) << "Hardware actuator providers are ready";
                return;
            }

            attempts++;
            if (attempts % 5 == 0) {
                LOG(INFO) << "Still waiting for hardware providers... (" << attempts << "s)";
            }
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }

        LOG(ERROR) << "Timeout waiting for hardware actuator providers";
    }

    void RemoteClimateControl::stop() {
        running_ = false;
        vss_client_.disconnect();
    }

    void RemoteClimateControl::setup_states() {
        state_machine_.define_state(ClimateState::CLIMATE_OFF)
            .on_entry([this]() {
                LOG(INFO) << "Climate control OFF";
            });

        state_machine_.define_state(ClimateState::CLIMATE_ON)
            .on_entry([this]() {
                LOG(INFO) << "Climate control ON";
            });

        state_machine_.define_state(ClimateState::CLIMATE_OFF_LOW_BATTERY)
            .on_entry([this]() {
                LOG(WARNING) << "Climate control OFF - low battery protection";
            });
    }

    void RemoteClimateControl::setup_transitions() {
        // Simple on/off transitions
        state_machine_.add_transition(
            ClimateState::CLIMATE_OFF, ClimateState::CLIMATE_ON, "climate_activate");

        state_machine_.add_transition(
            ClimateState::CLIMATE_ON, ClimateState::CLIMATE_OFF, "climate_deactivate");

        // Low battery protection
        state_machine_.add_transition(
            ClimateState::CLIMATE_ON, ClimateState::CLIMATE_OFF_LOW_BATTERY, "battery_low");

        // Battery recovery
        state_machine_.add_transition(
            ClimateState::CLIMATE_OFF_LOW_BATTERY, ClimateState::CLIMATE_ON, "battery_recovered");
    }

    void RemoteClimateControl::subscribe_to_signals() {
        LOG(INFO) << "Subscribing to VSS signals";

        // Publish initial AC state using standalone PublishValue RPC
        Sensor<bool> ac_state_sensor("Vehicle.Cabin.HVAC.IsAirConditioningActive");
        vss_client_.publish(ac_state_sensor, false);
        LOG(INFO) << "Published initial AC state: OFF";

        // Subscribe to hardware feedback (published by fixture provider as sensor value)
        Sensor<bool> ac_request_sensor("Vehicle.Private.HVAC.ACRequest");
        vss_client_.subscribe(ac_request_sensor, [this, ac_state_sensor](bool actual) {
            LOG(INFO) << "ACRequest from hardware: " << (actual ? "ON" : "OFF");

            // Track previous value to avoid loops
            static bool last_actual = false;
            if (actual != last_actual) {
                last_actual = actual;
                // Publish IsAirConditioningActive actual value using standalone PublishValue RPC
                vss_client_.publish(ac_state_sensor, actual);
            }
        });

        // Subscribe to battery level sensor
        vss_client_.subscribe(battery_sensor_, [this](float level) {
            battery_level_ = level;
            handle_battery_change(level);
        });

        // Start subscription processing after all subscriptions are registered
        vss_client_.start_subscriptions();

        LOG(INFO) << "Subscribed to all signals, waiting for updates...";
    }

    void RemoteClimateControl::handle_ac_request(bool requested) {
        Actuator<bool> ac_request("Vehicle.Private.HVAC.ACRequest");

        if (requested) {
            // Check battery before activating
            if (battery_level_ < min_battery_level_) {
                LOG(WARNING) << "AC request denied - battery too low ("
                           << battery_level_ << "% < " << min_battery_level_ << "%)";
                // Don't send command to hardware if battery is low
                return;
            }

            state_machine_.trigger("climate_activate");
            vss_client_.set_target(ac_request, true);
        } else {
            state_machine_.trigger("climate_deactivate");
            vss_client_.set_target(ac_request, false);
        }
    }

    void RemoteClimateControl::handle_battery_change(float level) {
        auto current_state = state_machine_.current_state();
        Actuator<bool> ac_request("Vehicle.Private.HVAC.ACRequest");

        if (current_state == ClimateState::CLIMATE_ON) {
            if (level < min_battery_level_) {
                LOG(WARNING) << "Battery dropped to " << level << "% - shutting down climate";
                state_machine_.trigger("battery_low");
                vss_client_.set_target(ac_request, false);
            }
        }
        else if (current_state == ClimateState::CLIMATE_OFF_LOW_BATTERY) {
            if (level >= min_battery_level_) {
                LOG(INFO) << "Battery recovered to " << level << "% - reactivating climate";
                state_machine_.trigger("battery_recovered");
                vss_client_.set_target(ac_request, true);
            }
        }
    }



