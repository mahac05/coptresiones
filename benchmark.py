import time
from core.service import _SimpleThreadPool

def benchmark():
    # We use 1000 workers to magnify the CPU overhead of waking up every 0.5s
    pool = _SimpleThreadPool(max_workers=1000)

    start_time = time.process_time()
    start_perf = time.perf_counter()

    # Wait for 10 seconds
    time.sleep(10)

    end_time = time.process_time()
    end_perf = time.perf_counter()

    pool.shutdown(wait=True)

    print(f"Elapsed real time: {end_perf - start_perf:.4f}s")
    print(f"CPU time used: {end_time - start_time:.4f}s")

if __name__ == '__main__':
    benchmark()
