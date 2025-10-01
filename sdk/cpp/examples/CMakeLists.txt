# Examples for SDV State Machine SDK

# Door control example
add_executable(door_example door_example.cpp)
target_link_libraries(door_example PRIVATE sdv::state_machine)

# Vehicle state example
add_executable(vehicle_example vehicle_example.cpp)
target_link_libraries(vehicle_example PRIVATE sdv::state_machine)

# Add custom target to build all examples
add_custom_target(examples DEPENDS door_example vehicle_example)