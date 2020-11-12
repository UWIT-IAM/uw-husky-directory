set -e
# Bootstraps a developer laptop by installing poetry as well as library dependencies (using poetry to do so).
# This takes one optional argument: a python interpreter path. You can use this to change which python interpreter
# is used to _install_ poetry. It won't have any effect on the virtual environment _created_ by poetry. If the
# default (python3.8) is not available on your system, provide a path to a python3 binary, for instance:
#     ./scripts/bootstrap-dev-local.sh ~/.pyenv/versions/3.7.7/bin/python
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
poetry install

VIRTUAL_ENV=$(poetry env list --full-path 2>/dev/null | cut -f1 -d\ )
LOCAL=$(pwd)
STARTUP=${VIRTUAL_ENV}/.envrc

echo "Generating your virtualenv startups script: ${STARTUP}"

echo "# This file sets environment variables for the uw-husky-directory developer virtual environment." > ${STARTUP}
echo "# Feel free to edit this as desired; it will be sourced every time your virtualenv is activated." >> ${STARTUP}
echo "# To re-generate this at anytime, simply re-run this script." >> ${STARTUP}
echo "" >> ${STARTUP}
echo "# Sets your personal image suffix for using \`docker push ${PERSONAL_IMAGE}\`" >> ${STARTUP}
echo "export PERSONAL_IMAGE_SUFFIX=${USER}" >> ${STARTUP}
echo "export VENV_STARTUP=${STARTUP}" >> ${STARTUP}
echo "# Always sources .pre_push env variables from your last successful pre-push validation, if it exists." >> ${STARTUP}
echo "test -e $LOCAL/.pre_push && source $LOCAL/.pre_push/last" >> ${STARTUP}

echo "source ${STARTUP}" >> ${VIRTUAL_ENV}/bin/activate

echo "Added ${STARTUP} to virtualenv activate script. Edit that to do any setup you want when your virtualenv is activated."
echo "(You may want to edit it to set your PERSONAL_IMAGE_SUFFIX to start, so that it matches your UW netid)"
echo "The VENV_STARTUP environment variable is included, so you can easily access this file to edit it."
