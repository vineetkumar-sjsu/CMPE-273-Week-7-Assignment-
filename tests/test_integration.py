"""
Integration tests — spin up registry + services, test full discovery flow.

These tests use real subprocess processes and HTTP calls.
They are slower than unit tests but verify the entire system works end-to-end.
"""
import pytest
import subprocess
import time
import requests
import signal
import os
import sys

BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
REGISTRY_PORT = 5051  # Use non-default port to avoid conflicts
SERVICE_PORT_1 = 8051
SERVICE_PORT_2 = 8052
REGISTRY_URL = f"http://localhost:{REGISTRY_PORT}"


def wait_for_health(url, timeout=10):
    """Poll a health endpoint until it responds or timeout."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{url}/health", timeout=2)
            if resp.status_code == 200:
                return True
        except requests.exceptions.ConnectionError:
            pass
        time.sleep(0.5)
    return False


def wait_for_service_count(registry_url, service_name, expected_count, timeout=15):
    """Poll the registry until the expected number of instances are registered."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            resp = requests.get(f"{registry_url}/discover/{service_name}", timeout=2)
            if resp.status_code == 200:
                data = resp.json()
                if data.get('count', 0) >= expected_count:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


@pytest.fixture(scope="module")
def system():
    """Start registry and 2 order-service instances for all tests in this module."""
    procs = []

    # Start registry on non-default port via REGISTRY_PORT env var
    registry_env = os.environ.copy()
    registry_env['REGISTRY_PORT'] = str(REGISTRY_PORT)
    registry_proc = subprocess.Popen(
        [sys.executable, "service_registry.py"],
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=registry_env
    )
    procs.append(registry_proc)

    # Wait for registry
    assert wait_for_health(REGISTRY_URL), "Registry failed to start"

    # Start service instance 1
    svc1_proc = subprocess.Popen(
        [sys.executable, "order_service.py", "--port", str(SERVICE_PORT_1),
         "--registry", REGISTRY_URL],
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    procs.append(svc1_proc)

    # Start service instance 2
    svc2_proc = subprocess.Popen(
        [sys.executable, "order_service.py", "--port", str(SERVICE_PORT_2),
         "--registry", REGISTRY_URL],
        cwd=BASE_DIR,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    procs.append(svc2_proc)

    # Wait for both to register
    assert wait_for_service_count(REGISTRY_URL, "order-service", 2), \
        "Services failed to register within timeout"

    yield {
        "registry_url": REGISTRY_URL,
        "registry_proc": registry_proc,
        "svc1_proc": svc1_proc,
        "svc2_proc": svc2_proc,
        "svc1_port": SERVICE_PORT_1,
        "svc2_port": SERVICE_PORT_2,
    }

    # Cleanup
    for proc in procs:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()


def test_registry_health(system):
    """Registry responds to health check."""
    resp = requests.get(f"{system['registry_url']}/health")
    assert resp.status_code == 200
    assert resp.json()['status'] == 'healthy'


def test_service_registration(system):
    """Both instances appear in /services."""
    resp = requests.get(f"{system['registry_url']}/services")
    assert resp.status_code == 200
    data = resp.json()
    assert 'order-service' in data['services']
    assert data['services']['order-service']['active_instances'] == 2


def test_service_discovery(system):
    """GET /discover/order-service returns 2 instances."""
    resp = requests.get(f"{system['registry_url']}/discover/order-service")
    assert resp.status_code == 200
    data = resp.json()
    assert data['count'] == 2
    addresses = [inst['address'] for inst in data['instances']]
    assert f"http://localhost:{system['svc1_port']}" in addresses
    assert f"http://localhost:{system['svc2_port']}" in addresses


def test_client_random_routing(system):
    """Multiple requests are distributed across both instances."""
    import random

    instances_hit = set()
    for _ in range(20):
        # Discover
        resp = requests.get(f"{system['registry_url']}/discover/order-service")
        data = resp.json()
        addresses = [inst['address'] for inst in data['instances']]

        # Pick random
        selected = random.choice(addresses)

        # Call
        resp = requests.get(f"{selected}/orders")
        result = resp.json()
        instances_hit.add(result['instance_id'])

    # With 20 random picks from 2 options, probability of all going to one
    # is 2/2^20 ~ 0.0002%. If this fails, it's almost certainly a real bug.
    assert len(instances_hit) == 2, \
        f"Expected both instances to be hit, but only got: {instances_hit}"


def test_individual_instance_responds(system):
    """Each instance returns its own instance_id."""
    resp1 = requests.get(f"http://localhost:{system['svc1_port']}/orders")
    assert resp1.status_code == 200
    assert resp1.json()['instance_id'] == f"order-service-{system['svc1_port']}"

    resp2 = requests.get(f"http://localhost:{system['svc2_port']}/orders")
    assert resp2.status_code == 200
    assert resp2.json()['instance_id'] == f"order-service-{system['svc2_port']}"


def test_z_graceful_deregistration(system):
    """Kill one instance, verify it deregisters from registry.

    Named with 'z_' prefix so it runs last (module-scoped fixture means
    killing svc2 would affect other tests if they ran after).
    """
    system['svc2_proc'].terminate()
    try:
        system['svc2_proc'].wait(timeout=5)
    except subprocess.TimeoutExpired:
        system['svc2_proc'].kill()
    time.sleep(3)

    resp = requests.get(f"{system['registry_url']}/discover/order-service")
    data = resp.json()
    addresses = [inst['address'] for inst in data['instances']]
    assert f"http://localhost:{system['svc1_port']}" in addresses
    assert f"http://localhost:{system['svc2_port']}" not in addresses
