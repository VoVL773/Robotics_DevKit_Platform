"""生成独立项目的 GitHub Actions 工作流。"""


def workflow_for(kind):
    ros = kind.startswith('ros2_')
    if ros:
        return '''name: ROS smoke
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-24.04
    container: ros:jazzy-ros-base
    steps:
      - uses: actions/checkout@v4
        with:
          path: ws/src/project
      - name: Build and test
        shell: bash
        run: |
          source /opt/ros/jazzy/setup.bash
          apt-get update
          apt-get install -y python3-colcon-common-extensions python3-rosdep python3-pytest
          cd ws
          rosdep update
          rosdep install --from-paths src --ignore-src -r -y
          colcon build --symlink-install
          source install/setup.bash
          colcon test --event-handlers console_direct+
          colcon test-result --verbose
'''
    return '''name: CPU smoke
on: [push, pull_request]
jobs:
  test:
    runs-on: ubuntu-24.04
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - run: python -m pip install -e '.[dev]'
      - run: python -m pytest -q
      - run: python -m training.train
      - run: python -m training.evaluate
'''
