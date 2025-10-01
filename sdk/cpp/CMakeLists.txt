cmake_minimum_required(VERSION 3.16)
project(sdv_state_machine VERSION 0.1.0 LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

# Options
option(BUILD_EXAMPLES "Build examples" ON)
option(BUILD_TESTS "Build tests" ON)
option(WITH_PROMETHEUS "Build with Prometheus support" OFF)

# Find dependencies
find_package(Threads REQUIRED)
find_package(glog REQUIRED)
find_package(yaml-cpp REQUIRED)

if(WITH_PROMETHEUS)
    find_package(prometheus-cpp CONFIG REQUIRED)
endif()

# Library sources
set(HEADERS
    include/sdv/state_machine/state_machine.hpp
    include/sdv/state_machine/hierarchical_state_machine.hpp
    include/sdv/state_machine/transition.hpp
    include/sdv/state_machine/state_definition.hpp
)

set(SOURCES
    src/state_machine.cpp
    src/hierarchical_state_machine.cpp
)

# Create library
add_library(sdv_state_machine ${SOURCES})
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


# Installation
include(GNUInstallDirs)

install(TARGETS sdv_state_machine
    EXPORT sdv_state_machine-targets
    LIBRARY DESTINATION ${CMAKE_INSTALL_LIBDIR}
    ARCHIVE DESTINATION ${CMAKE_INSTALL_LIBDIR}
    RUNTIME DESTINATION ${CMAKE_INSTALL_BINDIR}
)

install(DIRECTORY include/sdv TYPE INCLUDE)

install(EXPORT sdv_state_machine-targets
    FILE sdv_state_machine-config.cmake
    NAMESPACE sdv::
    DESTINATION ${CMAKE_INSTALL_LIBDIR}/cmake/sdv_state_machine
)

# Examples
if(BUILD_EXAMPLES)
    add_subdirectory(examples)
endif()

# Tests
if(BUILD_TESTS)
    enable_testing()
    add_subdirectory(tests)
endif()