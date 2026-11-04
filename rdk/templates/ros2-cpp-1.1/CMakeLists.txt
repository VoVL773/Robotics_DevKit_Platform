cmake_minimum_required(VERSION 3.16)
project({{package_name}})

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)

add_executable({{node_name}} src/hello_node.cpp)
target_compile_features({{node_name}} PUBLIC cxx_std_17)
target_include_directories({{node_name}} PRIVATE include)
ament_target_dependencies({{node_name}} rclcpp)
install(TARGETS {{node_name}} DESTINATION lib/${PROJECT_NAME})
install(DIRECTORY launch config DESTINATION share/${PROJECT_NAME})

if(BUILD_TESTING)
  find_package(ament_cmake_gtest REQUIRED)
  ament_add_gtest(test_node test/test_node.cpp)
  target_compile_features(test_node PUBLIC cxx_std_17)
  target_include_directories(test_node PRIVATE include)
  ament_target_dependencies(test_node rclcpp)
endif()

ament_package()
