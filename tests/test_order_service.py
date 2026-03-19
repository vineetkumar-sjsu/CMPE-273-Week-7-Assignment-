"""Unit tests for order service endpoints."""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


@pytest.fixture
def client():
    """Create a Flask test client for the order service."""
    from order_service import create_app
    app = create_app(port=9999, registry_url=None)
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


def test_get_orders(client):
    """GET /orders returns pre-seeded orders with instance metadata."""
    response = client.get('/orders')
    assert response.status_code == 200
    data = response.get_json()
    assert 'orders' in data
    assert len(data['orders']) == 3
    assert data['instance_id'] == 'order-service-9999'
    assert data['instance_port'] == 9999


def test_get_order_by_id(client):
    """GET /orders/<id> returns correct order for valid ID."""
    response = client.get('/orders/1')
    assert response.status_code == 200
    data = response.get_json()
    assert data['order']['id'] == 1
    assert 'item' in data['order']
    assert data['instance_id'] == 'order-service-9999'


def test_get_order_not_found(client):
    """GET /orders/<id> returns 404 for invalid ID."""
    response = client.get('/orders/999')
    assert response.status_code == 404
    data = response.get_json()
    assert data['error'] == 'Order not found'


def test_create_order(client):
    """POST /orders creates order, returns 201 with instance metadata."""
    response = client.post('/orders', json={
        'item': 'Keyboard',
        'quantity': 2,
        'customer': 'Alice'
    })
    assert response.status_code == 201
    data = response.get_json()
    assert data['order']['item'] == 'Keyboard'
    assert data['order']['quantity'] == 2
    assert data['order']['customer'] == 'Alice'
    assert 'id' in data['order']
    assert data['instance_id'] == 'order-service-9999'


def test_create_order_missing_fields(client):
    """POST /orders returns 400 for missing required fields."""
    response = client.post('/orders', json={'item': 'Keyboard'})
    assert response.status_code == 400
    data = response.get_json()
    assert 'error' in data


def test_health(client):
    """GET /health returns healthy status."""
    response = client.get('/health')
    assert response.status_code == 200
    data = response.get_json()
    assert data['status'] == 'healthy'
    assert data['instance_id'] == 'order-service-9999'
