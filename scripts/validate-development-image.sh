#!/bin/sh

# This runs validation checks and tests, outputting a summary of failures (if any).
# You can run this on your local machine instead of via docker:
#   SRC_DIR=husky_directory TEST_DIR=tests ./scripts/validate-development-image.sh

SRC_DIR=${SRC_DIR:-/app}
TST_DIR=${TST_DIR:-/tests}
# Make sure our source code is blackened
CMD="black --check $SRC_DIR"
echo $CMD
if ! $CMD
then
  BLACK_SRC_DIR_ERR=1
  FAIL=1
fi
CMD="black --check $TST_DIR"
echo $CMD
if ! $CMD
then
  BLACK_TST_DIR_ERR=1
  FAIL=1
fi

CMD="pytest $TST_DIR --cov ${SRC_DIR}/husky_directory --cov-fail-under 95"
echo $CMD
if ! $CMD
then
  PYTEST_ERR=1
  FAIL=1
fi

CMD="flake8 /app/husky_directory /tests --max-line-length=119"
echo $CMD
if ! $CMD
then
  FLAKE8_ERR=1
  FAIL=1
fi

if test -n "$FAIL"
then
  echo "**========================================**"
  echo "|| --------- VALIDATION FAILED ---------- ||"
  echo "**========================================**"
  if test -n "$BLACK_SRC_DIR_ERR"
  then
    echo " * Expected $SRC_DIR to be blackened."
    echo "   Run 'black $SRC_DIR' and try again."
    echo "**========================================**"
  fi
  if test -n "$BLACK_TST_DIR_ERR"
  then
    echo " * Expected $TST_DIR to be blackened."
    echo "   Run 'black $TST_DIR' and try again."
    echo "**========================================**"
  fi
  if test -n "$FLAKE8_ERR"
  then
    echo " * Expected flake8 to succeed. "
    echo "   Review output and correct errors, "
    echo "   then try again."
    echo "**========================================**"
  fi
  if test -n "$PYTEST_ERR"
  then
    echo " * Pytest failed. Run 'pytest' "
    echo "   to find and fix problems. "
    echo "**========================================**"
  fi
  exit 1
fi

  echo "**=========================================**"
  echo "|| --------- VALIDATION SUCCESS ---------- ||"
  echo "**=========================================**"
