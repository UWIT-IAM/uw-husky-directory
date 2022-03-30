# Tox

[tox] is a python virtual environment and task management system.
Tox can also manage dependencies, to some degree, but we do not use it for that.

To execute all code change validations, simply run `poetry run tox`.

This will:

- Clean up any previous test artifacts
- Reformat your code using `black`
- Lint your code using `flake8`
- Build your application using docker, via `./build-layers.sh`
- Test your code using `pytest`
