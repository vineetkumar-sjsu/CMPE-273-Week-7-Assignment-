# CMPE-273 Week 7: Naming and Service Discovery Assignment

**Name:** Vineet Kumar
**ID:** 019140433

A microservice system that uses a central service registry for service discovery. Two instances of an order service register themselves with the registry, and a client discovers them at runtime and routes requests to a random instance.

## Architecture

![Architecture](docs/architecture.png)

```
                  Service Registry (Port 5001)
                   /                    \
            register +               register +
            heartbeat                 heartbeat
                /                        \
    Order Service (8001)       Order Service (8002)
                \                        /
                 \     random pick      /
                  \        |           /
                   Discovery Client
```

1. The registry starts first and listens on port 5001
2. Two order service instances start on ports 8001 and 8002, each registers itself with the registry and starts sending heartbeats every 10 seconds
3. The client calls `GET /discover/order-service` to get all active instances, picks one at random, and sends the request
4. If an instance stops sending heartbeats for 30 seconds, the registry removes it

## Prerequisites

- Python 3.8+
- pip

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Running the Demo

The easiest way to see everything in action:

```bash
chmod +x week-7-demo.sh
./week-7-demo.sh
```

This starts the registry, both service instances, runs the discovery client, and demonstrates graceful shutdown.

## Running Manually

Open four separate terminals (make sure venv is activated in each):

**Terminal 1 - Registry:**
```bash
python3 service_registry.py
```

**Terminal 2 - Order Service Instance 1:**
```bash
python3 order_service.py --port 8001
```

**Terminal 3 - Order Service Instance 2:**
```bash
python3 order_service.py --port 8002
```

**Terminal 4 - Client:**
```bash
python3 client.py --rounds 10
```

## Proof of Functionality

### 1. Both Instances Register Successfully

After starting both order service instances, querying the registry shows 2 active instances:

```
$ curl -s http://localhost:5001/services | python3 -m json.tool
{
    "services": {
        "order-service": {
            "active_instances": 2,
            "total_instances": 2
        }
    },
    "total_services": 1
}
```

### 2. Discovery Returns Both Instances

```
$ curl -s http://localhost:5001/discover/order-service | python3 -m json.tool
{
    "count": 2,
    "instances": [
        {
            "address": "http://localhost:8001",
            "uptime_seconds": 3.888687
        },
        {
            "address": "http://localhost:8002",
            "uptime_seconds": 2.912409
        }
    ],
    "service": "order-service"
}
```

### 3. Client Randomly Distributes Requests

Running the client for 10 rounds shows requests going to both instances:

```
$ python3 client.py --rounds 10

=== Round 1/10 ===
Discovered 2 instance(s): ['http://localhost:8001', 'http://localhost:8002']
Selected: http://localhost:8002
Response from instance: order-service-8002

=== Round 2/10 ===
Selected: http://localhost:8001
Response from instance: order-service-8001

...

============================================================
DISTRIBUTION SUMMARY
============================================================
  order-service-8001: 4/10 requests (40%)
  order-service-8002: 6/10 requests (60%)
```

Both instances receive traffic, confirming random load distribution works.

### 4. Graceful Shutdown

When an instance is stopped (Ctrl+C or SIGTERM), it deregisters from the registry. After stopping instance 2:

```
$ curl -s http://localhost:5001/discover/order-service | python3 -m json.tool
{
    "count": 1,
    "instances": [
        {
            "address": "http://localhost:8001",
            "uptime_seconds": 45.2
        }
    ],
    "service": "order-service"
}
```

Only instance 1 remains.

## Tests

```bash
source venv/bin/activate
pytest tests/test_order_service.py -v
```

Output:
```
tests/test_order_service.py::test_get_orders PASSED
tests/test_order_service.py::test_get_order_by_id PASSED
tests/test_order_service.py::test_get_order_not_found PASSED
tests/test_order_service.py::test_create_order PASSED
tests/test_order_service.py::test_create_order_missing_fields PASSED
tests/test_order_service.py::test_health PASSED

6 passed
```

## Files

| File | Purpose |
|------|---------|
| `service_registry.py` | Central registry server (based on professor's sample) |
| `order_service.py` | Order microservice with auto-registration |
| `client.py` | Discovery client with random instance selection |
| `week-7-demo.sh` | One-click demo script |
| `tests/` | Unit tests for the order service |
| `docs/architecture.png` | Architecture diagram |
