cmake_minimum_required(VERSION 3.16)
project(sdv_sdk VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Options
option(BUILD_EXAMPLES "Build examples" OFF)
option(BUILD_TESTS "Build tests" OFF)
option(WITH_PROMETHEUS "Build with Prometheus support" OFF)
option(WITH_VSS "Build VSS client library" ON)
option(WITH_STATE_MACHINE "Build state machine library" ON)
option(WITH_TESTING "Build testing library" ON)

# Find dependencies
find_package(Threads REQUIRED)
find_package(glog REQUIRED)

if(WITH_STATE_MACHINE)
    find_package(yaml-cpp REQUIRED)
endif()

if(WITH_VSS)
    find_package(Protobuf REQUIRED)
    # Try to find gRPC using CONFIG first, fall back to pkg-config
    find_package(gRPC CONFIG QUIET)
    if(NOT gRPC_FOUND)
        find_package(PkgConfig REQUIRED)
        pkg_check_modules(GRPC REQUIRED grpc++)
        # Create imported target manually for pkg-config
        if(NOT TARGET gRPC::grpc++)
            add_library(gRPC::grpc++ INTERFACE IMPORTED)
            set_target_properties(gRPC::grpc++ PROPERTIES
                INTERFACE_INCLUDE_DIRECTORIES "${GRPC_INCLUDE_DIRS}"
                INTERFACE_LINK_LIBRARIES "${GRPC_LIBRARIES}"
            )
        endif()
        # Find grpc_cpp_plugin
        find_program(GRPC_CPP_PLUGIN grpc_cpp_plugin REQUIRED)
        if(NOT TARGET gRPC::grpc_cpp_plugin)
            add_executable(gRPC::grpc_cpp_plugin IMPORTED)
            set_target_properties(gRPC::grpc_cpp_plugin PROPERTIES
                IMPORTED_LOCATION "${GRPC_CPP_PLUGIN}"
            )
        endif()
    endif()
endif()

if(WITH_PROMETHEUS)
    find_package(prometheus-cpp CONFIG REQUIRED)
endif()

# ============================================================================
# State Machine Library
# ============================================================================

if(WITH_STATE_MACHINE)
    set(SM_HEADERS
        include/sdv/state_machine/state_machine.hpp
        include/sdv/state_machine/hierarchical_state_machine.hpp
        include/sdv/state_machine/transition.hpp
        include/sdv/state_machine/state_definition.hpp
    )

    set(SM_SOURCES
        src/state_machine.cpp
        src/hierarchical_state_machine.cpp
    )

    add_library(sdv_state_machine ${SM_SOURCES})
    add_library(sdv::state_machine ALIAS sdv_state_machine)

    target_include_directories(sdv_state_machine
        PUBLIC
            $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
            $<INSTALL_INTERFACE:include>
    )

    target_link_libraries(sdv_state_machine
        PUBLIC
            Threads::Threads
            glog::glog
            yaml-cpp
    )

    if(WITH_PROMETHEUS)
        target_link_libraries(sdv_state_machine
            PUBLIC
                prometheus-cpp::pull
                prometheus-cpp::push
        )
        target_compile_definitions(sdv_state_machine PUBLIC SDV_WITH_PROMETHEUS)
    endif()
endif()

# ============================================================================
# VSS Client Library
# ============================================================================

if(WITH_VSS)
    # Use bundled v2 proto files
    set(PROTO_PATH "${CMAKE_CURRENT_SOURCE_DIR}/protos")

    if(NOT EXISTS "${PROTO_PATH}/kuksa/val/v2/val.proto")
        message(FATAL_ERROR "kuksa.val.v2 proto files not found in ${PROTO_PATH}/kuksa/val/v2/")
    endif()

    set(PROTO_FILES
        ${PROTO_PATH}/kuksa/val/v2/types.proto
        ${PROTO_PATH}/kuksa/val/v2/val.proto
    )

    # Generate C++ sources from proto files
    set(PROTO_SRCS "")
    set(PROTO_HDRS "")
    foreach(proto_file ${PROTO_FILES})
        get_filename_component(proto_name ${proto_file} NAME_WE)
        get_filename_component(proto_dir ${proto_file} DIRECTORY)

        set(proto_src "${CMAKE_CURRENT_BINARY_DIR}/kuksa/val/v2/${proto_name}.pb.cc")
        set(proto_hdr "${CMAKE_CURRENT_BINARY_DIR}/kuksa/val/v2/${proto_name}.pb.h")
        set(grpc_src "${CMAKE_CURRENT_BINARY_DIR}/kuksa/val/v2/${proto_name}.grpc.pb.cc")
        set(grpc_hdr "${CMAKE_CURRENT_BINARY_DIR}/kuksa/val/v2/${proto_name}.grpc.pb.h")

        add_custom_command(
            OUTPUT ${proto_src} ${proto_hdr} ${grpc_src} ${grpc_hdr}
            COMMAND ${Protobuf_PROTOC_EXECUTABLE}
            ARGS --grpc_out=${CMAKE_CURRENT_BINARY_DIR}
                 --cpp_out=${CMAKE_CURRENT_BINARY_DIR}
                 --plugin=protoc-gen-grpc=$<TARGET_FILE:gRPC::grpc_cpp_plugin>
                 -I ${PROTO_PATH}
                 ${proto_file}
            DEPENDS ${proto_file}
            COMMENT "Generating C++ code from ${proto_file}"
        )

        list(APPEND PROTO_SRCS ${proto_src} ${grpc_src})
        list(APPEND PROTO_HDRS ${proto_hdr} ${grpc_hdr})
    endforeach()

    set(VSS_HEADERS
        include/sdv/vss/types.hpp
        include/sdv/vss/client.hpp
        include/sdv/vss/provider.hpp
        include/sdv/vss/vss.hpp
    )

    set(VSS_SOURCES
        src/vss_client.cpp
        src/provider.cpp
        ${PROTO_SRCS}
    )

    add_library(sdv_vss ${VSS_SOURCES})
    add_library(sdv::vss ALIAS sdv_vss)

    target_include_directories(sdv_vss
        PUBLIC
            $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
            $<BUILD_INTERFACE:${CMAKE_CURRENT_BINARY_DIR}>
            $<INSTALL_INTERFACE:include>
        PRIVATE
            ${Protobuf_INCLUDE_DIRS}
    )

    target_link_libraries(sdv_vss
        PUBLIC
            gRPC::grpc++
            protobuf::libprotobuf
            Threads::Threads
            glog::glog
    )

    # Install VSS library
    install(TARGETS sdv_vss
        EXPORT sdv_vss-targets
        LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
        ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
        RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
    )

    install(EXPORT sdv_vss-targets
        FILE sdv_vss-config.cmake
        NAMESPACE sdv::
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/sdv_vss
    )
endif()

# ============================================================================
# Testing Library
# ============================================================================

if(WITH_TESTING AND WITH_VSS)
    find_package(yaml-cpp REQUIRED)
    find_package(GTest QUIET)  # Optional - only needed for Google Test integration

    set(TESTING_HEADERS
        include/sdv/testing/test_models.hpp
        include/sdv/testing/yaml_parser.hpp
        include/sdv/testing/kuksa_client_wrapper.hpp
        include/sdv/testing/test_runner.hpp
    )

    set(TESTING_SOURCES
        src/testing/yaml_parser.cpp
        src/testing/kuksa_client_wrapper.cpp
        src/testing/test_runner.cpp
    )

    # Add Google Test integration if available
    if(GTest_FOUND)
        list(APPEND TESTING_HEADERS include/sdv/testing/gtest_integration.hpp)
        list(APPEND TESTING_SOURCES src/testing/gtest_integration.cpp)
        message(STATUS "Google Test found - including gtest_integration")
    endif()

    add_library(sdv_testing ${TESTING_SOURCES})
    add_library(sdv::testing ALIAS sdv_testing)

    target_include_directories(sdv_testing
        PUBLIC
            $<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>
            $<INSTALL_INTERFACE:include>
    )

    target_link_libraries(sdv_testing
        PUBLIC
            sdv::vss
            yaml-cpp
            glog::glog
            Threads::Threads
    )

    # Link Google Test if available
    if(GTest_FOUND)
        target_link_libraries(sdv_testing PUBLIC GTest::gtest)
        target_compile_definitions(sdv_testing PUBLIC SDV_WITH_GTEST)
    endif()

    # Install testing library
    install(TARGETS sdv_testing
        EXPORT sdv_testing-targets
        LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
        ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
        RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
    )

    install(EXPORT sdv_testing-targets
        FILE sdv_testing-config.cmake
        NAMESPACE sdv::
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/sdv_testing
    )
endif()


# Installation
include(GNUInstallDirs)

if(WITH_STATE_MACHINE)
    install(TARGETS sdv_state_machine
        EXPORT sdv_state_machine-targets
        LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
        ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
        RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
    )

    install(EXPORT sdv_state_machine-targets
        FILE sdv_state_machine-config.cmake
        NAMESPACE sdv::
        DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/sdv_state_machine
    )
endif()

install(DIRECTORY include/sdv TYPE INCLUDE)

# Examples
if(BUILD_EXAMPLES)
    add_subdirectory(examples)
endif()

# Tests
if(BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()