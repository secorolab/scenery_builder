---
layout: default
title: generate
parent: floorplan
---

# generate

Generate execution artefacts from JSON-LD models

Usage:

```bash
floorplan generate [OPTIONS] COMMAND1 [ARGS]... [COMMAND2 [ARGS]...]...
```

## Options

### Required

- `-i`, `--inputs`, `--input-path` (PATH)
    Path with JSON-LD models to be used as inputs.

### Optional

- `-o`, `--outputs`, `--output-path` (PATH)
    Output path for generated artefacts.
    Default: `.`
- `--templates` (PATH)
    Path with Jinja templates.
    Default: `.`
- `-c`, `--config` (PATH)
    Read values from TOML config file.


## Commands

- [`door-keyframes`](door-keyframes) - Generate the sampled keyframes for doors with time-based behaviours
- [`gazebo`](gazebo) - Generate Gazebo world, models and launch files
- [`mesh`](mesh) - Generate a 3D-mesh in STL or gltF 2.0 format
- [`occ-grid`](occ-grid) - Generate the occupancy grid map of the floorplan
- [`polyline`](polyline) - Generate a 3D polyline representation of the floorplan
- [`tasks`](tasks) - Generate disinfection tasks for each room in the floorplan
