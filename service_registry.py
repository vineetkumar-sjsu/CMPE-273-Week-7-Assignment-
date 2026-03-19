"""
Service Registry - A simple service discovery system for distributed applications

This registry allows microservices to:
1. Register themselves with their address
2. Discover other services
3. Deregister when shutting down
4. Perform health checks
"""

from flask import Flask, request, jsonify
from datetime import datetime
import threading
import time
import os

app = Flask(__name__)

# Registry structure: {service_name: [{address, registered_at, last_heartbeat}]}
registry = {}
registry_lock = threading.Lock()

# Configuration
HEARTBEAT_TIMEOUT = 30  # seconds
CLEANUP_INTERVAL = 10   # seconds


@app.route('/register', methods=['POST'])
def register():
    """
    Register a service instance

    Request body:
    {
        "service": "service-name",
        "address": "http://host:port"
    }
    """
    try:
        data = request.json

        if not data or 'service' not in data or 'address' not in data:
            return jsonify({
                "status": "error",
                "message": "Missing required fields: service and address"
            }), 400

        service = data['service']
        address = data['address']

        with registry_lock:
            if service not in registry:
                registry[service] = []

            # Check if address already registered
            existing = next((s for s in registry[service] if s['address'] == address), None)

            if existing:
                # Update heartbeat for existing service
                existing['last_heartbeat'] = datetime.now()
                return jsonify({
                    "status": "updated",
                    "message": f"Service {service} at {address} heartbeat updated"
                })
            else:
                # Register new service instance
                registry[service].append({
                    'address': address,
                    'registered_at': datetime.now(),
                    'last_heartbeat': datetime.now()
                })

                return jsonify({
                    "status": "registered",
                    "message": f"Service {service} registered at {address}"
                }), 201

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/discover/<service>', methods=['GET'])
def discover(service):
    """
    Discover all instances of a service

    Returns list of active service addresses
    """
    with registry_lock:
        if service not in registry:
            return jsonify({
                "service": service,
                "instances": [],
                "message": "Service not found"
            }), 404

        # Return only active instances (with recent heartbeats)
        now = datetime.now()
        active_instances = [
            {
                'address': s['address'],
                'uptime_seconds': (now - s['registered_at']).total_seconds()
            }
            for s in registry[service]
            if (now - s['last_heartbeat']).total_seconds() < HEARTBEAT_TIMEOUT
        ]

        return jsonify({
            "service": service,
            "instances": active_instances,
            "count": len(active_instances)
        })


@app.route('/deregister', methods=['POST'])
def deregister():
    """
    Deregister a service instance

    Request body:
    {
        "service": "service-name",
        "address": "http://host:port"
    }
    """
    try:
        data = request.json

        if not data or 'service' not in data or 'address' not in data:
            return jsonify({
                "status": "error",
                "message": "Missing required fields: service and address"
            }), 400

        service = data['service']
        address = data['address']

        with registry_lock:
            if service in registry:
                registry[service] = [
                    s for s in registry[service]
                    if s['address'] != address
                ]

                # Remove service key if no instances left
                if not registry[service]:
                    del registry[service]

                return jsonify({
                    "status": "deregistered",
                    "message": f"Service {service} at {address} deregistered"
                })
            else:
                return jsonify({
                    "status": "not_found",
                    "message": f"Service {service} not found"
                }), 404

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    """
    Update heartbeat for a service instance

    Request body:
    {
        "service": "service-name",
        "address": "http://host:port"
    }
    """
    try:
        data = request.json

        if not data or 'service' not in data or 'address' not in data:
            return jsonify({
                "status": "error",
                "message": "Missing required fields: service and address"
            }), 400

        service = data['service']
        address = data['address']

        with registry_lock:
            if service in registry:
                instance = next((s for s in registry[service] if s['address'] == address), None)

                if instance:
                    instance['last_heartbeat'] = datetime.now()
                    return jsonify({
                        "status": "ok",
                        "message": "Heartbeat updated"
                    })
                else:
                    return jsonify({
                        "status": "not_found",
                        "message": f"Instance {address} not found for service {service}"
                    }), 404
            else:
                return jsonify({
                    "status": "not_found",
                    "message": f"Service {service} not found"
                }), 404

    except Exception as e:
        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500


@app.route('/services', methods=['GET'])
def list_services():
    """
    List all registered services and their instance counts
    """
    with registry_lock:
        services_info = {}
        now = datetime.now()

        for service, instances in registry.items():
            active_count = sum(
                1 for s in instances
                if (now - s['last_heartbeat']).total_seconds() < HEARTBEAT_TIMEOUT
            )
            services_info[service] = {
                'total_instances': len(instances),
                'active_instances': active_count
            }

        return jsonify({
            "services": services_info,
            "total_services": len(services_info)
        })


@app.route('/health', methods=['GET'])
def health():
    """
    Health check endpoint for the registry itself
    """
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat()
    })


def cleanup_stale_services():
    """
    Background task to remove services that haven't sent heartbeats
    """
    while True:
        time.sleep(CLEANUP_INTERVAL)

        with registry_lock:
            now = datetime.now()
            services_to_remove = []

            for service, instances in registry.items():
                # Filter out stale instances
                active_instances = [
                    s for s in instances
                    if (now - s['last_heartbeat']).total_seconds() < HEARTBEAT_TIMEOUT
                ]

                if active_instances:
                    registry[service] = active_instances
                else:
                    services_to_remove.append(service)

            # Remove services with no active instances
            for service in services_to_remove:
                del registry[service]
                print(f"Removed stale service: {service}")


if __name__ == '__main__':
    # Start cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_stale_services, daemon=True)
    cleanup_thread.start()

    print("Service Registry starting on port 5001...")
    print(f"Heartbeat timeout: {HEARTBEAT_TIMEOUT}s")
    print(f"Cleanup interval: {CLEANUP_INTERVAL}s")

    port = int(os.environ.get('REGISTRY_PORT', 5001))
    app.run(host='0.0.0.0', port=port, debug=False)

# Made with Bob
