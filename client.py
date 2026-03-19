"""
Discovery Client — Discovers order-service instances and calls a random one.

Queries the service registry to find all active instances of order-service,
picks one at random, and makes an HTTP request. Repeats for N rounds to
demonstrate random distribution across instances.

Usage:
    python client.py                    # 10 rounds, GET /orders
    python client.py --rounds 20       # 20 rounds
    python client.py --action get-one  # GET /orders/1
    python client.py --action create   # POST /orders
"""

import argparse
import random
import requests
import sys
import json


def discover_instances(registry_url, service_name):
    """Query the registry for active instances of a service."""
    try:
        resp = requests.get(f"{registry_url}/discover/{service_name}", timeout=5)
        if resp.status_code == 200:
            data = resp.json()
            return [inst['address'] for inst in data.get('instances', [])]
        elif resp.status_code == 404:
            return []
        else:
            print(f"[ERROR] Discovery failed: {resp.status_code}")
            return []
    except requests.exceptions.ConnectionError:
        print(f"[ERROR] Cannot connect to registry at {registry_url}")
        print("Make sure the registry is running: python service_registry.py")
        sys.exit(1)


def call_instance(address, action):
    """Make an HTTP request to a service instance."""
    try:
        if action == 'list':
            resp = requests.get(f"{address}/orders", timeout=5)
        elif action == 'get-one':
            resp = requests.get(f"{address}/orders/1", timeout=5)
        elif action == 'create':
            resp = requests.post(f"{address}/orders", json={
                "item": f"Widget-{random.randint(100, 999)}",
                "quantity": random.randint(1, 10),
                "customer": random.choice(["Alice", "Bob", "Charlie", "Diana"])
            }, timeout=5)
        else:
            print(f"[ERROR] Unknown action: {action}")
            return None

        return resp.json()
    except Exception as e:
        print(f"[ERROR] Call to {address} failed: {e}")
        return None


def main():
    parser = argparse.ArgumentParser(description="Service Discovery Client")
    parser.add_argument('--registry', type=str, default='http://localhost:5001',
                        help="Registry URL (default: http://localhost:5001)")
    parser.add_argument('--rounds', type=int, default=10,
                        help="Number of requests to make (default: 10)")
    parser.add_argument('--action', type=str, default='list',
                        choices=['list', 'get-one', 'create'],
                        help="Action to perform (default: list)")
    args = parser.parse_args()

    print("=" * 60)
    print("SERVICE DISCOVERY CLIENT")
    print("=" * 60)
    print(f"Registry: {args.registry}")
    print(f"Action:   {args.action}")
    print(f"Rounds:   {args.rounds}")
    print("=" * 60)
    print()

    # Track distribution
    distribution = {}

    for i in range(1, args.rounds + 1):
        print(f"=== Round {i}/{args.rounds} ===")

        # Step 1: Discover
        instances = discover_instances(args.registry, "order-service")
        if not instances:
            print("[ERROR] No instances available. Are the services running?")
            sys.exit(1)

        print(f"Discovered {len(instances)} instance(s): {instances}")

        # Step 2: Pick random
        selected = random.choice(instances)
        print(f"Selected: {selected}")

        # Step 3: Call
        result = call_instance(selected, args.action)
        if result:
            instance_id = result.get('instance_id', 'unknown')
            print(f"Response from instance: {instance_id}")

            if args.action == 'list':
                print(f"Orders returned: {result.get('count', '?')}")
            elif args.action == 'get-one':
                order = result.get('order', {})
                print(f"Order: #{order.get('id')} - {order.get('item')}")
            elif args.action == 'create':
                order = result.get('order', {})
                print(f"Created: #{order.get('id')} - {order.get('item')}")

            # Track distribution
            distribution[instance_id] = distribution.get(instance_id, 0) + 1

        print("---")
        print()

    # Summary
    print("=" * 60)
    print("DISTRIBUTION SUMMARY")
    print("=" * 60)
    total = sum(distribution.values())
    for instance_id, count in sorted(distribution.items()):
        pct = (count / total) * 100 if total > 0 else 0
        print(f"  {instance_id}: {count}/{total} requests ({pct:.0f}%)")
    print()


if __name__ == '__main__':
    main()
