import threading
from server.job_queue import ThreadJobQueue

def test_thread_job_queue_runs_fn_off_thread():
    done = threading.Event()
    seen = {}
    def work():
        seen["tid"] = threading.get_ident()
        done.set()
    ThreadJobQueue().submit(work)
    assert done.wait(timeout=5)
    assert seen["tid"] != threading.get_ident()
