---
title: Config file
layout: default
parent: CLI
---

# Using a configuration file

When generating multiple artefacts, parametrizing the generation can be cumbersome if one needs to customize multiple parameters in each subcommand.
The [generate](generate.md) command can use the `--config` option as an alternative to passing arguments to individual subcommands.
It must be written using [TOML](https://toml.io/en/), and follow the nesting structure of the commands and their arguments.

For example, to generate the tasks for a given model, and parametrizing the distance to 0.9 m, one would run:

```shell
floorplan generate --inputs model/json-ld --outputs gen/model/tasks tasks --dist-to-corner 0.9
```

The same result can be achieved using the following config file:

```toml
[generate]
inputs = "model/json-ld"
outputs = "gen/model/tasks"

[generate.tasks] # Sections should follow the pattern [command.subcommand]
dist_to_corner = 0.7
```

Note how the options are scoped to the command being used (i.e, `generate` has the options `inputs` and `outputs`). 
To add arguments for subcommands, then we reference the subsection in the form `command.subcommand`.
Now to run the command, we pass the `--config` option to the generate command instead:

```shell
floorplan generate --config config.toml tasks
```

An example config file with all the supported options can be found [here](https://github.com/secorolab/scenery_builder/blob/devel/config/config.toml).