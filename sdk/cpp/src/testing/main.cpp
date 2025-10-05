#include "sdv/testing/yaml_parser.hpp"
#include "sdv/testing/kuksa_client_wrapper.hpp"
#include "sdv/testing/test_runner.hpp"
#include <glog/logging.h>
#include <iostream>
#include <cstdlib>

using namespace sdv {
namespace testing;

int main(int argc, char* argv[]) {
    google::InitGoogleLogging(argv[0]);
    FLAGS_logtostderr = 1;
    FLAGS_colorlogtostderr = 1;

    if (argc < 2) {
        std::cerr << "Usage: " << argv[0] << " <test-suite.yaml> [--kuksa-url <url>]" << std::endl;
        return 1;
    }

    std::string test_file = argv[1];
    std::string kuksa_url = "databroker:55555";

    // Parse command line args
    for (int i = 2; i < argc; i++) {
        std::string arg = argv[i];
        if (arg == "--kuksa-url" && i + 1 < argc) {
            kuksa_url = argv[++i];
        }
    }

    // Check for environment variables
    if (const char* env_addr = std::getenv("KUKSA_ADDRESS")) {
        if (const char* env_port = std::getenv("KUKSA_PORT")) {
            kuksa_url = std::string(env_addr) + ":" + std::string(env_port);
        }
    }

    LOG(INFO) << "═══════════════════════════════════════════════════════════";
    LOG(INFO) << "Test Framework v5 - C++ with KUKSA v2 Support";
    LOG(INFO) << "═══════════════════════════════════════════════════════════";
    LOG(INFO) << "Test suite: " << test_file;
    LOG(INFO) << "KUKSA URL: " << kuksa_url;

    try {
        // Parse test suite
        YamlParser parser;
        TestSuite suite = parser.parse_file(test_file);

        // Connect to KUKSA
        auto client = std::make_shared<KuksaClientWrapper>(kuksa_url);
        if (!client->connect()) {
            LOG(ERROR) << "Failed to connect to KUKSA databroker";
            return 1;
        }

        // Run tests
        TestRunner runner(client);
        TestSuiteResult result = runner.run_suite(suite);

        // Cleanup
        client->disconnect();

        // Return exit code based on results
        if (result.failed > 0) {
            return 1;
        }

        return 0;

    } catch (const std::exception& e) {
        LOG(ERROR) << "Error: " << e.what();
        return 1;
    }
}
