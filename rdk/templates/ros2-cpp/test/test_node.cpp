#include <chrono>
#include <memory>
#include <stdexcept>
#include "gtest/gtest.h"
#include "{{package_name}}/hello_node.hpp"

TEST(HelloNode, TimerAndParameters)
{
  rclcpp::init(0, nullptr);
  auto options = rclcpp::NodeOptions().parameter_overrides({rclcpp::Parameter("period", 0.01)});
  auto node = std::make_shared<{{package_name}}::HelloNode>(options);
  EXPECT_EQ(node->get_parameter("message").as_string(), "hello from {{package_name}}");
  auto deadline = std::chrono::steady_clock::now() + std::chrono::seconds(3);
  while (node->count() == 0 && std::chrono::steady_clock::now() < deadline) {
    rclcpp::spin_some(node);
  }
  EXPECT_GT(node->count(), 0u);
  node.reset();
  rclcpp::shutdown();
}

TEST(HelloNode, RejectsInvalidPeriod)
{
  rclcpp::init(0, nullptr);
  auto options = rclcpp::NodeOptions().parameter_overrides({rclcpp::Parameter("period", 0.0)});
  EXPECT_THROW(std::make_shared<{{package_name}}::HelloNode>(options), std::invalid_argument);
  rclcpp::shutdown();
}
