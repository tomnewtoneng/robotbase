FROM ros:jazzy-ros-base

# Add the OSRF apt repo for Gazebo Harmonic, then install the sim stack,
# the ROS<->gz bridge, robot_state_publisher, xacro and colcon.
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
      ros-jazzy-robot-state-publisher \
      ros-jazzy-xacro \
      python3-colcon-common-extensions \
      python3-numpy \
    && rm -rf /var/lib/apt/lists/*

# Optional visualization: foxglove_bridge (only used when a project is launched
# with --gui). Kept in its own layer so it doesn't invalidate the base install.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-jazzy-foxglove-bridge \
    && rm -rf /var/lib/apt/lists/*

# Episode recording: rosbag2 + the MCAP storage plugin. Every scenario run is
# recorded to a portable .mcap (Foxglove/Rerun-openable). Own layer, and ros-base
# does not ship rosbag2, so install it explicitly.
RUN apt-get update && apt-get install -y --no-install-recommends \
      ros-jazzy-rosbag2 ros-jazzy-rosbag2-storage-mcap \
    && rm -rf /var/lib/apt/lists/*

# Headless software rendering (Mesa llvmpipe); no host GPU assumed.
ENV LIBGL_ALWAYS_SOFTWARE=1
ENV OGRE_RTT_MODE=Copy
WORKDIR /workspace
