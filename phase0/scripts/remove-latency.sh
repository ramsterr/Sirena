#!/bin/bash
set -e

SERVICES="yelb-appserver yelb-db yelb-ui redis-server"

remove_latency() {
    local service=$1
    
    local pod=$(kubectl get pods -l app=${service} -o jsonpath='{.items[0].metadata.name}')
    if [ -z "$pod" ]; then
        echo "ERROR: Could not find pod for service ${service}"
        return 1
    fi
    
    local container=$(kubectl get pods -l app=${service} -o jsonpath='{.items[0].spec.containers[0].name}')
    
    echo "Removing latency from ${service} (pod: ${pod})..."
    kubectl exec ${pod} -c ${container} -- tc qdisc del dev eth0 root 2>/dev/null || \
        echo "No latency injection was active on ${service}"
}

if [ -z "$1" ]; then
    echo "Removing latency from all services..."
    for svc in ${SERVICES}; do
        remove_latency "${svc}" || true
    done
else
    remove_latency "$1"
fi