# Workflows

The `.yml` files in this directory are used by Github Actions to run workflows.
See [Github Actions documentation] if you want to learn more about how these work.

This document will discuss the workflow intents and oddities, as needed.

## scheduled-maintenance

The [scheduled-maintenance] workflow runs on a weekly schedule and
is responsible for keeping our dependencies and runtime OS patched.

Notifications for this workflow are sent to the `#cloud-native-directory` 
slack channel. 

### Artifacts

As a result of this workflow, the following artifacts will be created:

1. A git tag of the new application version (e.g., 1.2.3)
2. A dependency image tagged both with its sha256 fingerprint as well as the
   pseduo-semver datetime "version" (e.g., 255.15.7, for a build that ran at 3:07pm 
   on September 12).
3. An application image tagged with its new patch version  (e.g., 1.2.3)
4. A pull request that can be merged without careful review.


### Testing

You can test this workflow by pushing to the `run-scheduled-maintenance-workflow` 
branch. When doing this, the git tag will be `0.0.0-testing`
and the application image will have a prerelease version (1.2.2-alpha.0),
instead of a patch version (1.2.3). This will prevent tests from having any
lasting effects on our tag history.

### FAQs

> Should I approve this automatic pull request?

Yes! You should! In the future, this process too will be automated. The pull request
will not be created if the tests fail, so you should only see a PR created if 
everything worked.

> What if this workflow fails?

This workflow only creates artifacts if all tests are successful. A failure
indicates that one of the dependencies that was updated is not compatible
with our current application. You may ignore this change and hope that 
the next week's sync resolves the problem, or you can investigate to 
discover the cause and remediate it. If your investigations lead you to 
believe that a certain dependency should not be updated until further
notice, keep reading...

> What if I don't want certain packages to update?

You can pin a specific version in `pyproject.toml`. If the version
guidance is exact, the `poetry lock` command will not find
any new updates (e.g., change `^1.2` to `1.2.3`).


[Github Actions documentation]: https://... 
[scheduled-maintenance]: https://...
