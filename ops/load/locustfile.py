"""
Locust Load Testing Suite for Runwise Agent Service.

Simulates concurrent customer support traffic profiles:
- Liveness & Readiness probes (Kubernetes health checks)
- Prometheus metrics scraping
- Customer inquiries and order status checks
- Authenticated mutation attempts (cancellations)
"""

from __future__ import annotations

import random
import uuid
from locust import HttpUser, between, task


class CustomerSupportUser(HttpUser):
    """
    Simulated customer navigating the support service.
    Maintains a sticky session ID across turns to test session affinity.
    """

    wait_time = between(0.5, 2.0)

    def on_start(self) -> None:
        """Allocate a persistent session ID and customer identity."""
        self.session_id = f"load_sess_{uuid.uuid4().hex[:10]}"
        self.customer_id = random.choice(["CUST-101", "CUST-102", "CUST-103", "CUST-104", "CUST-105"])

    @task(4)
    def health_check(self) -> None:
        """Liveness probe: GET /healthz."""
        self.client.get("/healthz", name="GET /healthz")

    @task(2)
    def ready_check(self) -> None:
        """Readiness probe: GET /readyz (verifies DB & provider config)."""
        self.client.get("/readyz", name="GET /readyz")

    @task(1)
    def metrics_scrape(self) -> None:
        """Prometheus scraper: GET /metrics."""
        self.client.get("/metrics", name="GET /metrics")

    @task(5)
    def agent_inquiry(self) -> None:
        """Standard customer order status query: POST /v1/agent/run."""
        order_id = random.choice(["ORD-101", "ORD-102", "ORD-103", "ORD-104"])
        payload = {
            "session_id": self.session_id,
            "prompt": f"Hi, what is the current shipping status of order {order_id}?",
            "task_id": "load_inquiry",
            "customer_id": self.customer_id,
        }
        with self.client.post(
            "/v1/agent/run",
            json=payload,
            name="POST /v1/agent/run (Inquiry)",
            catch_response=True,
            timeout=20.0,
        ) as response:
            if response.status_code == 200:
                data = response.json()
                if "response" in data and data.get("response"):
                    response.success()
                else:
                    response.failure("Response payload missing 'response' field")
            elif response.status_code == 429:
                response.failure("Rate limited: HTTP 429 Too Many Requests")
            else:
                response.failure(f"HTTP {response.status_code}: {response.text[:100]}")

    @task(2)
    def agent_mutation(self) -> None:
        """Customer order cancellation request: POST /v1/agent/run."""
        order_id = random.choice(["ORD-101", "ORD-102", "ORD-103"])
        payload = {
            "session_id": self.session_id,
            "prompt": f"Please cancel order {order_id} immediately.",
            "task_id": "load_cancel",
            "customer_id": self.customer_id,
        }
        with self.client.post(
            "/v1/agent/run",
            json=payload,
            name="POST /v1/agent/run (Mutation)",
            catch_response=True,
            timeout=20.0,
        ) as response:
            if response.status_code == 200:
                response.success()
            elif response.status_code == 429:
                response.failure("Rate limited: HTTP 429")
            else:
                response.failure(f"HTTP {response.status_code}")
