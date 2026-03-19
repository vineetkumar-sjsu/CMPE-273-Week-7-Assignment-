#!/bin/bash
#
# Week 7 Demo - Microservice Discovery
#
# Usage: ./week-7-demo.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

PIDS=()

say() {
    echo "$1"
    sleep 2
}

pause_for() {
    local seconds="${1:-3}"
    sleep "$seconds"
}

section() {
    echo ""
    echo -e "${BOLD}────────────────────────────────────────────${NC}"
    echo ""
}

cleanup() {
    echo ""
    echo -e "${YELLOW}Cleaning up all background processes...${NC}"
    for pid in "${PIDS[@]}"; do
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null
            wait "$pid" 2>/dev/null || true
        fi
    done
    sleep 1
    echo -e "${GREEN}All processes stopped.${NC}"
    echo ""
}

trap cleanup EXIT

# ============================================================
# INTRO
# ============================================================
if [ -t 1 ]; then clear 2>/dev/null || true; fi
echo ""
echo -e "${BLUE}╔════════════════════════════════════════════════════╗${NC}"
echo -e "${BLUE}║                                                    ║${NC}"
echo -e "${BLUE}║   ${BOLD}CMPE-273 Week 7: Service Discovery Demo${NC}${BLUE}          ║${NC}"
echo -e "${BLUE}║                                                    ║${NC}"
echo -e "${BLUE}║   Microservice with Registry-Based Discovery       ║${NC}"
echo -e "${BLUE}║                                                    ║${NC}"
echo -e "${BLUE}╚════════════════════════════════════════════════════╝${NC}"
echo ""
sleep 3
say "  This demo shows how microservices register with a central"
say "  service registry and how a client discovers and routes"
say "  requests to random instances."
echo ""
sleep 2

# ============================================================
# STEP 1: Check dependencies
# ============================================================
section
echo -e "${YELLOW}Step 1: Checking dependencies...${NC}"
sleep 2
if ! python3 -c "import flask, requests" 2>/dev/null; then
    echo -e "${RED}  Missing dependencies. Installing...${NC}"
    pip3 install -r requirements.txt
fi
echo -e "${GREEN}  Flask and Requests are installed.${NC}"
sleep 3

# ============================================================
# STEP 2: Start Service Registry
# ============================================================
section
echo -e "${YELLOW}Step 2: Starting the Service Registry...${NC}"
sleep 2
say "  The registry is the central hub where services register themselves."
say "  It runs on port 5001."
echo ""
sleep 2

python3 service_registry.py > /tmp/registry.log 2>&1 &
PIDS+=($!)

echo -e "${CYAN}  Waiting for registry to start...${NC}"
sleep 4

if curl -s http://localhost:5001/health > /dev/null 2>&1; then
    echo -e "${GREEN}  Registry is running on port 5001${NC}"
else
    echo -e "${RED}  Failed to start registry. Check /tmp/registry.log${NC}"
    exit 1
fi
echo ""
echo -e "${BLUE}  Health check response:${NC}"
sleep 2
curl -s http://localhost:5001/health | python3 -m json.tool
sleep 4

# ============================================================
# STEP 3: Start Order Service Instances
# ============================================================
section
echo -e "${YELLOW}Step 3: Starting two Order Service instances...${NC}"
sleep 2
say "  Each instance is an independent process serving the same API."
say "  They self-register with the registry on startup."
echo ""
sleep 2

echo -e "${BLUE}  Starting Instance 1 on port 8001...${NC}"
python3 order_service.py --port 8001 > /tmp/order-service-8001.log 2>&1 &
PIDS+=($!)
sleep 3
echo -e "${GREEN}  Instance 1 (port 8001) is running${NC}"
echo ""

echo -e "${BLUE}  Starting Instance 2 on port 8002...${NC}"
python3 order_service.py --port 8002 > /tmp/order-service-8002.log 2>&1 &
PIDS+=($!)

echo -e "${CYAN}  Waiting for both instances to register...${NC}"
sleep 4

echo -e "${GREEN}  Instance 2 (port 8002) is running${NC}"
sleep 3

# ============================================================
# STEP 4: Verify Registration
# ============================================================
section
echo -e "${YELLOW}Step 4: Verifying service registration...${NC}"
sleep 2
say "  Querying the registry to confirm both instances registered."
echo ""
sleep 2

echo -e "${BLUE}  GET /services - all registered services:${NC}"
echo ""
curl -s http://localhost:5001/services | python3 -m json.tool
sleep 4

echo ""
echo -e "${BLUE}  GET /discover/order-service - discovered instances:${NC}"
echo ""
curl -s http://localhost:5001/discover/order-service | python3 -m json.tool
sleep 4

echo ""
echo -e "${GREEN}  Both instances are registered and discoverable.${NC}"
sleep 3

# ============================================================
# STEP 5: Discovery Client - Random Routing
# ============================================================
section
echo -e "${YELLOW}Step 5: Running the Discovery Client...${NC}"
sleep 2
say "  The client queries the registry, gets a list of instances,"
say "  and picks one at RANDOM for each request."
say "  Watch which instance handles each round."
echo ""
sleep 3

python3 client.py --rounds 10

sleep 5

# ============================================================
# STEP 6: Instance Isolation
# ============================================================
section
echo -e "${YELLOW}Step 6: Demonstrating instance isolation...${NC}"
sleep 2
say "  Each instance has its own in-memory state."
say "  A POST to one instance does NOT affect the other."
echo ""
sleep 3

echo -e "${BLUE}  Creating 'Headphones' order on Instance 1 (port 8001):${NC}"
echo ""
curl -s -X POST http://localhost:8001/orders \
    -H "Content-Type: application/json" \
    -d '{"item": "Headphones", "quantity": 1, "customer": "Demo-User"}' | python3 -m json.tool
sleep 3

echo ""
echo -e "${BLUE}  Creating 'Webcam' order on Instance 2 (port 8002):${NC}"
echo ""
curl -s -X POST http://localhost:8002/orders \
    -H "Content-Type: application/json" \
    -d '{"item": "Webcam", "quantity": 2, "customer": "Demo-User"}' | python3 -m json.tool
sleep 3

echo ""
echo -e "${BLUE}  Instance 1 orders (has Headphones, but NOT Webcam):${NC}"
echo ""
curl -s http://localhost:8001/orders | python3 -m json.tool
sleep 4

echo ""
echo -e "${BLUE}  Instance 2 orders (has Webcam, but NOT Headphones):${NC}"
echo ""
curl -s http://localhost:8002/orders | python3 -m json.tool
sleep 4

echo ""
echo -e "${GREEN}  Each instance maintains independent state.${NC}"
sleep 3

# ============================================================
# STEP 7: Graceful Shutdown
# ============================================================
section
echo -e "${YELLOW}Step 7: Demonstrating graceful shutdown...${NC}"
sleep 2
say "  When a service shuts down, it deregisters from the registry."
say "  The registry immediately reflects the change."
echo ""
sleep 3

echo -e "${BLUE}  Before shutdown - both instances active:${NC}"
echo ""
curl -s http://localhost:5001/discover/order-service | python3 -m json.tool
sleep 4

echo ""
echo -e "${RED}  Stopping Instance 2 (port 8002)...${NC}"
kill "${PIDS[2]}" 2>/dev/null
wait "${PIDS[2]}" 2>/dev/null || true
sleep 2
echo -e "${RED}  Instance 2 sent deregister request and shut down.${NC}"

echo -e "${CYAN}  Waiting for registry to reflect the change...${NC}"
sleep 4

echo ""
echo -e "${BLUE}  After shutdown - only Instance 1 remains:${NC}"
echo ""
curl -s http://localhost:5001/discover/order-service | python3 -m json.tool
sleep 4

echo ""
echo -e "${GREEN}  Instance 2 was gracefully removed from the registry.${NC}"
sleep 3

section
echo -e "${GREEN}${BOLD}DEMO COMPLETE${NC}"
echo ""
sleep 3
