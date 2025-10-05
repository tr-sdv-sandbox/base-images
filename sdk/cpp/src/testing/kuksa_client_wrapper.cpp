#include "sdv/testing/kuksa_client_wrapper.hpp"
#include <glog/logging.h>

namespace sdv {
namespace testing {

KuksaClientWrapper::KuksaClientWrapper(const std::string& kuksa_url)
    : kuksa_url_(kuksa_url),
      client_(std::make_unique<sdv::vss::VSSClient>(kuksa_url)) {
}

KuksaClientWrapper::~KuksaClientWrapper() {
    disconnect();
}

bool KuksaClientWrapper::connect() {
    LOG(INFO) << "Connecting to KUKSA at: " << kuksa_url_;
    return client_->connect();
}

void KuksaClientWrapper::disconnect() {
    if (client_) {
        client_->disconnect();
    }
}

template<typename T>
bool KuksaClientWrapper::inject_typed(const std::string& path, T value, ActuatorMode mode) {
    if (mode == ActuatorMode::TARGET) {
        // Use Actuate() RPC - works with v2 providers!
        sdv::vss::Actuator<T> actuator(path);
        LOG(INFO) << "Injecting " << path << " [TARGET] using Actuate() RPC";
        return client_->set_target(actuator, value);
    } else {
        // Use PublishValue() RPC - standalone publish
        sdv::vss::Sensor<T> sensor(path);
        LOG(INFO) << "Injecting " << path << " [VALUE] using PublishValue() RPC";
        return client_->publish(sensor, value);
    }
}

bool KuksaClientWrapper::inject(const std::string& path, const TestValue& value, ActuatorMode mode) {
    return std::visit([this, &path, mode](auto&& v) -> bool {
        using T = std::decay_t<decltype(v)>;

        if constexpr (std::is_same_v<T, bool>) {
            return inject_typed<bool>(path, v, mode);
        }
        else if constexpr (std::is_same_v<T, int32_t>) {
            return inject_typed<int32_t>(path, v, mode);
        }
        else if constexpr (std::is_same_v<T, float>) {
            return inject_typed<float>(path, v, mode);
        }
        else if constexpr (std::is_same_v<T, double>) {
            return inject_typed<float>(path, static_cast<float>(v), mode);
        }
        else if constexpr (std::is_same_v<T, std::string>) {
            LOG(ERROR) << "String values not yet supported";
            return false;
        }

        return false;
    }, value);
}

template<typename T>
std::optional<TestValue> KuksaClientWrapper::get_typed(const std::string& path) {
    sdv::vss::Sensor<T> sensor(path);
    auto result = client_->get(sensor);

    if (result.has_value()) {
        return TestValue(result.value());
    }

    return std::nullopt;
}

std::optional<TestValue> KuksaClientWrapper::get(const std::string& path) {
    // Try different types - start with most common

    // Try bool
    auto bool_result = get_typed<bool>(path);
    if (bool_result.has_value()) {
        return bool_result;
    }

    // Try float
    auto float_result = get_typed<float>(path);
    if (float_result.has_value()) {
        return float_result;
    }

    // Try int32
    auto int_result = get_typed<int32_t>(path);
    if (int_result.has_value()) {
        return int_result;
    }

    LOG(WARNING) << "Could not get value for " << path;
    return std::nullopt;
}


} // namespace testing
} // namespace sdv
