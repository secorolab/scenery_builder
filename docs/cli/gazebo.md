---
layout: default
title: gazebo
parent: generate
---

# gazebo

Generate Gazebo world, models and launch files

Usage:

```bash
floorplan generate gazebo [OPTIONS]
```

## Options

### Optional

- `--ros-version` (CHOICE)
    ROS version for launch files.
    Default: `ROS2`
- `--ros-pkg` (STRING)
    Name of the ROS package where gazebo models.
    Default: `floorplan_models`
- `--behaviors` (PATH)
    Path to YAML file with door behavior parameters.
- `--world-frame` (STRING)
    ID of the world frame in the input models.
    Default: `world-frame`


