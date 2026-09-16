from pathlib import Path
from time import perf_counter


class SlidingWindowRateLimiter:
    """Monotonically timed sliding-window rate limiter per client."""

    def __init__(self, maximum_requests, window_seconds):
        self.maximum_requests = maximum_requests
        self.window_seconds = window_seconds
        self.request_times = {}

    def is_allowed(self, client_key, current_time):
        times = self.request_times.get(client_key, [])
        cutoff = current_time - self.window_seconds
        surviving = [t for t in times if t > cutoff]

        if len(surviving) >= self.maximum_requests:
            self.request_times[client_key] = surviving
            return False

        surviving.append(current_time)
        self.request_times[client_key] = surviving
        return True


class RequestLogger:
    """Callable middleware logging HTTP requests with status and latency."""

    def __init__(self, log_file_path):
        self.log_file_path = Path(log_file_path)
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)

    async def __call__(self, request, call_next):
        start = perf_counter()
        response = await call_next(request)
        duration_ms = (perf_counter() - start) * 1000.0
        line = f"{request.method} {request.url.path} {response.status_code} {duration_ms:.1f}ms\n"
        with open(self.log_file_path, "a", encoding="utf-8") as f:
            f.write(line)
        return response


if __name__ == "__main__":
    limiter = SlidingWindowRateLimiter(2, 60)
    print("attempt 1 allowed:", limiter.is_allowed("test", 10.0))
    print("attempt 2 allowed:", limiter.is_allowed("test", 11.0))
    print("attempt 3 allowed:", limiter.is_allowed("test", 12.0))
    print("attempt 4 allowed:", limiter.is_allowed("test", 13.0))
    print("after the window:", limiter.is_allowed("test", 75.0))
