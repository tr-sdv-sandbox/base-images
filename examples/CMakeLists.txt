cmake_minimum_required(VERSION 3.16)
project(climate_control_example)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Find dependencies
find_package(glog REQUIRED)
find_package(Threads REQUIRED)

# Add SDK include path
set(SDK_PATH "${CMAKE_CURRENT_SOURCE_DIR}/../sdk/cpp")

# Create climate control executable
add_executable(climate_control climate_control.cpp)

target_include_directories(climate_control
    PRIVATE
        ${SDK_PATH}/include
)

target_link_libraries(climate_control
    PRIVATE
        glog::glog
        Threads::Threads
)

# Install
install(TARGETS climate_control
    DESTINATION bin
)

install(FILES climate_control_test_spec.yaml
    DESTINATION share/examples
)