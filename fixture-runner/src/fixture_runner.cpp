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
    ActuatorProvider provider_;
    VSSClient vss_client_;
    std::vector<ActuatorFixture> fixtures_;
    bool running_ = false;

public:
    FixtureRunner(const std::string& kuksa_address)
        : provider_(kuksa_address), vss_client_(kuksa_address) {
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

        // Connect to KUKSA with both provider and client
        if (!provider_.connect()) {
            LOG(ERROR) << "Failed to connect provider to KUKSA";
            return;
        }

        if (!vss_client_.connect()) {
            LOG(ERROR) << "Failed to connect VSS client to KUKSA";
            return;
        }

        // Collect all actuator paths to claim ownership
        std::vector<std::string> actuator_paths;
        for (const auto& fixture : fixtures_) {
            actuator_paths.push_back(fixture.target_signal);
            LOG(INFO) << "Fixture: " << fixture.name
                      << " will provide " << fixture.target_signal
                      << " with " << fixture.delay_seconds << "s delay";
        }

        // Claim ownership of all actuators
        if (!provider_.provide_actuators(actuator_paths)) {
            LOG(ERROR) << "Failed to claim actuator ownership";
            return;
        }

        // Register callback for actuation requests
        provider_.on_actuate_request([this](const ActuationRequest& req) {
            HandleActuation(req);
        });

        // Start provider stream
        provider_.start();

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
        provider_.stop();
        provider_.disconnect();
        LOG(INFO) << "All fixtures stopped";
    }

private:
    // Find fixture definition for a given path
    const ActuatorFixture* FindFixture(const std::string& path) const {
        for (const auto& fixture : fixtures_) {
            if (fixture.target_signal == path) {
                return &fixture;
            }
        }
        return nullptr;
    }

    // Handle actuation request from databroker
    void HandleActuation(const ActuationRequest& req) {
        // Find matching fixture
        const auto* fixture = FindFixture(req.path);
        if (!fixture) {
            LOG(WARNING) << "Received actuation for unknown path: " << req.path;
            return;
        }

        LOG(INFO) << "[" << fixture->name << "] Received actuation: "
                  << req.path << " (id=" << req.signal_id << ")";

        // Simulate hardware delay
        if (fixture->delay_seconds > 0) {
            std::this_thread::sleep_for(
                std::chrono::milliseconds(
                    static_cast<int>(fixture->delay_seconds * 1000)
                )
            );
        }

        // Publish actual value using standalone PublishValue RPC (not provider stream)
        std::visit([this, &req, fixture](auto&& value) {
            using T = std::decay_t<decltype(value)>;

            LOG(INFO) << "[" << fixture->name << "] Publishing actual value for " << req.path;

            // Use standalone PublishValue RPC
            if constexpr (std::is_same_v<T, bool>) {
                Sensor<bool> sensor(req.path);
                vss_client_.publish(sensor, value);
            } else if constexpr (std::is_same_v<T, int32_t>) {
                Sensor<int32_t> sensor(req.path);
                vss_client_.publish(sensor, value);
            } else if constexpr (std::is_same_v<T, float>) {
                Sensor<float> sensor(req.path);
                vss_client_.publish(sensor, value);
            }
        }, req.value);

        LOG(INFO) << "[" << fixture->name << "] Actuation complete";
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
