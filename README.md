# uw-husky-directory
Maintained by UW-IT Identity & Access Management.

This README contains some basic getting started instructions.

For full documentation, refer to the [docs/](https://github.com/uwit-iam/uw-husky-directory/tree/main/docs) directory.

## Organization of this repository:

```
+ uw-husky-directory
| + .github     # Github CICD configuration and scripts
| + docker      # Dockerfiles
| | + compose   # docker-compose files
| + docs        # Documentation about using and maintaining this package
| + husky_directory  # Source code for the application
| | + templates      # jinja2 templates
| + static      # Static assets
| + tests       # Unit tests
```

# Getting Started with Development

This package comes with convenience scripts to set up your environment. They should be macos and linux compatible.
If you are working from a Windows machine, feel free to add similar scripts for that use case, or provide documentation 
on how to get started on Windows.

## Pre-requisites:

- Docker, with a running docker daemon
- Python, preferably 3+, to install poetry (if not already installed)

## Bootstrapping

Clone the repository:

```
git clone git@github.com:UWIT-IAM/uw-husky-directory
cd uw-husky-directory
```

Run the boostrapping script which:

- Makes sure [poetry](https://python-poetry.org/) is installed
- Installs dependencies for this package using poetry
- Creates a startup script in your virtualenv that you can (and should feel free to) edit

```
./scripts/bootstrap-dev-local.sh
```

Take a moment to read the output from the bootstrapper; there may be helpful information or other optional 
steps you can do.

Validate everything works by running the pre-push script which:

```
./scripts/pre-push.sh --no-commit --pro
```

You should see a message at the end reading:
 
> "🚢 Your commit looks good to go! 🌈"

This indicates everything works properly inside of a docker image.

# Key Dependencies

We are using [poetry](https://python-poetry.org/) as a dependency management tool. Poetry takes care of setting up 
virtual environments and installing dependencies. No more having to muck about with any of that yourself. It is 
_highly_ recommended to read poetry's documentation so you know its capabilities and commands, and how to add 
dependencies to the project the "right" way.

We also use [docker]() for testing and production use cases. Learn more about out how we use docker in 
[docs/docker.md](https://github.com/uwit-iam/uw-husky-directory/tree/main/docs/docker.md)

# Pre-push checks

You can rest easy knowing your code will probably pass its validation workflow by running the pre-push script. 
This script is responsible for checking the state of your repository, linting your code, building in image, and
running tests on that image.

This should be the last step before you push with the intent of receiving a code review. 

Running without arguments performs the full validation suite, and may amend your commit; if it passes validation,
your commit will also be amended with a little output from the workflow as a visual cue to your code reviewers.

```
./scripts/pre-push.sh
```

This full validation mode requires a clean branch; the intent is to validate that your code, exactly as it is now,
is ready for testing and review.

The `--no-commit` option will not amend your commit (but your commit will also not be validated). 

The `--test` option will run the full script even if certain conditions are not met; this is good for taking a look at 
the state of a change commit _before_ committing. This option implies `--no-commit`; you do not need to set both.

The `--incognito` behaves the same as normal validation, except it will not add a entry in your `.pre_push` cache. I'm 
not sure if this is useful, but people should have control over what gets preserved on their system.

Lastly, the `--pro` option limits the output of the script for people who just want the deets without any opinions
or helpful hints mixed in.
