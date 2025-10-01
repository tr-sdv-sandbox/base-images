/**
 * @file climate_control.cpp
 * @brief Testable vehicle climate control state machine
 * 
 * This state machine responds to triggers that would normally come from VSS signals:
 * - temperature_changed: When cabin temperature vs desired temperature changes
 * - eco_mode_requested/eco_mode_cancelled: ECO mode toggle
 * - defrost_requested/defrost_cancelled: Defrost mode toggle
 * - power_on/power_off: System power control
 * 
 * The test framework can trigger these events based on VSS signal changes
 */

#include <sdv/state_machine/state_machine.hpp>
#include <glog/logging.h>
#include <memory>

// Climate control states
enum class ClimateState {
    Off,
    Idle,
    Cooling,
    Heating,
    Defrost,
    EcoMode,
    Error,
    _Count
};

// String representation for logging
std::string climate_state_name(ClimateState state) {
    switch (state) {
        case ClimateState::Off:      return "OFF";
        case ClimateState::Idle:     return "IDLE";
        case ClimateState::Cooling:  return "COOLING";
        case ClimateState::Heating:  return "HEATING";
        case ClimateState::Defrost:  return "DEFROST";
        case ClimateState::EcoMode:  return "ECO_MODE";
        case ClimateState::Error:    return "ERROR";
        default:                     return "UNKNOWN";
    }
}

class ClimateControl {
public:
    ClimateControl() : state_machine_("ClimateControl", ClimateState::Off) {
        // Set state name function for clear logging
        state_machine_.set_state_name_function(climate_state_name);
        
        // Define states
        state_machine_.define_state(ClimateState::Off)
            .on_entry([]() {
                LOG(INFO) << "Climate system powered off";
            });
        
        state_machine_.define_state(ClimateState::Idle)
            .on_entry([]() {
                LOG(INFO) << "Climate system idle - monitoring temperature";
            });
        
        state_machine_.define_state(ClimateState::Cooling)
            .on_entry([]() {
                LOG(INFO) << "Cooling mode activated";
            })
            .on_exit([]() {
                LOG(INFO) << "Cooling mode deactivated";
            });
        
        state_machine_.define_state(ClimateState::Heating)
            .on_entry([]() {
                LOG(INFO) << "Heating mode activated";
            })
            .on_exit([]() {
                LOG(INFO) << "Heating mode deactivated";
            });
        
        state_machine_.define_state(ClimateState::Defrost)
            .on_entry([]() {
                LOG(INFO) << "Defrost mode activated - max heat and fan";
            })
            .on_exit([]() {
                LOG(INFO) << "Defrost mode deactivated";
            });
        
        state_machine_.define_state(ClimateState::EcoMode)
            .on_entry([]() {
                LOG(INFO) << "ECO mode activated - reduced energy consumption";
            });
        
        state_machine_.define_state(ClimateState::Error)
            .on_entry([]() {
                LOG(ERROR) << "Climate control error - insufficient power";
            });
        
        // Define transitions
        setup_transitions();
    }
    
    // Public interface for test framework
    bool trigger(const std::string& event, const sdv::Context& context = {}) {
        return state_machine_.trigger(event, context);
    }
    
    std::string get_current_state() const {
        return state_machine_.current_state_name();
    }
    
    std::vector<std::string> get_available_triggers() const {
        return state_machine_.available_triggers();
    }
    
private:
    void setup_transitions() {
        // From Off state
        state_machine_.add_transition(ClimateState::Off, ClimateState::Idle, "power_on",
            [](const auto& ctx) {
                // Check if we have sufficient power (battery > 20% or engine running)
                auto battery_level = std::any_cast<float>(ctx.at("battery_level"));
                auto engine_running = std::any_cast<bool>(ctx.at("engine_running"));
                return battery_level > 20.0f || engine_running;
            });
        
        state_machine_.add_transition(ClimateState::Off, ClimateState::Error, "power_on",
            [](const auto& ctx) {
                // Go to error if insufficient power
                auto battery_level = std::any_cast<float>(ctx.at("battery_level"));
                auto engine_running = std::any_cast<bool>(ctx.at("engine_running"));
                return battery_level <= 20.0f && !engine_running;
            });
        
        // From Idle state
        state_machine_.add_transition(ClimateState::Idle, ClimateState::Cooling, "start_cooling",
            [](const auto& ctx) {
                // Only if temperature difference > 1°C
                auto temp_diff = std::any_cast<float>(ctx.at("temperature_difference"));
                return temp_diff > 1.0f;
            });
        
        state_machine_.add_transition(ClimateState::Idle, ClimateState::Heating, "start_heating",
            [](const auto& ctx) {
                auto temp_diff = std::any_cast<float>(ctx.at("temperature_difference"));
                return temp_diff < -1.0f;
            });
        
        state_machine_.add_transition(ClimateState::Idle, ClimateState::Defrost, "defrost_requested");
        state_machine_.add_transition(ClimateState::Idle, ClimateState::EcoMode, "eco_mode_requested");
        state_machine_.add_transition(ClimateState::Idle, ClimateState::Off, "power_off");
        
        // From Cooling state
        state_machine_.add_transition(ClimateState::Cooling, ClimateState::Idle, "temperature_reached");
        state_machine_.add_transition(ClimateState::Cooling, ClimateState::Defrost, "defrost_requested");
        state_machine_.add_transition(ClimateState::Cooling, ClimateState::EcoMode, "eco_mode_requested");
        state_machine_.add_transition(ClimateState::Cooling, ClimateState::Off, "power_off");
        
        // From Heating state  
        state_machine_.add_transition(ClimateState::Heating, ClimateState::Idle, "temperature_reached");
        state_machine_.add_transition(ClimateState::Heating, ClimateState::Defrost, "defrost_requested");
        state_machine_.add_transition(ClimateState::Heating, ClimateState::EcoMode, "eco_mode_requested");
        state_machine_.add_transition(ClimateState::Heating, ClimateState::Off, "power_off");
        
        // From Defrost state
        state_machine_.add_transition(ClimateState::Defrost, ClimateState::Idle, "defrost_cancelled");
        state_machine_.add_transition(ClimateState::Defrost, ClimateState::Off, "power_off");
        
        // From EcoMode state
        state_machine_.add_transition(ClimateState::EcoMode, ClimateState::Idle, "eco_mode_cancelled");
        state_machine_.add_transition(ClimateState::EcoMode, ClimateState::Defrost, "defrost_requested");
        state_machine_.add_transition(ClimateState::EcoMode, ClimateState::Off, "power_off");
        
        // From Error state
        state_machine_.add_transition(ClimateState::Error, ClimateState::Off, "error_cleared");
    }
    
    sdv::StateMachine<ClimateState> state_machine_;
};

// Make it accessible as a library
std::unique_ptr<ClimateControl> create_climate_control() {
    return std::make_unique<ClimateControl>();
}

// Simple test executable
int main(int argc, char* argv[]) {
    google::InitGoogleLogging(argv[0]);
    FLAGS_logtostderr = 1;
    
    LOG(INFO) << "=== Climate Control State Machine ===";
    LOG(INFO) << "This state machine is designed to be driven by a test framework";
    LOG(INFO) << "that monitors VSS signals and triggers appropriate events\n";
    
    auto climate = create_climate_control();
    
    LOG(INFO) << "Initial state: " << climate->get_current_state();
    LOG(INFO) << "Available triggers: ";
    for (const auto& trigger : climate->get_available_triggers()) {
        LOG(INFO) << "  - " << trigger;
    }
    
    // Example of how the test framework would use it:
    LOG(INFO) << "\nExample usage (normally driven by test framework):";
    
    // Power on with sufficient battery
    sdv::Context power_context;
    power_context["battery_level"] = std::any(80.0f);
    power_context["engine_running"] = std::any(true);
    climate->trigger("power_on", power_context);
    
    // Start cooling when temperature is too high
    sdv::Context temp_context;
    temp_context["temperature_difference"] = std::any(3.5f); // current - desired
    climate->trigger("start_cooling", temp_context);
    
    // Temperature reached
    climate->trigger("temperature_reached");
    
    // Request eco mode
    climate->trigger("eco_mode_requested");
    
    return 0;
}