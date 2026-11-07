from glob import glob
from setuptools import find_packages, setup

name = '{{package_name}}'
setup(name=name, version='0.1.0', packages=find_packages(exclude=['test']),
      data_files=[('share/ament_index/resource_index/packages', ['resource/'+name]),
                  ('share/'+name, ['package.xml']),
                  ('share/'+name+'/launch', glob('launch/*.launch.py')),
                  ('share/'+name+'/config', glob('config/*'))],
      install_requires=['setuptools'], zip_safe=False,
      maintainer='{{maintainer}}',
      maintainer_email='{{maintainer_email}}',
      license='{{license}}', entry_points={'console_scripts': []})
