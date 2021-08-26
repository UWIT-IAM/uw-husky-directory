import gevent.monkey

gevent.monkey.patch_all()

worker_class = "gevent"


def worker_exit(worker, server):
    worker.log.info(f"Server {server} shutting down . . .")
