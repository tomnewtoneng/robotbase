FROM ros:jazzy-ros-base

# gz-harmonic lives in the OSRF apt repo (not configured on the ros:jazzy base),
# so add it before installing Gazebo Harmonic + the ROS<->gz bridge for Jazzy.
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl lsb-release gnupg ca-certificates \
    && curl https://packages.osrfoundation.org/gazebo.gpg \
         --output /usr/share/keyrings/pkgs-osrf-archive-keyring.gpg \
    && echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/pkgs-osrf-archive-keyring.gpg] http://packages.osrfoundation.org/gazebo/ubuntu-stable $(lsb_release -cs) main" \
         > /etc/apt/sources.list.d/gazebo-stable.list \
    && apt-get update && apt-get install -y --no-install-recommends \
      gz-harmonic \
      ros-jazzy-ros-gz-sim \
      ros-jazzy-ros-gz-bridge \
      python3-numpy \
    && rm -rf /var/lib/apt/lists/*

# Force headless software rendering (Mesa llvmpipe); no host GPU assumed.
ENV LIBGL_ALWAYS_SOFTWARE=1
ENV OGRE_RTT_MODE=Copy
WORKDIR /spike
COPY minimal.sdf check_scan.py run-spike.sh ./
