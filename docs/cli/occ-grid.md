---
layout: default
title: occ-grid
parent: generate
---

# occ-grid

Generate the occupancy grid map of the floorplan

Usage:

```bash
floorplan generate occ-grid [OPTIONS]
```

## Options

### Optional

- `--laser-height` (FLOAT)
    Height of the laser to generate the occupancy grid.
    Default: `0.7`
- `--border` (INT)
    Border the occupancy grid image file.
    Default: `50`
- `--resolution` (FLOAT)
    Resolution of the pgm file in m/pixel.
    Default: `0.05`
- `--occupied-threshold` (FLOAT)
    Probability of a pixel at which a cell is considered occupied.
    Default: `0.65`
- `--free-threshold` (FLOAT)
    Probability of a pixel at which a cell is considered free.
    Default: `0.196`
- `--negate` (INT)
    Whether the occupied/free/unknown semantics of the occupancy grid should be reversed.
- `--unknown-value` (INT)
    Value for cells to be considered unknown in the occupancy grid.
    Default: `200`
- `--occupied-value` (INT)
    Value for cells to be considered occupied in the occupancy map.
- `--free-value` (INT)
    Value for cells to be considered free in the occupancy map.
    Default: `255`


