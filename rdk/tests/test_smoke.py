"""真实构建和运行；用 ROBOT_CLI_RUN_SMOKE=1 启用，依赖由宿主环境提供。"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

import pytest

pytestmark = pytest.mark.skipif(os.environ.get('ROBOT_CLI_RUN_SMOKE') != '1',
                                reason='设置 ROBOT_CLI_RUN_SMOKE=1 运行真实依赖冒烟测试')


def run(arguments, cwd, env):
    result = subprocess.run(arguments, cwd=cwd, env=env, text=True, capture_output=True, timeout=180)
    assert result.returncode == 0, result.stdout + result.stderr
    return result.stdout


@pytest.mark.parametrize('template', ['ros2-python', 'ros2-cpp', 'ros2-bringup'])
def test_ros_build_test_and_launch(template, tmp_path):
    env = {**os.environ, 'ROBOT_CLI_TEMPLATE_HOME': str(tmp_path / 'store'),
           'ROS_LOG_DIR': str(tmp_path / 'ros_logs'), 'ROS_AUTOMATIC_DISCOVERY_RANGE': 'LOCALHOST',
           'ROS_DOMAIN_ID': str(50 + ['ros2-python', 'ros2-cpp', 'ros2-bringup'].index(template))}
    workspace = tmp_path / 'ws'
    name = template.replace('-', '_') + '_demo'
    # 显式指定新节点名，验证 CMake、入口和 Launch 同步替换。
    arguments = [sys.executable, '-m', 'rdk_cli.main', 'project', 'create', template,
                 '--name', name, '--output', str(workspace / 'src'), '--maintainer', 'Test Team',
                 '--license', 'MIT', '--ci', '--git', '--smoke-test']
    if template != 'ros2-bringup':
        arguments += ['--node-name', 'demo_node']
    run(arguments, tmp_path, env)
    assert (workspace / 'src' / name / '.git').is_dir()
    launch = 'bringup.launch.py' if template == 'ros2-bringup' else 'hello.launch.py'
    script = f'source install/setup.bash && exec ros2 launch {name} {launch}'
    log = tmp_path / 'launch.log'
    with log.open('w') as output:
        process = subprocess.Popen(['bash', '-c', script], cwd=workspace, env=env,
                                   stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        try:
            deadline = time.monotonic() + 20
            while time.monotonic() < deadline:
                text = log.read_text()
                expected = 'I heard:' if template == 'ros2-bringup' else f'hello from {name} #1'
                if expected in text:
                    break
                assert process.poll() is None, text
                time.sleep(0.1)
            else:
                pytest.fail(log.read_text())
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGINT)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait(timeout=5)


def test_cpu_training_and_evaluation(tmp_path):
    pytest.importorskip('torch')
    env = {**os.environ, 'ROBOT_CLI_TEMPLATE_HOME': str(tmp_path / 'store'),
           'PYTEST_DISABLE_PLUGIN_AUTOLOAD': '1'}
    env.pop('ROS_DISTRO', None)
    env.pop('ROS_VERSION', None)
    run([sys.executable, '-m', 'rdk_cli.main', 'project', 'create', 'pytorch-training',
         '--name', 'training_demo', '--output', str(tmp_path), '--ci', '--smoke-test'], tmp_path, env)
    project = tmp_path / 'training_demo'
    trained = json.loads((project / 'outputs/metrics.json').read_text())
    evaluated = json.loads((project / 'outputs/evaluation.json').read_text())
    assert trained == evaluated
    assert trained['accuracy'] >= 0.75
