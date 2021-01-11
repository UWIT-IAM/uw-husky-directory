# Useful tips and snippets

This is not a substitute for [official poetry documentation], but a reference for 
commonly used commands, etc.

## Poetry's virtual environment

Use `poetry shell`.

You may be used to running `source venv/bin/activate` to work inside of your virtual 
environment. This is not necessary. 

However, if you need to know about your virtual environment (for example, to 
configure your project interpreter in your IDE), you can get the path by using the 
command:

```bash
poetry env info
```

The output will contain a `Path` field.


## Dependency management

Please refer to the official [poetry dependency management] documentation, which 
essentially encompasses the following commands:
- `add`
- `show`
- `remove`

### Adding a new python dependency

First, consider whether your dependency needs to be available at runtime, or if it 
is only used in testing or development. 

If it is a _runtime_ dependency, use the command: `poetry add dependency-name`

If it is a _development_ or _testing_ dependency, use the 
command: `poetry add -D dependency-name`

If you need to change this, you can edit [pyproject.toml].


[official poetry documentation]: https://python-poetry.org/docs/
[poetry dependency management]: https://python-poetry.org/docs/cli/#add
[pyproject.toml]: http://github.com/UWIT-IAM/uw-husky-directory/tree/main/pyproject.toml
