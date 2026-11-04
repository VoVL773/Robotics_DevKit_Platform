#include <exception>
#include <memory>
#include "{{package_name}}/hello_node.hpp"

int main(int argc, char ** argv)
{
  rclcpp::init(argc, argv);
  int result = 0;
  try {
    rclcpp::spin(std::make_shared<{{package_name}}::HelloNode>());
  } catch (const std::exception & error) {
    RCLCPP_ERROR(rclcpp::get_logger("{{node_name}}"), "%s", error.what());
    result = 1;
  }
  rclcpp::shutdown();
  return result;
}
