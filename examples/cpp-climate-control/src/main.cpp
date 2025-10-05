#include "climate_control.hpp"
#include <glog/logging.h>
#include <memory>
#include <cstdlib>

int main(int argc, char* argv[]) {
    google::InitGoogleLogging(argv[0]);
    FLAGS_logtostderr = 1;

    std::string kuksa_url = "localhost:55555";
    if (const char* env_addr = std::getenv("KUKSA_ADDRESS")) {
        if (const char* env_port = std::getenv("KUKSA_PORT")) {
            kuksa_url = std::string(env_addr) + ":" + std::string(env_port);
        }
    }

    LOG(INFO) << "=== Remote Climate Control with VSS ===";
    LOG(INFO) << "Connecting to KUKSA at: " << kuksa_url;

    auto climate = std::make_unique<RemoteClimateControl>(kuksa_url);
    climate->run();

    return 0;
}
