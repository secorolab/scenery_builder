---
title: Shell Autocompletion
parent: CLI
---

# Shell Autocompletion

These instructions are based on the [shell completion](https://click.palletsprojects.com/en/stable/shell-completion/) docs from Click.

## Zsh

Save the script somewhere:

```zsh
_FLOORPLAN_COMPLETE=zsh_source floorplan > ~/.floorplan-complete.zsh
```

Then add it to your `.zshrc`:

```zsh
echo 'source ~/.floorplan-complete.zsh' >> ~/.zshrc
```
