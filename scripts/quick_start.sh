#!/bin/bash
# Quick Start Script for ShipStack AI
# Validates config, launches all services, opens dashboard

set -e

DROPSHIP_OS=$(dirname "$(readlink -f "$0")")
cd "$DROPSHIP_OS"

echo "================================"
echo "ShipStack AI Quick Start"
echo "================================"

echo ""
echo "Step 1: Validating configuration..."
python3 validate_config.py
if [ $? -ne 0 ]; then
    echo "❌ Config validation failed. Fix issues and try again."
    exit 1
fi

echo ""
echo "Step 2: Launching services..."
python3 launch_shipstack.py &
LAUNCHER_PID=$!

echo ""
echo "Step 3: Waiting for services to start..."
sleep 5

echo ""
echo "Step 4: Running integration tests..."
python3 test_integration.py
if [ $? -ne 0 ]; then
    echo "⚠️  Some tests failed. Check logs."
fi

echo ""
echo "================================"
echo "✓ ShipStack AI is running"
echo "================================"
echo ""
echo "Service URLs:"
echo "  Dashboard:          http://localhost:8890"
echo "  ShipStack Engine:   http://localhost:8889"
echo "  Prometheus Engine:  http://localhost:8766"
echo "  Social AI Agent:    http://localhost:8867"
echo ""
echo "Press Ctrl+C to stop all services"
echo ""

wait $LAUNCHER_PID
