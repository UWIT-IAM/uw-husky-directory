#!/usr/bin/env bash

pr_body="Beep boop! I'm a bot, here to make sure your dependencies are up to date! "
pr_body+="Everything looks good, I just need your approval to merge this "
pr_body+="change in to your main branch!"

source ./.build-scripts/sources/github-actions.sh

gh pr create \
  -B main \
  -b "${pr_body}" \
  -r tomthorogood \
  -r goulter \
  -r jdiverp \
  --fill

pr_number=$(gh pr list --json number -q '.[0].number')

set_ci_output pull-request-number "$pr_number"
