/**
 * @file provider.cpp
 * @brief VSS Actuator Provider Implementation
 */

#include <sdv/vss/provider.hpp>
#include <grpcpp/grpcpp.h>
#include <glog/logging.h>
#include <map>
#include <mutex>
#include <thread>
#include <queue>
#include <condition_variable>
#include <atomic>
#include <future>

// Include KUKSA v2 protobuf definitions
#include "kuksa/val/v2/types.pb.h"
#include "kuksa/val/v2/val.pb.h"
#include "kuksa/val/v2/val.grpc.pb.h"

using grpc::Channel;
using grpc::ClientContext;
using grpc::ClientReaderWriter;
using grpc::Status;
using kuksa::val::v2::VAL;
using kuksa::val::v2::OpenProviderStreamRequest;
using kuksa::val::v2::OpenProviderStreamResponse;
using kuksa::val::v2::ProvideActuationRequest;
using kuksa::val::v2::PublishValuesRequest;
using kuksa::val::v2::BatchActuateStreamResponse;
using kuksa::val::v2::SignalID;
using kuksa::val::v2::ListMetadataRequest;
using kuksa::val::v2::ListMetadataResponse;

namespace sdv::vss {

// ============================================================================
// Internal implementation
// ============================================================================

class ActuatorProvider::Impl {
public:
    explicit Impl(const std::string& address)
        : address_(address), connected_(false), running_(false) {
    }

    ~Impl() {
        stop();
    }

    bool connect() {
        LOG(INFO) << "Provider connecting to KUKSA databroker at: " << address_;

        auto channel = grpc::CreateChannel(address_, grpc::InsecureChannelCredentials());
        stub_ = VAL::NewStub(channel);

        // Test connection by checking if channel can connect
        auto deadline = std::chrono::system_clock::now() + std::chrono::seconds(2);
        if (!channel->WaitForConnected(deadline)) {
            LOG(ERROR) << "Provider failed to connect to KUKSA databroker at: " << address_;
            connected_ = false;
            return false;
        }

        // Verify with a metadata call
        ClientContext context;
        context.set_deadline(std::chrono::system_clock::now() + std::chrono::seconds(2));
        ListMetadataRequest request;
        request.set_root("Vehicle"); // Query root metadata
        ListMetadataResponse response;

        Status status = stub_->ListMetadata(&context, request, &response);

        // Accept any response as proof server is alive
        if (!status.ok() &&
            (status.error_code() == grpc::StatusCode::UNAVAILABLE ||
             status.error_code() == grpc::StatusCode::DEADLINE_EXCEEDED)) {
            LOG(ERROR) << "KUKSA databroker not responding: " << status.error_message();
            connected_ = false;
            return false;
        }

        connected_ = true;
        LOG(INFO) << "Provider connected to KUKSA databroker";
        return true;
    }

    void disconnect() {
        stop();
        connected_ = false;
    }

    bool is_connected() const {
        return connected_;
    }

    int32_t query_signal_id(const std::string& path) {
        if (!connected_ || !stub_) {
            LOG(ERROR) << "Cannot query signal ID - not connected";
            return -1;
        }

        ClientContext context;
        ListMetadataRequest request;
        ListMetadataResponse response;

        // Query metadata for this specific path
        request.set_root(path);

        Status status = stub_->ListMetadata(&context, request, &response);

        if (!status.ok()) {
            LOG(ERROR) << "ListMetadata failed for " << path << ": " << status.error_message();
            return -1;
        }

        // Find matching metadata entry
        for (const auto& metadata : response.metadata()) {
            if (metadata.path() == path) {
                return metadata.id();
            }
        }

        LOG(WARNING) << "No metadata found for path: " << path;
        return -1;
    }

    bool provide_actuators(const std::vector<std::string>& paths) {
        LOG(INFO) << "Registering provider for " << paths.size() << " actuator(s)";

        std::lock_guard<std::mutex> lock(actuators_mutex_);

        // Query databroker for signal IDs
        for (const auto& path : paths) {
            actuator_paths_.push_back(path);

            // Get signal ID from databroker metadata
            int32_t signal_id = query_signal_id(path);
            if (signal_id >= 0) {
                id_to_path_[signal_id] = path;
                path_to_id_[path] = signal_id;
                LOG(INFO) << "  - " << path << " (id=" << signal_id << ")";
            } else {
                LOG(WARNING) << "  - " << path << " (id query failed)";
            }
        }

        return true;
    }

    void on_actuate_request(ActuationCallback callback) {
        actuation_callback_ = callback;
    }

    void publish_actual_value(const std::string& path, const Value& value) {
        std::lock_guard<std::mutex> lock(publish_mutex_);

        // Queue publish request
        PublishRequest req;
        req.path = path;
        req.value = value;
        publish_queue_.push(req);
        publish_cv_.notify_one();

        LOG(INFO) << "Queued publish for " << path;
    }

    void start() {
        if (running_) {
            LOG(WARNING) << "Provider already running";
            return;
        }

        if (!connected_) {
            LOG(ERROR) << "Cannot start provider - not connected";
            return;
        }

        running_ = true;

        // Start actuation worker thread
        actuation_worker_thread_ = std::thread([this]() {
            actuation_worker();
        });

        // Start provider stream in background thread
        stream_thread_ = std::thread([this]() {
            provider_stream_loop();
        });

        LOG(INFO) << "Provider started";
    }

    void stop() {
        if (!running_) {
            return;
        }

        LOG(INFO) << "Stopping provider...";
        running_ = false;

        // Wake up worker threads
        publish_cv_.notify_all();
        actuation_cv_.notify_all();

        // Wait for threads to finish
        if (actuation_worker_thread_.joinable()) {
            actuation_worker_thread_.join();
        }

        if (stream_thread_.joinable()) {
            stream_thread_.join();
        }

        LOG(INFO) << "Provider stopped";
    }

private:
    struct PublishRequest {
        std::string path;
        Value value;
    };

    void provider_stream_loop() {
        LOG(INFO) << "Opening provider stream";

        ClientContext context;
        auto stream = stub_->OpenProviderStream(&context);

        if (!stream) {
            LOG(ERROR) << "Failed to open provider stream";
            running_ = false;
            return;
        }

        // Create a new promise/future for this stream
        provide_response_promise_ = std::promise<bool>();
        provide_response_future_ = provide_response_promise_.get_future();

        // Start receive thread FIRST (it will handle the ProvideActuationResponse)
        std::thread read_thread([this, &stream]() {
            receive_loop(stream.get());
        });

        std::thread write_thread([this, &stream]() {
            publish_loop(stream.get());
        });

        // Send ProvideActuationRequest (response will be handled by receive_loop)
        if (!send_provide_actuation_async(stream.get())) {
            LOG(ERROR) << "Failed to send provide actuation request";
            running_ = false;
            publish_cv_.notify_all();
            actuation_cv_.notify_all();
            read_thread.join();
            write_thread.join();
            return;
        }

        // Wait for ownership confirmation from receive_loop (with timeout)
        if (provide_response_future_.wait_for(std::chrono::seconds(5)) == std::future_status::timeout) {
            LOG(ERROR) << "Timeout waiting for ownership confirmation";
            running_ = false;
            publish_cv_.notify_all();
            actuation_cv_.notify_all();
            read_thread.join();
            write_thread.join();
            return;
        }

        if (!provide_response_future_.get()) {
            LOG(ERROR) << "Failed to get ownership confirmation";
            running_ = false;
            publish_cv_.notify_all();
            actuation_cv_.notify_all();
            read_thread.join();
            write_thread.join();
            return;
        }

        LOG(INFO) << "Actuator ownership confirmed";

        // Wait for threads
        read_thread.join();
        write_thread.join();

        // Close stream
        stream->WritesDone();
        Status status = stream->Finish();

        if (!status.ok()) {
            LOG(ERROR) << "Provider stream finished with error: " << status.error_message()
                      << " (code: " << status.error_code() << ")";
        } else {
            LOG(INFO) << "Provider stream finished successfully";
        }
    }

    bool send_provide_actuation_async(ClientReaderWriter<OpenProviderStreamRequest, OpenProviderStreamResponse>* stream) {
        std::lock_guard<std::mutex> lock(actuators_mutex_);

        OpenProviderStreamRequest request;
        auto* provide_req = request.mutable_provide_actuation_request();

        for (const auto& path : actuator_paths_) {
            auto* signal_id = provide_req->add_actuator_identifiers();
            signal_id->set_path(path);
        }

        LOG(INFO) << "Sending ProvideActuationRequest for " << actuator_paths_.size() << " actuator(s)";

        std::lock_guard<std::mutex> write_lock(stream_write_mutex_);
        if (!stream->Write(request)) {
            LOG(ERROR) << "Failed to send ProvideActuationRequest";
            return false;
        }

        // Response will be handled by receive_loop
        return true;
    }

    void receive_loop(ClientReaderWriter<OpenProviderStreamRequest, OpenProviderStreamResponse>* stream) {
        LOG(INFO) << "Provider receive loop started";

        OpenProviderStreamResponse response;
        while (running_ && stream->Read(&response)) {
            if (response.has_provide_actuation_response()) {
                // Ownership confirmation
                LOG(INFO) << "Received ProvideActuationResponse - ownership granted";
                provide_response_promise_.set_value(true);
            } else if (response.has_batch_actuate_stream_request()) {
                handle_actuation_request(response.batch_actuate_stream_request(), stream);
            } else if (response.has_publish_values_response()) {
                // Acknowledgement of published value (only on error)
                auto& pub_response = response.publish_values_response();
                for (const auto& [signal_id, error] : pub_response.status()) {
                    if (error.code() != 0) {
                        LOG(WARNING) << "Publish error for signal " << signal_id << ": " << error.message();
                    }
                }
            } else {
                LOG(WARNING) << "Received unexpected response type";
            }
        }

        // If we haven't set the promise yet, set it to false
        try {
            provide_response_promise_.set_value(false);
        } catch (const std::future_error&) {
            // Already set, ignore
        }

        if (running_) {
            LOG(WARNING) << "Provider receive loop ended unexpectedly (stream closed by server)";
        } else {
            LOG(INFO) << "Provider receive loop ended normally";
        }
    }

    void handle_actuation_request(
        const kuksa::val::v2::BatchActuateStreamRequest& batch_req,
        ClientReaderWriter<OpenProviderStreamRequest, OpenProviderStreamResponse>* stream) {

        LOG(INFO) << "Received BatchActuateStreamRequest with " << batch_req.actuate_requests_size() << " actuation(s)";

        // Process each actuation
        for (const auto& actuate_req : batch_req.actuate_requests()) {
            // Extract signal ID and value from ActuateRequest
            const auto& signal_id_msg = actuate_req.signal_id();
            int32_t signal_id = 0;

            // Get signal ID - prefer id field, fallback to path lookup
            if (signal_id_msg.has_id()) {
                signal_id = signal_id_msg.id();
            } else if (signal_id_msg.has_path()) {
                signal_id = get_signal_id_for_path(signal_id_msg.path());
            }

            const auto& value = actuate_req.value();
            // Find path for this signal ID
            std::string path = find_path_for_id(signal_id);
            if (path.empty()) {
                LOG(WARNING) << "Unknown signal ID: " << signal_id;
                continue;
            }

            LOG(INFO) << "Actuation request for " << path << " (id=" << signal_id << ")";

            // Convert proto Value to variant Value
            Value cpp_value = convert_from_proto(value);

            // Send acknowledgement IMMEDIATELY (before callback)
            // This prevents stream timeout if callback blocks
            send_actuation_ack(stream, signal_id);

            // Create actuation request
            ActuationRequest req{
                .path = path,
                .signal_id = signal_id,
                .value = cpp_value
            };

            // Queue request for async processing
            // Each actuator has its own worker thread
            if (actuation_callback_) {
                queue_actuation_request(req);
            }
        }
    }

    void send_actuation_ack(ClientReaderWriter<OpenProviderStreamRequest, OpenProviderStreamResponse>* stream, int32_t signal_id) {
        OpenProviderStreamRequest request;
        auto* ack = request.mutable_batch_actuate_stream_response();

        // Empty error map means success
        // If there was an error, we would add it: (*ack->mutable_results())[signal_id] = error;

        std::lock_guard<std::mutex> write_lock(stream_write_mutex_);
        if (!stream->Write(request)) {
            LOG(ERROR) << "Failed to send BatchActuateStreamResponse";
        }
    }

    void publish_loop(ClientReaderWriter<OpenProviderStreamRequest, OpenProviderStreamResponse>* stream) {
        LOG(INFO) << "Provider publish loop started";

        while (running_) {
            std::unique_lock<std::mutex> lock(publish_mutex_);

            // Wait for publish requests
            publish_cv_.wait(lock, [this]() {
                return !publish_queue_.empty() || !running_;
            });

            if (!running_) {
                break;
            }

            // Process all queued publishes
            while (!publish_queue_.empty()) {
                auto req = publish_queue_.front();
                publish_queue_.pop();

                lock.unlock();
                send_publish_value(stream, req.path, req.value);
                lock.lock();
            }
        }

        LOG(INFO) << "Provider publish loop ended";
    }

    void send_publish_value(ClientReaderWriter<OpenProviderStreamRequest, OpenProviderStreamResponse>* stream,
                           const std::string& path, const Value& value) {

        OpenProviderStreamRequest request;
        auto* publish_req = request.mutable_publish_values_request();

        // Set request ID (can be 0 for simple cases)
        publish_req->set_request_id(0);

        // Get signal ID for path
        int32_t signal_id = get_signal_id_for_path(path);
        if (signal_id < 0) {
            LOG(ERROR) << "Cannot publish " << path << " - no signal ID";
            return;
        }

        // Convert variant Value to proto Value
        kuksa::val::v2::Value proto_value = convert_to_proto(value);

        // Create datapoint
        kuksa::val::v2::Datapoint dp;
        *dp.mutable_value() = proto_value;

        // Add to publish request (using signal ID as key)
        (*publish_req->mutable_data_points())[signal_id] = dp;

        LOG(INFO) << "Publishing value for " << path << " (id=" << signal_id << ")";

        {
            std::lock_guard<std::mutex> write_lock(stream_write_mutex_);
            LOG(INFO) << "Acquired write lock for publish";
            if (!stream->Write(request)) {
                LOG(ERROR) << "Failed to send PublishValuesRequest for " << path;
            } else {
                LOG(INFO) << "Successfully sent PublishValuesRequest for " << path;
            }
            LOG(INFO) << "Released write lock for publish";
        }
    }

    std::string find_path_for_id(int32_t signal_id) {
        std::lock_guard<std::mutex> lock(actuators_mutex_);
        auto it = id_to_path_.find(signal_id);
        return it != id_to_path_.end() ? it->second : "";
    }

    int32_t get_signal_id_for_path(const std::string& path) {
        std::lock_guard<std::mutex> lock(actuators_mutex_);
        auto it = path_to_id_.find(path);
        return it != path_to_id_.end() ? it->second : -1;
    }

    Value convert_from_proto(const kuksa::val::v2::Value& proto_value) {
        if (proto_value.has_bool_()) {
            return proto_value.bool_();
        } else if (proto_value.has_int32()) {
            return proto_value.int32();
        } else if (proto_value.has_float_()) {
            return proto_value.float_();
        } else if (proto_value.has_double_()) {
            return proto_value.double_();
        } else if (proto_value.has_string()) {
            return proto_value.string();
        }
        return false;  // Default
    }

    kuksa::val::v2::Value convert_to_proto(const Value& cpp_value) {
        kuksa::val::v2::Value proto_value;

        std::visit([&proto_value](auto&& arg) {
            using T = std::decay_t<decltype(arg)>;
            if constexpr (std::is_same_v<T, bool>) {
                proto_value.set_bool_(arg);
            } else if constexpr (std::is_same_v<T, int32_t>) {
                proto_value.set_int32(arg);
            } else if constexpr (std::is_same_v<T, float>) {
                proto_value.set_float_(arg);
            } else if constexpr (std::is_same_v<T, double>) {
                proto_value.set_double_(arg);
            } else if constexpr (std::is_same_v<T, std::string>) {
                proto_value.set_string(arg);
            }
        }, cpp_value);

        return proto_value;
    }

    // Queue actuation request for async processing
    void queue_actuation_request(const ActuationRequest& req) {
        std::lock_guard<std::mutex> lock(actuation_mutex_);
        actuation_queue_.push(req);
        actuation_cv_.notify_one();
    }

    // Worker thread that processes actuation requests
    void actuation_worker() {
        LOG(INFO) << "Actuation worker thread started";

        while (running_) {
            std::unique_lock<std::mutex> lock(actuation_mutex_);

            // Wait for requests
            actuation_cv_.wait(lock, [this]() {
                return !actuation_queue_.empty() || !running_;
            });

            if (!running_) break;

            if (!actuation_queue_.empty()) {
                ActuationRequest req = actuation_queue_.front();
                actuation_queue_.pop();
                lock.unlock();

                // Call user callback (may block for hardware delay)
                if (actuation_callback_) {
                    actuation_callback_(req);
                }
            }
        }

        LOG(INFO) << "Actuation worker thread stopped";
    }

    std::string address_;
    std::unique_ptr<VAL::Stub> stub_;
    bool connected_;
    std::atomic<bool> running_;

    // Actuator registration
    std::mutex actuators_mutex_;
    std::vector<std::string> actuator_paths_;
    std::map<int32_t, std::string> id_to_path_;
    std::map<std::string, int32_t> path_to_id_;

    // Actuation callback
    ActuationCallback actuation_callback_;

    // Actuation request queue (one worker thread processes all actuations sequentially)
    std::mutex actuation_mutex_;
    std::queue<ActuationRequest> actuation_queue_;
    std::condition_variable actuation_cv_;
    std::thread actuation_worker_thread_;

    // Promise for ProvideActuationResponse
    std::promise<bool> provide_response_promise_;
    std::future<bool> provide_response_future_;

    // Publishing
    std::mutex publish_mutex_;
    std::queue<PublishRequest> publish_queue_;
    std::condition_variable publish_cv_;

    // Stream write synchronization
    std::mutex stream_write_mutex_;

    // Threads
    std::thread stream_thread_;
};

// ============================================================================
// Public API implementation
// ============================================================================

ActuatorProvider::ActuatorProvider(const std::string& databroker_address)
    : impl_(std::make_unique<Impl>(databroker_address)) {
}

ActuatorProvider::~ActuatorProvider() = default;

bool ActuatorProvider::connect() {
    return impl_->connect();
}

void ActuatorProvider::disconnect() {
    impl_->disconnect();
}

bool ActuatorProvider::is_connected() const {
    return impl_->is_connected();
}

bool ActuatorProvider::provide_actuators(const std::vector<std::string>& paths) {
    return impl_->provide_actuators(paths);
}

void ActuatorProvider::on_actuate_request(ActuationCallback callback) {
    impl_->on_actuate_request(callback);
}

void ActuatorProvider::publish_actual_value(const std::string& path, const Value& value) {
    impl_->publish_actual_value(path, value);
}

void ActuatorProvider::start() {
    impl_->start();
}

void ActuatorProvider::stop() {
    impl_->stop();
}

// Template specializations
template<>
void ActuatorProvider::publish_actual<bool>(const std::string& path, bool value) {
    publish_actual_value(path, Value(value));
}

template<>
void ActuatorProvider::publish_actual<int32_t>(const std::string& path, int32_t value) {
    publish_actual_value(path, Value(value));
}

template<>
void ActuatorProvider::publish_actual<float>(const std::string& path, float value) {
    publish_actual_value(path, Value(value));
}

template<>
void ActuatorProvider::publish_actual<double>(const std::string& path, double value) {
    publish_actual_value(path, Value(value));
}

template<>
void ActuatorProvider::publish_actual<std::string>(const std::string& path, std::string value) {
    publish_actual_value(path, Value(value));
}

// Additional integer type specializations for compatibility
template<>
void ActuatorProvider::publish_actual<long>(const std::string& path, long value) {
    publish_actual_value(path, Value(static_cast<int32_t>(value)));
}

template<>
void ActuatorProvider::publish_actual<unsigned int>(const std::string& path, unsigned int value) {
    publish_actual_value(path, Value(static_cast<int32_t>(value)));
}

template<>
void ActuatorProvider::publish_actual<unsigned long>(const std::string& path, unsigned long value) {
    publish_actual_value(path, Value(static_cast<int32_t>(value)));
}

} // namespace sdv::vss
