from glob import glob
from setuptools import find_packages, setup

package_name = '{{package_name}}'
setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='{{maintainer}}',
    maintainer_email='{{maintainer_email}}',
    description='Parameterized ROS 2 Python example node',
    license='{{license}}',
    entry_points={'console_scripts': [
        '{{node_name}} = {{package_name}}.hello_node:main',
    ]},
)
