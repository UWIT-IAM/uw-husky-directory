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
| | + blueprints     # View/API blueprints
| | + models         # API models
| | + services       # Application/back-end services
| | + settings       # Application settings (dotenv and yml files)
| | + templates      # jinja2 templates
| + static      # Static assets
| + tests       # Unit tests
```

# Getting Started with Development

This package comes with convenience scripts to set up your environment. They should be macos and linux compatible.
If you are working from a Windows machine, feel free to add similar scripts for that use case, or provide documentation 
on how to get started on Windows.

## Pre-requisites:

- Python, preferably 3+, to install poetry (if not already installed)
- [Poetry](https://python-poetry.org)
- Docker desktop, with a running docker daemon (required for deployments and selenium tests)
- Python 3.8+, somewhere on your system, so that poetry can link your virtualenv to 
  the right python binary for the application. (For instance, at `~/.pyenv/versions/3.8.6`)

Validate that everything works by running `poetry run tox`.

# Build Dependencies

## poetry

- Poetry manages our dependencies and application version. (For more, refer to 
  [docs/poetry](docs/poetry.md))
- Docker builds our application to prepare it for deployment, and docker-compose 
  runs our selenium tests. (For more, refer to [docs/docker](docs/docker.md)).
- Tox invokes build and testing tasks. (For more, refer to [docs/tox](docs/tox.md))

#
