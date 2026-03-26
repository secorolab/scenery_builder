---
layout: default
title: tasks
parent: generate
---

# tasks

Generate navigation waypoints for each room in the floorplan

The current version creates a YAML file for each room with the waypoints for a disinfection task (one waypoint per corner).
The files currently have the following structure:

```yaml
id: <space name>
task:
  - name: <space name>
    type: waypoint_following
    waypoints:
    - {id: <space name>-point-0000, x: <float>, y: <float>, yaw: <float>, z: <float>}
    - {id: <space name>-point-0001, x: <float>, y: <float>, yaw: <float>, z: <float>}
    - {id: <space name>-point-0002, x: <float>, y: <float>, yaw: <float>, z: <float>}
    - {id: <space name>-point-0003, x: <float>, y: <float>, yaw: <float>, z: <float>}
```


Usage:

```bash
floorplan generate tasks [OPTIONS]
```

## Options

### Optional

- `--dist-to-corner` (FLOAT)
    Distance between generated waypoints and a space's corner.
    Default: `0.7`


