set -e
# Bootstraps a developer laptop by installing poetry as well as library dependencies (using poetry to do so).
# This takes one optional argument: a python interpreter path. you can use this to change which python interpreter
# is used to _install_ poetry. It won't have any effect on the virtual environment _created_ by poetry. if the
# default (python3.8) is not available on your system, provide a path to a python3 binary, for instance:
#     ./scripts/bootstrap-dev-local.sh ~/.pyenv/versions/3.7.7/bin/python
#
# Even though poetry can be installed using any version of python>=2.7, the
# actual directory poetry environment will require >=3.8 to be available on your system.
#
# Note that poetry creates virtual environments; you should already have created one before installing poetry.
# Poetry will be installed in ${HOME}/.poetry by default, but you can override this by setting
# the POETRY_HOME
# This will also amend your poetry virtualenv activate script to export some helpful environment
# variables by setting POETRY_HOME to someplace specific.

PYTHON=$1
POETRY_INSTALLER_DIR=${POETRY_INSTALLER_DIR:-/tmp}
POETRY_INSTALLER=${POETRY_INSTALLER_DIR}/get_poetry.py

test -z "${PYTHON}" && PYTHON="python3.8"
test -z "${POETRY_HOME}" && POETRY_HOME="${HOME}/.poetry"

if ! command -v "${PYTHON}" &>/dev/null
then
  echo "Cannot find ${PYTHON}. Please provide the path to a source binary, or make sure the executable is on your PATH."
  exit 1
fi

if ! command -v poetry &>/dev/null
then
  echo "poetry could not be found. Installing to ${POETRY_HOME} using '${PYTHON}'."
  set -x
  curl -sSL https://raw.githubusercontent.com/python-poetry/poetry/master/get-poetry.py > ${POETRY_INSTALLER}
  ${PYTHON} ${POETRY_INSTALLER} -y
  source "${POETRY_HOME}/env"
  set +x
  echo "Done. You can uninstall this with '${PYTHON} ${POETRY_INSTALLER} --uninstall'."
fi

# Install declared library dependencies
poetry env use "${PYTHON}"
poetry install
./scripts/install-build-scripts.sh
