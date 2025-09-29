#include <iostream>
#include <iomanip>
#include <thread>
#include <chrono>
#include <cstdlib>
#include <string>
#include <memory>
#include <grpcpp/grpcpp.h>
#include <glog/logging.h>

// Include generated protobuf headers
#include "kuksa/val/v1/types.pb.h"
#include "kuksa/val/v1/val.pb.h"
#include "kuksa/val/v1/val.grpc.pb.h"

using grpc::Channel;
using grpc::ClientContext;
using grpc::Status;
using kuksa::val::v1::GetRequest;
using kuksa::val::v1::GetResponse;
using kuksa::val::v1::SubscribeRequest;
using kuksa::val::v1::SubscribeResponse;
using kuksa::val::v1::SetRequest;
using kuksa::val::v1::SetResponse;
using kuksa::val::v1::EntryRequest;
using kuksa::val::v1::DataEntry;
using kuksa::val::v1::Datapoint;
using kuksa::val::v1::Field;
using kuksa::val::v1::View;
using kuksa::val::v1::VAL;

class EngineMonitor {
private:
    std::string kuksa_address_;
    int kuksa_port_;
    float rpm_limit_;
    float temp_limit_;
    std::unique_ptr<VAL::Stub> stub_;
    
    std::string getEnvOrDefault(const char* name, const std::string& default_value) {
        const char* value = std::getenv(name);
        return value ? std::string(value) : default_value;
    }
    
public:
    EngineMonitor() 
        : kuksa_address_(getEnvOrDefault("KUKSA_ADDRESS", "localhost"))
        , kuksa_port_(std::stoi(getEnvOrDefault("KUKSA_PORT", "55555")))
        , rpm_limit_(std::stof(getEnvOrDefault("RPM_LIMIT", "4500")))
        , temp_limit_(std::stof(getEnvOrDefault("TEMP_LIMIT", "105.0"))) {
    }
    
    bool connect() {
        try {
            std::string target = kuksa_address_ + ":" + std::to_string(kuksa_port_);
            LOG(INFO) << "Connecting to KUKSA.val at " << target;
            
            auto channel = grpc::CreateChannel(target, grpc::InsecureChannelCredentials());
            stub_ = VAL::NewStub(channel);
            
            // Test connection with a simple Get request
            ClientContext context;
            GetRequest request;
            GetResponse response;
            
            auto* entry = request.add_entries();
            entry->set_path("Vehicle.Version.VehicleIdentification.VIN");
            entry->add_fields(Field::FIELD_VALUE);
            
            Status status = stub_->Get(&context, request, &response);
            
            if (status.ok()) {
                LOG(INFO) << "Connected to KUKSA.val databroker";
                return true;
            } else {
                LOG(ERROR) << "Failed to connect: " << status.error_message();
                return false;
            }
        }
        catch (const std::exception& e) {
            LOG(ERROR) << "Connection error: " << e.what();
            return false;
        }
    }
    
    void monitorEngine() {
        LOG(INFO) << "Starting engine monitoring...";
        LOG(INFO) << "RPM limit: " << rpm_limit_;
        LOG(INFO) << "Temperature limit: " << temp_limit_ << "°C";
        
        // Create subscription request
        SubscribeRequest request;
        
        // Subscribe to Engine RPM
        auto* rpm_entry = request.add_entries();
        rpm_entry->set_path("Vehicle.Powertrain.CombustionEngine.Speed");
        rpm_entry->add_fields(Field::FIELD_VALUE);
        
        // Subscribe to Engine Temperature  
        auto* temp_entry = request.add_entries();
        temp_entry->set_path("Vehicle.Powertrain.CombustionEngine.ECT");
        temp_entry->add_fields(Field::FIELD_VALUE);
        
        LOG(INFO) << "Subscribing to " << request.entries_size() << " signals";
        
        // Create context and start subscription
        ClientContext context;
        auto reader = stub_->Subscribe(&context, request);
        
        LOG(INFO) << "Started subscription, waiting for updates...";
        
        SubscribeResponse response;
        while (reader->Read(&response)) {
            LOG(INFO) << "Received update with " << response.updates_size() << " entries";
            // Process updates
            for (const auto& update : response.updates()) {
                const auto& entry = update.entry();
                
                LOG(INFO) << "Processing update for path: " << entry.path();
                
                if (entry.has_value()) {
                    const auto& dp = entry.value();
                    
                    if (entry.path() == "Vehicle.Powertrain.CombustionEngine.Speed") {
                        float rpm = 0.0;
                        if (dp.has_float_()) {
                            rpm = dp.float_();
                        } else if (dp.has_double_()) {
                            rpm = static_cast<float>(dp.double_());
                        } else if (dp.has_int32()) {
                            rpm = static_cast<float>(dp.int32());
                        } else if (dp.has_int64()) {
                            rpm = static_cast<float>(dp.int64());
                        } else if (dp.has_uint32()) {
                            rpm = static_cast<float>(dp.uint32());
                        } else if (dp.has_uint64()) {
                            rpm = static_cast<float>(dp.uint64());
                        } else {
                            LOG(INFO) << "RPM data not numeric (type: " << dp.value_case() << ")";
                            continue;
                        }
                        
                        LOG(INFO) << "RPM: " << rpm << " rpm";
                        if (rpm > rpm_limit_) {
                            LOG(WARNING) << "RPM ALERT: " << rpm 
                                        << " exceeds limit of " << rpm_limit_;
                        }
                    }
                    else if (entry.path() == "Vehicle.Powertrain.CombustionEngine.ECT") {
                        float temp = 0.0;
                        if (dp.has_float_()) {
                            temp = dp.float_();
                        } else if (dp.has_double_()) {
                            temp = static_cast<float>(dp.double_());
                        } else if (dp.has_int32()) {
                            temp = static_cast<float>(dp.int32());
                        } else if (dp.has_int64()) {
                            temp = static_cast<float>(dp.int64());
                        } else if (dp.has_uint32()) {
                            temp = static_cast<float>(dp.uint32());
                        } else if (dp.has_uint64()) {
                            temp = static_cast<float>(dp.uint64());
                        } else {
                            LOG(INFO) << "Temperature data not numeric (type: " << dp.value_case() << ")";
                            continue;
                        }
                        
                        LOG(INFO) << "Temperature: " << temp << " °C";
                        if (temp > temp_limit_) {
                            LOG(WARNING) << "TEMPERATURE ALERT: " << temp 
                                        << "°C exceeds limit of " << temp_limit_ << "°C";
                        }
                    }
                } else {
                    LOG(INFO) << "No value in update";
                }
            }
        }
        
        Status status = reader->Finish();
        if (!status.ok()) {
            LOG(ERROR) << "Subscription error: " << status.error_message();
        }
    }
    
    void run() {
        while (true) {
            if (connect()) {
                try {
                    monitorEngine();
                }
                catch (const std::exception& e) {
                    LOG(ERROR) << "Monitoring error: " << e.what();
                }
            }
            
            LOG(INFO) << "Reconnecting in 5 seconds...";
            std::this_thread::sleep_for(std::chrono::seconds(5));
        }
    }
};

int main(int argc, char* argv[]) {
    // Initialize Google's logging library
    google::InitGoogleLogging(argv[0]);
    FLAGS_logtostderr = 1;  // Log to stderr instead of log files
    FLAGS_colorlogtostderr = 1;  // Colorize logs
    
    LOG(INFO) << "Engine Monitor User Function Starting...";
    LOG(INFO) << "RPM limit: " << std::getenv("RPM_LIMIT");
    LOG(INFO) << "Temperature limit: " << std::getenv("TEMP_LIMIT") << "°C";
    
    try {
        EngineMonitor monitor;
        monitor.run();
    }
    catch (const std::exception& e) {
        LOG(FATAL) << "Fatal error: " << e.what();
        return 1;
    }
    
    return 0;
}