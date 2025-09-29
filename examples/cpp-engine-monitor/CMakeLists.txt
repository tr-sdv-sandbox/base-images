cmake_minimum_required(VERSION 3.16)
project(engine_monitor)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Set default build type to Release if not specified
if(NOT CMAKE_BUILD_TYPE)
    set(CMAKE_BUILD_TYPE Release)
endif()

# Set optimization flags
set(CMAKE_CXX_FLAGS_RELEASE "-O2 -DNDEBUG")
set(CMAKE_CXX_FLAGS_DEBUG "-O0 -g")

# Find required packages
find_package(Protobuf REQUIRED)
find_package(gRPC CONFIG REQUIRED)
find_package(Threads REQUIRED)

# Find gRPC plugin
find_program(GRPC_CPP_PLUGIN_EXECUTABLE grpc_cpp_plugin)
if(NOT GRPC_CPP_PLUGIN_EXECUTABLE)
    get_target_property(GRPC_CPP_PLUGIN_EXECUTABLE gRPC::grpc_cpp_plugin LOCATION)
endif()

# Proto files location
set(PROTO_PATH "/usr/local/include")
set(PROTO_FILES
    ${PROTO_PATH}/kuksa/val/v1/types.proto
    ${PROTO_PATH}/kuksa/val/v1/val.proto
)

# Generate C++ sources from proto files
set(PROTO_SRCS)
set(PROTO_HDRS)
set(GRPC_SRCS)
set(GRPC_HDRS)

foreach(proto_file ${PROTO_FILES})
    get_filename_component(proto_name ${proto_file} NAME_WE)
    get_filename_component(proto_dir ${proto_file} DIRECTORY)
    string(REPLACE ${PROTO_PATH} "" proto_rel_dir ${proto_dir})
    
    set(proto_src "${CMAKE_CURRENT_BINARY_DIR}${proto_rel_dir}/${proto_name}.pb.cc")
    set(proto_hdr "${CMAKE_CURRENT_BINARY_DIR}${proto_rel_dir}/${proto_name}.pb.h")
    set(grpc_src "${CMAKE_CURRENT_BINARY_DIR}${proto_rel_dir}/${proto_name}.grpc.pb.cc")
    set(grpc_hdr "${CMAKE_CURRENT_BINARY_DIR}${proto_rel_dir}/${proto_name}.grpc.pb.h")
    
    add_custom_command(
        OUTPUT ${proto_src} ${proto_hdr} ${grpc_src} ${grpc_hdr}
        COMMAND ${Protobuf_PROTOC_EXECUTABLE}
        ARGS --grpc_out=${CMAKE_CURRENT_BINARY_DIR}
             --cpp_out=${CMAKE_CURRENT_BINARY_DIR}
             --plugin=protoc-gen-grpc=${GRPC_CPP_PLUGIN_EXECUTABLE}
             -I ${PROTO_PATH}
             ${proto_file}
        DEPENDS ${proto_file}
        COMMENT "Generating C++ code from ${proto_file}"
    )
    
    list(APPEND PROTO_SRCS ${proto_src})
    list(APPEND PROTO_HDRS ${proto_hdr})
    list(APPEND GRPC_SRCS ${grpc_src})
    list(APPEND GRPC_HDRS ${grpc_hdr})
endforeach()

# Create executable with all sources
add_executable(engine_monitor
    engine_monitor.cpp
    ${PROTO_SRCS}
    ${GRPC_SRCS}
)

# Include directories
target_include_directories(engine_monitor PRIVATE
    ${CMAKE_CURRENT_BINARY_DIR}
)

# Link libraries
target_link_libraries(engine_monitor
    PRIVATE
        gRPC::grpc++
        protobuf::libprotobuf
        Threads::Threads
        glog
)

# Set runtime path
set_target_properties(engine_monitor PROPERTIES
    INSTALL_RPATH_USE_LINK_PATH TRUE
)
