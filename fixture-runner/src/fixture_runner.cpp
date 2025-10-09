/**
 * Hardware Fixture Runner - v2 Provider Pattern
 *
 * Simulates hardware responses to actuator commands using KUKSA v2 provider API.
 * Claims ownership of actuators and mirrors commanded values to actual values.
 */

#include <iostream>
#include <string>
#include <thread>
#include <chrono>
#include <map>
#include <memory>
#include <variant>
#include <nlohmann/json.hpp>
#include <fstream>
#include <sys/stat.h>
#include <glog/logging.h>
#include <sdv/vss/provider.hpp>
#include <sdv/vss/client.hpp>

using json = nlohmann::json;
using namespace sdv::vss;

struct ActuatorFixture {
    std::string name;
    std::string target_signal;
    std::string actual_signal;
    double delay_seconds;
};

class FixtureRunner {
private:
    std::unique_ptr<ActuatorProvider> provider_;
    std::string kuksa_address_;
    std::vector<ActuatorFixture> fixtures_;
    bool running_ = false;

public:
    FixtureRunner(const std::string& kuksa_address)
        : kuksa_address_(kuksa_address) {
    }

    void LoadFixtures(const std::string& config_file) {
        // Check if file exists and is a regular file
        struct stat st;
        if (stat(config_file.c_str(), &st) != 0) {
            std::cerr << "[ERROR] Config file does not exist: " << config_file << std::endl;
            return;
        }
        if (S_ISDIR(st.st_mode)) {
            std::cerr << "[ERROR] Config path is a directory, not a file: " << config_file << std::endl;
            return;
        }

        std::ifstream file(config_file);
        if (!file.is_open()) {
            std::cerr << "[ERROR] Failed to open fixture config: " << config_file << std::endl;
            return;
        }

        json config;
        file >> config;

        if (!config.contains("fixtures")) {
            std::cerr << "No fixtures defined in config" << std::endl;
            return;
        }

        for (const auto& fixture_json : config["fixtures"]) {
            if (fixture_json["type"] != "actuator_mirror") {
                std::cerr << "Unsupported fixture type: " << fixture_json["type"] << std::endl;
                continue;
            }

            ActuatorFixture fixture;
            fixture.name = fixture_json.value("name", "Unnamed Fixture");
            fixture.target_signal = fixture_json["target_signal"];
            fixture.actual_signal = fixture_json["actual_signal"];
            fixture.delay_seconds = fixture_json.value("delay", 0.1);

            fixtures_.push_back(fixture);
            std::cout << "[INFO] Loaded fixture: " << fixture.name << std::endl;
        }
    }

    void Start() {
        running_ = true;

        // Create provider (connects to KUKSA)
        auto provider_result = ActuatorProvider::create(kuksa_address_);
        if (!provider_result.ok()) {
            LOG(ERROR) << "Failed to create actuator provider: " << provider_result.status();
            return;
        }
        provider_ = std::move(*provider_result);

        // Register handlers for all fixtures using dynamic API
        // The provider will query metadata and validate types when start() is called
        for (const auto& fixture : fixtures_) {
            LOG(INFO) << "Fixture: " << fixture.name
                      << " will provide " << fixture.target_signal
                      << " with " << fixture.delay_seconds << "s delay";

            // Register handler using serve() - validation happens in start()
            // Use BOOL as placeholder - provider will use KUKSA's actual type
            provider_->serve(
                fixture.target_signal,
                ValueType::BOOL,  // Placeholder - provider validates against KUKSA
                [this, fixture](const Value& target, const DynamicActuatorOwnerHandle& handle) {
                    HandleActuation(target, fixture, handle);
                }
            );
        }

        // Start provider (validates all handlers atomically)
        auto start_status = provider_->start();
        if (!start_status.ok()) {
            LOG(ERROR) << "Failed to start provider: " << start_status;
            return;
        }

        LOG(INFO) << "Started provider for " << fixtures_.size() << " actuator(s)";
    }

    void Run() {
        // Keep running
        while (running_) {
            std::this_thread::sleep_for(std::chrono::seconds(1));
        }
    }

    void Stop() {
        running_ = false;
        if (provider_) {
            provider_->stop();
        }
        LOG(INFO) << "All fixtures stopped";
    }

private:
    // Handle actuation request from databroker
    void HandleActuation(const Value& target, const ActuatorFixture& fixture, const DynamicActuatorOwnerHandle& handle) {
        LOG(INFO) << "[" << fixture.name << "] Received actuation: "
                  << handle.path() << " (id=" << handle.id() << ")";

        // Simulate hardware delay
        if (fixture.delay_seconds > 0) {
            std::this_thread::sleep_for(
                std::chrono::milliseconds(
                    static_cast<int>(fixture.delay_seconds * 1000)
                )
            );
        }

        // Publish actual value using provider->publish_actual()
        // The handle already has type information, and the provider validates it
        LOG(INFO) << "[" << fixture.name << "] Publishing actual value for " << handle.path();

        auto status = provider_->publish_actual(handle, target);
        if (!status.ok()) {
            LOG(ERROR) << "[" << fixture.name << "] Failed to publish actual value: " << status;
            return;
        }

        LOG(INFO) << "[" << fixture.name << "] Actuation complete";
    }
};

int main(int argc, char* argv[]) {
    // Initialize glog
    google::InitGoogleLogging(argv[0]);
    FLAGS_logtostderr = 1;

    std::string kuksa_address = "databroker:55555";
    std::string config_file = "/app/fixtures.json";

    // Parse command line arguments
    for (int i = 1; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--kuksa" && i + 1 < argc) {
            kuksa_address = argv[++i];
        } else if (arg == "--config" && i + 1 < argc) {
            config_file = argv[++i];
        }
    }

    LOG(INFO) << "=== Hardware Fixture Runner ===";
    LOG(INFO) << "KUKSA address: " << kuksa_address;
    LOG(INFO) << "Config file: " << config_file;

    FixtureRunner runner(kuksa_address);
    runner.LoadFixtures(config_file);
    runner.Start();
    runner.Run();

    runner.Stop();
    return 0;
}
