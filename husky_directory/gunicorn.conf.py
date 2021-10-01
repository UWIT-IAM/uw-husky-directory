from gevent import monkey

monkey.patch_all()

import os  # noqa: E402
from multiprocessing import cpu_count  # noqa: E402
from prometheus_flask_exporter.multiprocess import (  # noqa: E402
    GunicornInternalPrometheusMetrics,
)

if not os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
    raise EnvironmentError("PROMETHEUS_MULTIPROC_DIR environment variable must be set!")


def worker_exit(worker, server):
    worker.log.info(f"Server {server} shutting down . . .")


def max_workers():
    default_max = 2 * cpu_count() + 1
    return os.environ.get("GUNICORN_MAX_WORKERS", default_max)


def child_exit(server, worker):
    GunicornInternalPrometheusMetrics.mark_process_dead_on_child_exit(worker.pid)


max_requests = 1000
bind = "0.0.0.0:8000"
worker_class = "gevent"
workers = max_workers()
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "DEBUG")
reload = os.environ.get("FLASK_ENV") == "development"
preload_app = os.environ.get("FLASK_ENV") != "development"
