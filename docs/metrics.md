# Metrics

This application is configured to export prometheus metrics.
These metrics are available from the `/metrics` url. 
If the `PROMETHEUS_USERNAME` and `PROMETHEUS_PASSWORD` environment 
variables are set, the `/metrics` url will require HTTP Bsic Auth using those
values. 

If you run `./scripts/run-development-server.sh --compose`, you can test
prometheus yourself using the username `admin` and the password `supersecret`. 

When running in a kubernetes cluster, these variables are set by our cluster 
configuration. See the 
[cluster config repository](https://www.github.com/uwit-iam/gcp-k8), which contains
the `uw-directory` configuration for each of our clusters.

We currently only export default metrics; more are coming as part of EDS-600.

## Viewing metrics

All metrics are prefixed with `uw_directory`, so you can search
for them in whatever prometheus instance suits your needs.

When running locally via `run-development-server.sh --compose`, 
the prometheus web UI is located at `localhost:9000`.
