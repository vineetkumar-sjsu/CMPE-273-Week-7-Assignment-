"""
Order Service — A microservice that serves order data.

Registers with a service registry on startup, sends periodic heartbeats,
and deregisters on shutdown. Each response includes instance metadata
so clients can verify which instance handled the request.

Usage:
    python order_service.py --port 8001
    python order_service.py --port 8002 --registry http://localhost:5001
"""

from flask import Flask, request, jsonify
from datetime import datetime
import argparse
import requests as http_requests
import threading
import signal
import sys
import time

# --- Sample Data ---

SEED_ORDERS = [
    {"id": 1, "item": "Laptop", "quantity": 1, "customer": "John", "status": "shipped"},
    {"id": 2, "item": "Mouse", "quantity": 3, "customer": "Jane", "status": "processing"},
    {"id": 3, "item": "Monitor", "quantity": 1, "customer": "Bob", "status": "delivered"},
]


def create_app(port, registry_url=None):
    """
    Factory function to create the Flask app.

    Args:
        port: The port this instance runs on.
        registry_url: URL of the service registry (None to skip registration).
    """
    app = Flask(__name__)
    app.config['PORT'] = port
    app.config['INSTANCE_ID'] = f"order-service-{port}"
    app.config['REGISTRY_URL'] = registry_url

    # Each instance gets its own copy of orders
    orders = [dict(o) for o in SEED_ORDERS]
    next_id = len(orders) + 1

    @app.route('/orders', methods=['GET'])
    def get_orders():
        return jsonify({
            "orders": orders,
            "count": len(orders),
            "instance_id": app.config['INSTANCE_ID'],
            "instance_port": app.config['PORT']
        })

    @app.route('/orders/<int:order_id>', methods=['GET'])
    def get_order(order_id):
        order = next((o for o in orders if o['id'] == order_id), None)
        if not order:
            return jsonify({"error": "Order not found"}), 404
        return jsonify({
            "order": order,
            "instance_id": app.config['INSTANCE_ID'],
            "instance_port": app.config['PORT']
        })

    @app.route('/orders', methods=['POST'])
    def create_order():
        nonlocal next_id
        data = request.json

        if not data or not all(k in data for k in ('item', 'quantity', 'customer')):
            return jsonify({
                "error": "Missing required fields: item, quantity, customer"
            }), 400

        new_order = {
            "id": next_id,
            "item": data['item'],
            "quantity": data['quantity'],
            "customer": data['customer'],
            "status": "pending"
        }
        next_id += 1
        orders.append(new_order)

        return jsonify({
            "order": new_order,
            "instance_id": app.config['INSTANCE_ID'],
            "instance_port": app.config['PORT']
        }), 201

    @app.route('/health', methods=['GET'])
    def health():
        return jsonify({
            "status": "healthy",
            "instance_id": app.config['INSTANCE_ID'],
            "instance_port": app.config['PORT'],
            "timestamp": datetime.now().isoformat()
        })

    return app


# --- Registry Integration ---

class RegistryClient:
    """Handles registration, heartbeat, and deregistration with the service registry."""

    def __init__(self, service_name, port, registry_url):
        self.service_name = service_name
        self.address = f"http://localhost:{port}"
        self.registry_url = registry_url
        self.stop_event = threading.Event()

    def register(self):
        try:
            resp = http_requests.post(
                f"{self.registry_url}/register",
                json={"service": self.service_name, "address": self.address},
                timeout=5
            )
            if resp.status_code in (200, 201):
                print(f"[REGISTERED] {self.service_name} at {self.address}")
                return True
            else:
                print(f"[REGISTER FAILED] Status {resp.status_code}: {resp.text}")
                return False
        except Exception as e:
            print(f"[REGISTER ERROR] {e}")
            return False

    def deregister(self):
        try:
            resp = http_requests.post(
                f"{self.registry_url}/deregister",
                json={"service": self.service_name, "address": self.address},
                timeout=5
            )
            if resp.status_code == 200:
                print(f"[DEREGISTERED] {self.service_name} at {self.address}")
                return True
        except Exception as e:
            print(f"[DEREGISTER ERROR] {e}")
        return False

    def heartbeat_loop(self):
        while not self.stop_event.is_set():
            try:
                http_requests.post(
                    f"{self.registry_url}/heartbeat",
                    json={"service": self.service_name, "address": self.address},
                    timeout=5
                )
            except Exception:
                pass
            self.stop_event.wait(10)

    def start(self):
        self.register()
        t = threading.Thread(target=self.heartbeat_loop, daemon=True)
        t.start()

    def stop(self):
        self.stop_event.set()
        self.deregister()


def main():
    parser = argparse.ArgumentParser(description="Order Service")
    parser.add_argument('--port', type=int, required=True, help="Port to run on")
    parser.add_argument('--registry', type=str, default='http://localhost:5001',
                        help="Registry URL (default: http://localhost:5001)")
    args = parser.parse_args()

    app = create_app(port=args.port, registry_url=args.registry)
    registry_client = RegistryClient("order-service", args.port, args.registry)

    def shutdown_handler(sig, frame):
        print(f"\n[SHUTDOWN] Gracefully stopping order-service-{args.port}...")
        registry_client.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    registry_client.start()
    print(f"[STARTED] order-service-{args.port} on http://localhost:{args.port}")
    app.run(host='0.0.0.0', port=args.port, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()
