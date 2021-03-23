# Github Actions Workflow Scripts

When 

```
run: |
    command 1
    command 2
    command 3
    # . . .
```

. . . gets too unwieldy for a yaml file, you can factor behavior into scripts. These
scripts are _only_ meant to be run via github actions, and may therefore directly depend
upon github actions environment variables.

Refer to github's 
[official documentation](https://docs.github.com/en/actions/reference/environment-variables) 
for Actions environment variables available to you.

Call these scripts in your workflow step's run command:

```
steps:
    - uses: actions/checkout@master
    - run: ./.github/scripts/script-name.sh
```

If the script you are writing should be called other times than during Github 
Actions, it belongs in the repository root's `scripts/` directory instead.
