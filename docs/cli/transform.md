---
layout: default
title: transform
parent: floorplan
---

# transform

Transform an FPM model into JSON-LD

This command is equivalent to using TextX's CLI to transform the fpm model:

```
textx generate --target json-ld --overwrite <model.fpm> -o <output path>
```

This requires that the [FloorPlan DSL](https://github.com/secorolab/FloorPlan-DSL) is installed.


Usage:

```bash
floorplan transform [OPTIONS]
```

## Options

### Required

- `-m`, `--model` (PATH)
    Path to the fpm model to transform into JSON-LD.

### Optional

- `-o`, `--output-path` (PATH)
    Output path for generated artefacts.
    Default: `.`


