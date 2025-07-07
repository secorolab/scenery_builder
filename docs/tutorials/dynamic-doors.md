---
title: Dynamic Doors in Gazebo
layout: default
parent: Tutorials
---

# Dynamic Doors in Gazebo

This tutorial assumes you have a door model as explained in this [tutorial](composable-models).

If you have included an initial state for any doors (as described in the tutorial), the scenery_builder will automatically add the `InitialJointStatePlugin` in the generated world file.

## Specifying Door Behaviours

Prepare a YAML file with the behaviours of each dynamic door. Note this can be a subset of the doors described in the model. The structure of this file follows the pattern below:

```yaml
door-instance-1:
  - type: <behaviour type>
    joint_name: <joint @id in object model>
    # Additional parameters of the behaviour
...
door-instance-n:
  - type: <behaviour type>
    joint_name: <joint @id in object model>
    # Additional parameters of the behaviour
```

### Timed-based behaviours

The behaviour is described by the type `timed-state-change` and the name of the joint described in the door object model:

```yaml
door-instance-12: # The @id of the door instance
  - type: timed-state-change
    joint_name: door:door-hinge # The door joint specified in the door object model
```

The timed-based behaviour is described in a JSON file. The use of an external file was chosen for reproducibility, as the same timestamps can be used in multiple runs to rule out non-deterministic behaviour. The format is as follows:

```JSON
{
    "keyframes": [
        {
            "position": 0.0,
            "time": 0.0
        },
        {
            "position": 1.7,
            "time": 18
        }
    ]
}
```

The scenery_builder can generate the specification for the timed-based behaviour using random sampled "keyframes" as the time when doors change transitions, but the generation process is completely independent, i.e, it is possible to write custom scripts or specify the keyframes by hand.
To use the generated keyframes, use the `scenery_builder` CLI:

```bash
floorplan generate -i models/json-ld -o gen/dynamic-floorplan door-keyframes 
```

### Distance-triggered behaviours

This behaviour is described by the type `distance-triggered-state-change`, and the name of the door joint, similarly to the timed-based behaviours. Additionally, the specification includes the joint angle before the trigger is activated, the distance threshold at which an agent will trigger the behavior and the joint angle of the door at the end of this transition. 

```yaml
door-instance-6: # The @id of the door instance
  - type: distance-triggered-state-change
    start_joint_angle: 1.4
    trigger_dist: 1.3
    target_joint_angle: 0.0
    joint_name: door:door-hinge
```

## Generating the Gazebo world and SDF models

Let us assume you have generated the JSON-LD representation of the FloorPlan model into `models/json-ld` and you have stored the manually-defined door models into `doors/json-ld`.
The behaviours specification is stored in a file called `behaviours.yaml`.

Use the scenery builder to generate the Gazebo world:

```bash
floorplan generate -i models/json-ld -i doors/json-ld -o gen/dynamic-floorplan gazebo 
```

## Loading the Gazebo world

As a prerequisite, you must have compiled the [FloorPlan Gazebo Plugins](https://github.com/secorolab/floorplan-gazebo-plugins?tab=readme-ov-file#installation).

Before loading the Gazebo world, make Gazebo can find the SDF files, meshes, and optionally the timed-behaviour specifications for the doors. To do so, add the paths where you have generated the 3d-mesh, and gazebo artefacts to your `GZ_SIM_RESOURCE_PATH`. For the example above where these are stored in `gen/dynamic-floorplan`, this would look like: 

```bash
export GZ_SIM_RESOURCE_PATH=$HOME/path/to/models/gen/dynamic-floorplan/gazebo/worlds:$HOME/path/to/models/gen/dynamic-floorplan/gazebo/models:$HOME/path/to/models/gen/dynamic-floorplan/3d-mesh:$GZ_SIM_RESOURCE_PATH
```

If you have any doors with timed-based behaviours, make sure to add the path the `doors/behaviours` path to `GZ_SIM_RESOURCE_PATH` as well:

```bash
export GZ_SIM_RESOURCE_PATH=$HOME/path/to/models/gen/dynamic-floorplan/doors-behaviours:$GZ_SIM_RESOURCE_PATH
```

### In Gazebo

If you are not using ROS, make sure you have added the Gazebo plugin path to `GZ_SIM_SYSTEM_PLUGIN_PATH`. 

Start the server:

```bash
gz sim -s gen/dynamic-floorplan/gazebo/worlds/dynamic-floorplan.sdf
```

Then the Gazebo GUI:

```bash
gz sim -g
```

### Using ROS

If you are using ROS, make sure you have sourced your colcon workspace. You can launch the Gazebo world as described in the [Gazebo documentation](https://gazebosim.org/docs/harmonic/ros2_launch_gazebo/). For example:

```bash
ros2 launch ros_gz_sim gz_sim.launch.py gz_args:=dynamic-floorplan.sdf
```
