#!/bin/sh

# This runs validation checks and tests, outputting a summary of failures (if any).
# You can run this on your local machine by setting SRC_DIR=husky_directory and TST_DIR=tests before running it:
#   SRC_DIR=husky_directory TEST_DIR=tests ./scripts/validate-development-image.sh
# This
# You can also run yourself with:
# docker build -f docker/development-serverj .

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

CMD="pytest $TST_DIR"
echo $CMD
if ! $CMD
then
  PYTEST_ERR=1
  FAIL=1
fi

#black --check $TST_DIR  || (BLACK_TST_DIR_ERR=1 && FAIL=1) # Make sure our test code is blackened
#pytest $TST_DIR || (PYTEST_ERR=1 && FAIL=1)
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
