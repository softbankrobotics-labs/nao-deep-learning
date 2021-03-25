import time
import functools
import Queue
import threading
import qi


logger = qi.logging.Logger('deep_nao.worker')


class Worker:
    """Worker allows you to queue tasks on its list of tasks, and then it
    execute them one after another until its task list is empty.

    """

    def __init__(self, name):
        self.tasks = Queue.Queue(0)
        self.running = False
        self.lock = threading.Lock()
        self.name = name

    def __repr__(self):
        return "Worker(%s)" % self.name

    def queue_size(self):
        return self.tasks.qsize()

    def add(self, function):
        """Add a new task on the task list"""
        logger.verbose("%s add task." % self)
        self.tasks.put(function)
        with self.lock:
            if not self.running:
                self.running = True
                qi.async(self._run)

    def _run(self):
        """Excecute the tasks on the task list"""
        logger.verbose("%s start running." % self)
        try:
            while True:
                with self.lock:
                    try:
                        function = self.tasks.get_nowait()
                    except Queue.Empty:
                        self.running = False
                        break
                try:
                    function()
                finally:
                    self.tasks.task_done()
            logger.verbose("%s done running." % self)
        except:
            logger.error(traceback.format_exc())

    workers = {}

    @classmethod
    def get_worker(cls, worker_id):
        """Get or create a Worker indentified with worker_id."""
        if worker_id not in cls.workers:
            cls.workers[worker_id] = cls(worker_id)
        return cls.workers[worker_id]


def _cancel(promise):
    promise.setCanceled()


def async(worker_id, expire_delay=-1, max_queue=-1):
    def wrap(method):
        @functools.wraps(method)
        def wrapper(self, *args, **kwds):
            promise = qi.Promise(_cancel)
            future = promise.future()
            queued_tmstp = time.time()

            def runner():
                if not promise.future().isCanceled():
                    try:
                        exec_tmstp = time.time()
                        if expire_delay != -1 and exec_tmstp - queued_tmstp > expire_delay:
                            logger.info("Expired %s%s, do not exec" % (method.__name__, args))
                            promise.setError("Could not exec method, it expired")
                            return
                        res = method(self, *args, **kwds)
                        if not promise.future().isCanceled():
                            promise.setValue(res)
                    except Exception, e:
                        logger.error(traceback.format_exc())
                        if not promise.future().isCanceled():
                            promise.setError(str(e))
            worker = Worker.get_worker(worker_id)
            if max_queue == -1 or max_queue >= worker.queue_size():
                worker.add(runner)
            else:
                promise.setError("Could not perform task. Queue is full.")
            if not hasattr(self, "_future"):
                self._futures = []
            self._futures.append(future)
            return future
        return wrapper
    return wrap
