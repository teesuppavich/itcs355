import threading
from collections import deque

from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

WINDOW_SIZE = 500
TRACKED_FEATURES = ("temp_c",)
LATENCY_BUCKETS_MS = (5, 10, 25, 50, 75, 100, 150, 200, 300, 500, 1000, 2000)

REQUESTS = Counter(
    "http_requests_total",
    "Requests to prediction routes",
    ["method", "path", "status_class"],
)
LATENCY = Histogram(
    "request_latency_ms",
    "Latency of prediction routes in milliseconds",
    buckets=LATENCY_BUCKETS_MS,
)
MODEL_VERSION = Gauge(
    "model_version_info",
    "Model version in production, value is always 1",
    ["version"],
)
FEATURE_MEAN = Gauge(
    "feature_rolling_mean",
    "Mean of the last WINDOW_SIZE scored values of a feature",
    ["feature"],
)

for _status_class in ("2xx", "4xx", "5xx"):
    REQUESTS.labels("POST", "/predict", _status_class)

_lock = threading.Lock()
_windows = {name: deque(maxlen=WINDOW_SIZE) for name in TRACKED_FEATURES}


def record_request(method, path, status, latency_ms):
    if not path.startswith("/predict"):
        return
    REQUESTS.labels(method, path, f"{status // 100}xx").inc()
    LATENCY.observe(latency_ms)


def observe_features(rows):
    with _lock:
        for name, window in _windows.items():
            for row in rows:
                value = row.get(name)
                if value is not None:
                    window.append(float(value))
            if window:
                FEATURE_MEAN.labels(name).set(sum(window) / len(window))


def set_version(version):
    MODEL_VERSION.clear()
    MODEL_VERSION.labels(str(version)).set(1)


def render():
    return generate_latest(), CONTENT_TYPE_LATEST
