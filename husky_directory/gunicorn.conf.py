import os
from multiprocessing import cpu_count


def worker_exit(worker, server):
    worker.log.info(f"Server {server} shutting down . . .")


def max_workers():
    default_max = 2 * cpu_count() + 1
    return os.environ.get("GUNICORN_MAX_WORKERS", default_max)


def max_threads():
    default_max = 4
    return os.environ.get("GUNICORN_MAX_THREADS", default_max)


max_requests = 1000
bind = "0.0.0.0:8000"
worker_class = "gthread"
workers = max_workers()
threads = max_threads()
loglevel = os.environ.get("GUNICORN_LOG_LEVEL", "DEBUG")
reload = os.environ.get("FLASK_ENV") == "development"
preload_app = os.environ.get("FLASK_ENV") != "development"
