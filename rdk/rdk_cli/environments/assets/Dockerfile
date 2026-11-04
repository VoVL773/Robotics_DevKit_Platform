# Generated context requires environment.lock.json, apt.lock and a digest-pinned base.
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG ROS_DISTRO
ENV ROS_DISTRO=${ROS_DISTRO}
SHELL ["/bin/bash", "-o", "pipefail", "-c"]
USER root
COPY ros.key /usr/share/keyrings/ros-archive-keyring.gpg
RUN if ! grep -Rqs 'packages.ros.org/ros2/ubuntu' /etc/apt/sources.list.d; then . /etc/os-release && echo "deb [arch=amd64 signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] https://packages.ros.org/ros2/ubuntu ${UBUNTU_CODENAME} main" > /etc/apt/sources.list.d/robot-cli-ros2.list; fi
COPY apt.lock /tmp/apt.lock
RUN apt-get update && DEBIAN_FRONTEND=noninteractive xargs -r -a /tmp/apt.lock apt-get install -y --no-install-recommends && rm -rf /var/lib/apt/lists/*
COPY requirements.lock /tmp/requirements.lock
RUN python3 -m venv --system-site-packages /opt/robot-cli-venv && /opt/robot-cli-venv/bin/pip install --no-deps -r /tmp/requirements.lock && /opt/robot-cli-venv/bin/pip check
COPY cli /opt/robot-cli-source
RUN /opt/robot-cli-venv/bin/pip install --no-deps --no-build-isolation /opt/robot-cli-source
COPY framework.lock /tmp/framework.lock
ARG WITH_TORCH=0
RUN if [ "$WITH_TORCH" = 1 ]; then /opt/robot-cli-venv/bin/pip install --no-deps -r /tmp/framework.lock && /opt/robot-cli-venv/bin/pip check; fi
ENV PATH="/opt/robot-cli-venv/bin:${PATH}"
COPY environment.lock.json /opt/robot-cli/environment.lock.json
RUN dpkg-query -W -f='${Package}=${Version}\n' > /opt/robot-cli/dpkg.lock && pip freeze --local > /opt/robot-cli/python.lock
RUN printf 'source /opt/ros/%s/setup.bash\nexport PATH=/opt/robot-cli-venv/bin:$PATH\n' "$ROS_DISTRO" >> /etc/bash.bashrc
WORKDIR /workspace
CMD ["sleep", "infinity"]
