"""Pytest configuration — disable conflicting ROS launch_testing plugins."""

# This conftest handles the case where ROS 2 pytest plugins are installed
# globally and interfere with our standalone test suite.
collect_ignore_glob = ["**/launch_testing*"]
