---
layout: default
title: variation
parent: floorplan
---

# variation

Generate FPM model variations from a variation specification

This command generates multiple FPM model variations by applying probability
distributions to spatial attributes as specified in a .variation file.

Each resulting model follows the format <floorplan_name>_<seed>.fpm and can be
further transformed into JSON-LD and other artefacts.

This command is equivalent to using TextX's CLI:

```
textx generate <variation model> --target fpm --variations <number> -o <output path>
```

This requires that the [FloorPlan DSL](https://github.com/secorolab/FloorPlan-DSL) is installed.

See https://github.com/secorolab/FloorPlan-DSL/blob/devel/docs/tutorials/variation.md
for more information on creating variation models.


Usage:

```bash
floorplan variation [OPTIONS]
```

## Options

### Required

- `-m`, `--model` (PATH)
    Path to the .variation model file.

### Optional

- `-n`, `--variations`, `--num-variations` (INT)
    Number of variations to generate.
    Default: `1`
- `-o`, `--output-path` (PATH)
    Output path for generated variations.
    Default: `.`


