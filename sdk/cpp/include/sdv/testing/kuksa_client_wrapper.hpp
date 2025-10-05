#pragma once

#include "test_models.hpp"
#include <sdv/vss/vss.hpp>
#include <string>
#include <optional>

namespace sdv {
namespace testing {

class KuksaClientWrapper {
public:
    explicit KuksaClientWrapper(const std::string& kuksa_url);
    ~KuksaClientWrapper();

    bool connect();
    void disconnect();

    // Inject value - uses correct v2 RPC based on mode
    bool inject(const std::string& path, const TestValue& value, ActuatorMode mode);

    // Get value for expectation
    std::optional<TestValue> get(const std::string& path);

private:
    std::string kuksa_url_;
    std::unique_ptr<vss::VSSClient> client_;

    // Template helpers for type-specific operations
    template<typename T>
    bool inject_typed(const std::string& path, T value, ActuatorMode mode);

    template<typename T>
    std::optional<TestValue> get_typed(const std::string& path);
};

} // namespace testing
} // namespace sdv
