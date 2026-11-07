#ifndef {{package_name_upper}}__HELLO_NODE_HPP_
#define {{package_name_upper}}__HELLO_NODE_HPP_

#include <chrono>
#include <cmath>
#include <cstdint>
#include <stdexcept>
#include <string>
#include "rclcpp/rclcpp.hpp"

namespace {{package_name}}
{
class HelloNode : public rclcpp::Node
{
public:
  explicit HelloNode(const rclcpp::NodeOptions & options = rclcpp::NodeOptions())
  : Node("{{node_name}}", options)
  {
    declare_parameter<std::string>("message", "hello from {{package_name}}");
    const double period = declare_parameter<double>("period", 1.0);
    if (!std::isfinite(period) || period <= 0.0) {
      throw std::invalid_argument("period must be finite and greater than zero");
    }
    const auto interval = std::chrono::duration_cast<std::chrono::nanoseconds>(
      std::chrono::duration<double>(period));
    if (interval.count() <= 0) {
      throw std::invalid_argument("period must be at least one nanosecond");
    }
    timer_ = create_wall_timer(interval, [this]() {
      ++count_;
      RCLCPP_INFO(get_logger(), "%s #%lu",
        get_parameter("message").as_string().c_str(), static_cast<unsigned long>(count_));
    });
    RCLCPP_INFO(get_logger(), "{{node_name}} started; press Ctrl+C to exit");
  }

  uint64_t count() const {return count_;}

private:
  uint64_t count_{0};
  rclcpp::TimerBase::SharedPtr timer_;
};
}  // namespace {{package_name}}
#endif  // {{package_name_upper}}__HELLO_NODE_HPP_
