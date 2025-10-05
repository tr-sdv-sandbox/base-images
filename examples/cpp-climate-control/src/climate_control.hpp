/**
 * @file climate_control.cpp
 * @brief Remote Climate Control with VSS integration
 *
 * Integrates state machine with KUKSA VSS databroker using VSS SDK
 */

#include <sdv/state_machine/state_machine.hpp>
#include <sdv/vss/vss.hpp>
#include <iostream>
#include <memory>
#include <thread>
#include <chrono>
#include <atomic>
#include <cstdlib>
#include <glog/logging.h>

#pragma once

using namespace sdv::vss;

// Simplified climate control states
enum class ClimateState {
    CLIMATE_OFF,
    CLIMATE_ON,
    CLIMATE_OFF_LOW_BATTERY,
    _Count
};

class RemoteClimateControl {
public:
    RemoteClimateControl(const std::string& kuksa_url);
    bool connect();
    void run();
    void wait_for_actuator_providers();
    void stop();
private:
    void setup_states();
    void setup_transitions();
    void subscribe_to_signals();
    void handle_ac_request(bool requested);
    void handle_battery_change(float level);

        // State machine
    sdv::StateMachine<ClimateState> state_machine_;

    // VSS Client
    VSSClient vss_client_;

    // AC Provider (we own IsAirConditioningActive)
    ActuatorProvider ac_provider_;

    // VSS Signal definitions
    Sensor<float> battery_sensor_;
    Attribute<int32_t> min_battery_attr_;

    // Application state
    std::atomic<bool> running_;
    float battery_level_ = 100.0f;
    float min_battery_level_ = 20.0f;
};
