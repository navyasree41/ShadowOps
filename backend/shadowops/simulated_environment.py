from typing import Any


SERVICES = {
    "checkout-service": {
        "health": {"status": "degraded", "replicas_ready": 3, "replicas_total": 3, "uptime_percent": 99.2},
        "metrics": {
            "window": "last 5 minutes",
            "request_rate_rps": 1840,
            "error_rate_percent": 87.0,
            "http_503_rate_percent": 84.6,
            "latency_p95_ms": 8420,
            "db_pool_used": 100,
            "db_pool_capacity": 100,
            "db_waiters": 42,
            "cpu_percent": 61,
            "memory_percent": 74,
        },
        "logs": [
            {"timestamp": "2026-09-29T10:14:02Z", "level": "ERROR", "message": "upstream database acquire timeout after 5000ms", "count": 381},
            {"timestamp": "2026-09-29T10:14:08Z", "level": "ERROR", "message": "POST /api/checkout returned 503; connection pool exhausted", "count": 294},
            {"timestamp": "2026-09-29T10:14:13Z", "level": "WARN", "message": "database pool at max capacity; 42 requests waiting", "count": 42},
        ],
        "deployments": [
            {"timestamp": "2026-09-29T09:42:11Z", "version": "checkout-2.14.3", "result": "succeeded", "change": "Cart tax calculation optimization"},
            {"timestamp": "2026-09-28T16:08:44Z", "version": "checkout-2.14.2", "result": "succeeded", "change": "Database pool default raised from 80 to 100"},
        ],
        "dependencies": [
            {"name": "postgres-primary", "status": "degraded", "latency_p95_ms": 690, "detail": "Connection acquisition queue elevated; database itself accepts connections."},
            {"name": "redis-checkout", "status": "healthy", "latency_p95_ms": 3, "detail": "Cache hit rate 94.1%; no elevated errors."},
            {"name": "payment-service", "status": "healthy", "latency_p95_ms": 118, "detail": "No correlated payment errors."},
        ],
    },
    "payment-service": {
        "health": {"status": "healthy", "replicas_ready": 4, "replicas_total": 4, "uptime_percent": 99.98},
        "metrics": {"window": "last 5 minutes", "request_rate_rps": 620, "error_rate_percent": 0.8, "latency_p95_ms": 214, "cpu_percent": 48, "memory_percent": 63},
        "logs": [{"timestamp": "2026-09-29T10:14:05Z", "level": "INFO", "message": "payment authorization completed", "count": 619}],
        "deployments": [{"timestamp": "2026-09-29T08:15:20Z", "version": "payment-5.7.1", "result": "succeeded", "change": "Updated provider retry backoff"}],
        "dependencies": [{"name": "card-gateway", "status": "healthy", "latency_p95_ms": 142, "detail": "Authorization success rate 99.7%."}],
    },
    "order-service": {
        "health": {"status": "healthy", "replicas_ready": 5, "replicas_total": 5, "uptime_percent": 99.96},
        "metrics": {"window": "last 5 minutes", "request_rate_rps": 1210, "error_rate_percent": 0.4, "latency_p95_ms": 176, "cpu_percent": 52, "memory_percent": 68, "queue_depth": 82},
        "logs": [{"timestamp": "2026-09-29T10:13:55Z", "level": "INFO", "message": "order persisted and event published", "count": 1204}],
        "deployments": [{"timestamp": "2026-09-29T07:52:03Z", "version": "orders-3.9.0", "result": "succeeded", "change": "Added idempotency key validation"}],
        "dependencies": [{"name": "orders-db", "status": "healthy", "latency_p95_ms": 31, "detail": "Replication lag 18ms."}, {"name": "orders-events", "status": "healthy", "latency_p95_ms": 12, "detail": "Consumer lag 82 messages."}],
    },
    "auth-service": {
        "health": {"status": "healthy", "replicas_ready": 3, "replicas_total": 3, "uptime_percent": 99.99},
        "metrics": {"window": "last 5 minutes", "request_rate_rps": 970, "error_rate_percent": 0.1, "latency_p95_ms": 67, "cpu_percent": 29, "memory_percent": 44},
        "logs": [{"timestamp": "2026-09-29T10:14:01Z", "level": "INFO", "message": "token validation completed", "count": 969}],
        "deployments": [{"timestamp": "2026-09-28T18:31:09Z", "version": "auth-1.22.0", "result": "succeeded", "change": "Rotated signing key with overlap"}],
        "dependencies": [{"name": "identity-postgres", "status": "healthy", "latency_p95_ms": 24, "detail": "No authentication database errors."}],
    },
    "notification-service": {
        "health": {"status": "degraded", "replicas_ready": 2, "replicas_total": 3, "uptime_percent": 98.7},
        "metrics": {"window": "last 5 minutes", "request_rate_rps": 380, "error_rate_percent": 3.2, "latency_p95_ms": 340, "cpu_percent": 73, "memory_percent": 82, "queue_depth": 18420},
        "logs": [{"timestamp": "2026-09-29T10:14:09Z", "level": "WARN", "message": "email worker retrying provider request; queue backlog increasing", "count": 1612}],
        "deployments": [{"timestamp": "2026-09-29T09:05:39Z", "version": "notify-4.2.6", "result": "succeeded", "change": "Raised email concurrency from 12 to 20"}],
        "dependencies": [{"name": "mail-provider", "status": "degraded", "latency_p95_ms": 2400, "detail": "Provider rate-limit responses at 6.4%."}],
    },
}


def service_health(service: str) -> dict[str, Any]:
    return {"service": service, **SERVICES[service]["health"]}


def service_metrics(service: str) -> dict[str, Any]:
    return {"service": service, **SERVICES[service]["metrics"]}


def service_logs(service: str) -> dict[str, Any]:
    return {"service": service, "entries": SERVICES[service]["logs"]}


def deployment_history(service: str) -> dict[str, Any]:
    return {"service": service, "deployments": SERVICES[service]["deployments"]}


def dependency_health(service: str) -> dict[str, Any]:
    return {"service": service, "dependencies": SERVICES[service]["dependencies"]}
