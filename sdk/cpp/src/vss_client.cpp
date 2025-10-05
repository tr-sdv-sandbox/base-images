/**
 * @file vss_client.cpp
 * @brief VSS Client Implementation for kuksa.val.v2
 */

#include <sdv/vss/client.hpp>
#include <grpcpp/grpcpp.h>
#include <glog/logging.h>
#include <map>
#include <mutex>
#include <thread>
#include <atomic>

// Include KUKSA v2 protobuf definitions
#include "kuksa/val/v2/types.pb.h"
#include "kuksa/val/v2/val.pb.h"
#include "kuksa/val/v2/val.grpc.pb.h"

using grpc::Channel;
using grpc::ClientContext;
using grpc::Status;
using kuksa::val::v2::VAL;
using kuksa::val::v2::GetValueRequest;
using kuksa::val::v2::GetValueResponse;
using kuksa::val::v2::PublishValueRequest;
using kuksa::val::v2::PublishValueResponse;
using kuksa::val::v2::ActuateRequest;
using kuksa::val::v2::ActuateResponse;
using kuksa::val::v2::SubscribeRequest;
using kuksa::val::v2::SubscribeResponse;
using kuksa::val::v2::SignalID;
using kuksa::val::v2::Datapoint;
// Note: Don't alias Value - conflicts with SDK's Value type
// using kuksa::val::v2::Value;

namespace sdv::vss {

// ============================================================================
// Internal implementation
// ============================================================================

class VSSClient::Impl {
public:
    explicit Impl(const std::string& address)
        : address_(address), connected_(false), running_(false) {
    }

    ~Impl() {
        disconnect();
    }

    bool connect() {
        LOG(INFO) << "Connecting to KUKSA databroker at: " << address_;

        auto channel = grpc::CreateChannel(address_, grpc::InsecureChannelCredentials());
        stub_ = VAL::NewStub(channel);

        // Test connection by checking if channel can connect
        // Use WaitForConnected with a short timeout to verify server is reachable
        auto deadline = std::chrono::system_clock::now() + std::chrono::seconds(2);
        if (!channel->WaitForConnected(deadline)) {
            LOG(ERROR) << "Failed to connect to KUKSA databroker at: " << address_;
            connected_ = false;
            return false;
        }

        // Double-check with a simple RPC call
        ClientContext context;
        context.set_deadline(std::chrono::system_clock::now() + std::chrono::seconds(2));
        GetValueRequest request;
        auto* signal_id = request.mutable_signal_id();
        signal_id->set_path("Vehicle.Speed"); // Try to get a common signal
        GetValueResponse response;

        Status status = stub_->GetValue(&context, request, &response);

        // Accept any response (even errors like NOT_FOUND) as proof server is alive
        // Only fail on connection-related errors
        if (!status.ok() &&
            (status.error_code() == grpc::StatusCode::UNAVAILABLE ||
             status.error_code() == grpc::StatusCode::DEADLINE_EXCEEDED)) {
            LOG(ERROR) << "KUKSA databroker not responding: " << status.error_message();
            connected_ = false;
            return false;
        }

        connected_ = true;
        LOG(INFO) << "Connected to KUKSA databroker";
        return true;
    }

    void disconnect() {
        if (running_) {
            running_ = false;
            if (subscription_thread_.joinable()) {
                subscription_thread_.join();
            }
        }
        connected_ = false;
    }

    bool is_connected() const {
        return connected_;
    }

    // Subscribe to a signal
    void subscribe(const std::string& path, std::function<void(const Datapoint&)> callback) {
        LOG(INFO) << "Registering subscription to " << path;

        std::lock_guard<std::mutex> lock(subscriptions_mutex_);
        subscriptions_[path] = callback;
    }

    // Start processing all subscriptions
    void start_subscriptions() {
        std::lock_guard<std::mutex> lock(subscriptions_mutex_);

        if (!connected_) {
            LOG(WARNING) << "Cannot start subscriptions - not connected";
            return;
        }

        if (running_) {
            LOG(INFO) << "Subscriptions already running";
            return;
        }

        LOG(INFO) << "Starting subscriptions for " << subscriptions_.size() << " signal(s)";

        start_subscription_thread();

        // Read initial values for all subscriptions
        for (const auto& [path, callback] : subscriptions_) {
            auto initial_value = get(path);
            if (initial_value.has_value()) {
                LOG(INFO) << "Got initial value for " << path;
                callback(initial_value.value());
            }
        }
    }

    // Get current value of a signal
    std::optional<Datapoint> get(const std::string& path) {
        if (!connected_) return std::nullopt;

        ClientContext context;
        GetValueRequest request;
        auto* signal_id = request.mutable_signal_id();
        signal_id->set_path(path);

        GetValueResponse response;
        Status status = stub_->GetValue(&context, request, &response);

        if (!status.ok()) {
            return std::nullopt;
        }

        return response.data_point();
    }

    // Publish a value (for sensors/actuator actual values)
    bool publish(const std::string& path, const Datapoint& value) {
        if (!connected_) return false;

        LOG(INFO) << "Publishing " << path;

        ClientContext context;
        PublishValueRequest request;
        auto* signal_id = request.mutable_signal_id();
        signal_id->set_path(path);
        *request.mutable_data_point() = value;

        PublishValueResponse response;
        Status status = stub_->PublishValue(&context, request, &response);

        if (!status.ok()) {
            LOG(ERROR) << "Failed to publish " << path << ": " << status.error_message();
            return false;
        }

        LOG(INFO) << "Successfully published " << path;
        return true;
    }

    // Actuate an actuator (send command)
    bool actuate(const std::string& path, const kuksa::val::v2::Value& value) {
        if (!connected_) return false;

        LOG(INFO) << "Actuating " << path;

        ClientContext context;
        ActuateRequest request;
        auto* signal_id = request.mutable_signal_id();
        signal_id->set_path(path);
        *request.mutable_value() = value;

        ActuateResponse response;
        Status status = stub_->Actuate(&context, request, &response);

        if (!status.ok()) {
            LOG(ERROR) << "Failed to actuate " << path << ": " << status.error_message();
            return false;
        }

        LOG(INFO) << "Successfully actuated " << path;
        return true;
    }

private:
    void start_subscription_thread() {
        running_ = true;
        subscription_thread_ = std::thread([this]() {
            subscribe_loop();
        });
    }

    void subscribe_loop() {
        LOG(INFO) << "Starting gRPC subscription stream for " << subscriptions_.size() << " entries";

        ClientContext context;
        SubscribeRequest request;

        // Add all subscriptions to request (v2 uses signal_paths not signal_ids)
        for (const auto& [path, callback] : subscriptions_) {
            request.add_signal_paths(path);
        }

        auto reader = stub_->Subscribe(&context, request);

        SubscribeResponse response;
        while (running_ && reader->Read(&response)) {
            LOG(INFO) << "Received " << response.entries_size() << " update(s) from subscription stream";

            // v2 returns map<string, Datapoint> entries
            for (const auto& [path, datapoint] : response.entries()) {
                handle_update(path, datapoint);
            }
        }

        Status status = reader->Finish();
        if (!status.ok() && running_) {
            LOG(ERROR) << "Subscription stream error: " << status.error_message();
        }
    }

    void handle_update(const std::string& path, const Datapoint& value) {
        std::lock_guard<std::mutex> lock(subscriptions_mutex_);

        auto it = subscriptions_.find(path);
        if (it != subscriptions_.end()) {
            LOG(INFO) << "Received update: " << path;
            it->second(value);
        }
    }

    std::string address_;
    std::unique_ptr<VAL::Stub> stub_;
    bool connected_;

    // Subscriptions
    std::mutex subscriptions_mutex_;
    std::map<std::string, std::function<void(const Datapoint&)>> subscriptions_;
    std::atomic<bool> running_;
    std::thread subscription_thread_;
};

// ============================================================================
// Public API implementation
// ============================================================================

VSSClient::VSSClient(const std::string& databroker_address)
    : impl_(std::make_unique<Impl>(databroker_address)) {
}

VSSClient::~VSSClient() = default;

bool VSSClient::connect() {
    return impl_->connect();
}

void VSSClient::disconnect() {
    impl_->disconnect();
}

bool VSSClient::is_connected() const {
    return impl_->is_connected();
}

void VSSClient::start_subscriptions() {
    impl_->start_subscriptions();
}

// ============================================================================
// Template specializations for sensor operations
// ============================================================================

template<>
void VSSClient::subscribe<bool>(const Sensor<bool>& sensor, typename Sensor<bool>::Callback callback) {
    impl_->subscribe(sensor.path(), [callback](const Datapoint& dp) {
        if (dp.value().has_bool_()) {
            callback(dp.value().bool_());
        }
    });
}

template<>
void VSSClient::subscribe<int32_t>(const Sensor<int32_t>& sensor, typename Sensor<int32_t>::Callback callback) {
    impl_->subscribe(sensor.path(), [callback](const Datapoint& dp) {
        if (dp.value().has_int32()) {
            callback(dp.value().int32());
        }
    });
}

template<>
void VSSClient::subscribe<float>(const Sensor<float>& sensor, typename Sensor<float>::Callback callback) {
    impl_->subscribe(sensor.path(), [callback](const Datapoint& dp) {
        if (dp.value().has_float_()) {
            callback(dp.value().float_());
        }
    });
}

template<>
std::optional<bool> VSSClient::get<bool>(const Sensor<bool>& sensor) {
    auto dp = impl_->get(sensor.path());
    if (dp.has_value() && dp->value().has_bool_()) {
        return dp->value().bool_();
    }
    return std::nullopt;
}

template<>
std::optional<int32_t> VSSClient::get<int32_t>(const Sensor<int32_t>& sensor) {
    auto dp = impl_->get(sensor.path());
    if (dp.has_value() && dp->value().has_int32()) {
        return dp->value().int32();
    }
    return std::nullopt;
}

template<>
std::optional<float> VSSClient::get<float>(const Sensor<float>& sensor) {
    auto dp = impl_->get(sensor.path());
    if (dp.has_value() && dp->value().has_float_()) {
        return dp->value().float_();
    }
    return std::nullopt;
}

// ============================================================================
// Template specializations for attribute operations
// ============================================================================

template<>
std::optional<int32_t> VSSClient::get<int32_t>(const Attribute<int32_t>& attribute) {
    auto dp = impl_->get(attribute.path());
    if (dp.has_value() && dp->value().has_int32()) {
        return dp->value().int32();
    }
    return std::nullopt;
}

// ============================================================================
// Template specializations for actuator operations
// ============================================================================

template<>
bool VSSClient::set_target<bool>(const Actuator<bool>& actuator, bool value) {
    kuksa::val::v2::Value proto_value;
    proto_value.set_bool_(value);
    return impl_->actuate(actuator.path(), proto_value);
}

template<>
bool VSSClient::set_target<int32_t>(const Actuator<int32_t>& actuator, int32_t value) {
    kuksa::val::v2::Value proto_value;
    proto_value.set_int32(value);
    return impl_->actuate(actuator.path(), proto_value);
}

template<>
bool VSSClient::set_target<float>(const Actuator<float>& actuator, float value) {
    kuksa::val::v2::Value proto_value;
    proto_value.set_float_(value);
    return impl_->actuate(actuator.path(), proto_value);
}

// ============================================================================
// Template specializations for publish operations (standalone PublishValue RPC)
// ============================================================================

template<>
bool VSSClient::publish<bool>(const Sensor<bool>& sensor, bool value) {
    Datapoint dp;
    dp.mutable_value()->set_bool_(value);
    return impl_->publish(sensor.path(), dp);
}

template<>
bool VSSClient::publish<int32_t>(const Sensor<int32_t>& sensor, int32_t value) {
    Datapoint dp;
    dp.mutable_value()->set_int32(value);
    return impl_->publish(sensor.path(), dp);
}

template<>
bool VSSClient::publish<float>(const Sensor<float>& sensor, float value) {
    Datapoint dp;
    dp.mutable_value()->set_float_(value);
    return impl_->publish(sensor.path(), dp);
}

} // namespace sdv::vss
