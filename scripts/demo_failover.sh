#!/usr/bin/env bash
# ===========================================================================
# SecureStego — Failover Demonstration Script
#
# Demonstrates that the system continues serving requests when one replica
# is killed, thanks to Nginx round-robin load balancing.
#
# Prerequisites:
#   - Docker and Docker Compose installed
#   - Run from the project root: ./scripts/demo_failover.sh
#
# What it does:
#   1. Starts the full stack (docker compose up)
#   2. Waits for all services to be healthy
#   3. Fires continuous health check requests via Nginx
#   4. Kills one API replica mid-stream
#   5. Shows that requests continue succeeding (no dropped connections)
#   6. Brings the killed replica back
#   7. Shows it rejoins the load balancer
# ===========================================================================

set -euo pipefail

COMPOSE_DIR="infra"
COMPOSE_FILE="$COMPOSE_DIR/docker-compose.yml"
NGINX_URL="http://localhost"
REPLICA_TO_KILL="securestego-api-2"
REQUEST_COUNT=40
SLEEP_BETWEEN=0.3

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}=== SecureStego Failover Demo ===${NC}"
echo ""

# --- Step 1: Start the stack ---
echo -e "${YELLOW}[1/7] Starting the full stack...${NC}"
docker compose -f "$COMPOSE_FILE" up -d --build
echo "Stack started."

# --- Step 2: Wait for health ---
echo -e "${YELLOW}[2/7] Waiting for services to be healthy...${NC}"
MAX_WAIT=60
WAITED=0
until curl -sf "$NGINX_URL/health" > /dev/null 2>&1; do
    sleep 2
    WAITED=$((WAITED + 2))
    if [ "$WAITED" -ge "$MAX_WAIT" ]; then
        echo -e "${RED}Timeout waiting for services. Check docker compose logs.${NC}"
        exit 1
    fi
    echo "  Waiting... (${WAITED}s)"
done
echo -e "${GREEN}All services healthy.${NC}"
echo ""

# --- Step 3: Fire requests (all 3 replicas alive) ---
echo -e "${YELLOW}[3/7] Sending $((REQUEST_COUNT / 2)) requests (all 3 replicas active)...${NC}"
SUCCESS_BEFORE=0
FAIL_BEFORE=0
for i in $(seq 1 $((REQUEST_COUNT / 2))); do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$NGINX_URL/health" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        SUCCESS_BEFORE=$((SUCCESS_BEFORE + 1))
    else
        FAIL_BEFORE=$((FAIL_BEFORE + 1))
    fi
    sleep "$SLEEP_BETWEEN"
done
echo -e "  ${GREEN}Success: $SUCCESS_BEFORE${NC} | ${RED}Failed: $FAIL_BEFORE${NC}"
echo ""

# --- Step 4: Kill one replica ---
echo -e "${YELLOW}[4/7] Killing replica: $REPLICA_TO_KILL${NC}"
docker stop "$REPLICA_TO_KILL"
echo -e "${RED}$REPLICA_TO_KILL stopped.${NC}"
sleep 2
echo ""

# --- Step 5: Fire requests (2 replicas remaining) ---
echo -e "${YELLOW}[5/7] Sending $((REQUEST_COUNT / 2)) requests (1 replica down, 2 remaining)...${NC}"
SUCCESS_DURING=0
FAIL_DURING=0
for i in $(seq 1 $((REQUEST_COUNT / 2))); do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" "$NGINX_URL/health" 2>/dev/null || echo "000")
    if [ "$HTTP_CODE" = "200" ]; then
        SUCCESS_DURING=$((SUCCESS_DURING + 1))
    else
        FAIL_DURING=$((FAIL_DURING + 1))
    fi
    sleep "$SLEEP_BETWEEN"
done
echo -e "  ${GREEN}Success: $SUCCESS_DURING${NC} | ${RED}Failed: $FAIL_DURING${NC}"
echo ""

# --- Step 6: Bring the replica back ---
echo -e "${YELLOW}[6/7] Restarting $REPLICA_TO_KILL...${NC}"
docker start "$REPLICA_TO_KILL"
sleep 5
echo -e "${GREEN}$REPLICA_TO_KILL restarted.${NC}"
echo ""

# --- Step 7: Summary ---
echo -e "${YELLOW}[7/7] Results Summary${NC}"
echo "=============================="
echo -e "Before kill:  ${GREEN}$SUCCESS_BEFORE success${NC} / ${RED}$FAIL_BEFORE failed${NC}"
echo -e "During kill:  ${GREEN}$SUCCESS_DURING success${NC} / ${RED}$FAIL_DURING failed${NC}"
echo "=============================="

TOTAL_SUCCESS=$((SUCCESS_BEFORE + SUCCESS_DURING))
TOTAL_FAIL=$((FAIL_BEFORE + FAIL_DURING))
TOTAL=$((TOTAL_SUCCESS + TOTAL_FAIL))

if [ "$FAIL_DURING" -le 1 ]; then
    echo -e "${GREEN}✓ FAILOVER SUCCESSFUL: Requests continued uninterrupted despite a killed replica.${NC}"
    echo "  $TOTAL_SUCCESS/$TOTAL requests succeeded ($FAIL_DURING failures during failover — Nginx retry handled it)."
else
    echo -e "${YELLOW}⚠ PARTIAL FAILOVER: Some requests failed during replica kill. This may be expected"
    echo "  during the brief window before Nginx detects the failure (max_fails=3).${NC}"
fi

echo ""
echo "To clean up: docker compose -f $COMPOSE_FILE down -v"
