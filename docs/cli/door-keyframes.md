---
layout: default
title: door-keyframes
parent: generate
---

# door-keyframes

Generate the sampled keyframes for doors with time-based behaviours

Usage:

```bash
floorplan generate door-keyframes [OPTIONS]
```

## Options

### Optional

- `--start-frame` (INT)
    Timestamp of the first keyframe.
- `--end-frame` (INT)
    Timestamp of the last keyframe.
    Default: `180`
- `--start-state` (FLOAT)
    Start joint angle of the doors.
- `--sampling-interval` (INT)
    Sampling interval.
    Default: `30`
- `--state-change-probability`, `--state-change-prob` (FLOAT)
    Probability of a door changing states at the next interval.
    Default: `0.5`


