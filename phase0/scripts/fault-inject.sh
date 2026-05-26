#!/bin/bash
set -e

SERVICES="yelb-appserver yelb-db yelb-ui redis-server"

inject_latency() {
    local service=$1
    local latency_ms=${2:-500}
    local duration_sec=${3:-120}
    
    echo "=== Injecting ${latency_ms}ms latency into ${service} for ${duration_sec}s ==="
    
    local pod=$(kubectl get pods -l app=${service} -o jsonpath='{.items[0].metadata.name}')
    if [ -z "$pod" ]; then
        echo "ERROR: Could not find pod for service ${service}"
        return 1
    fi
    
    local container=$(kubectl get pods -l app=${service} -o jsonpath='{.items[0].spec.containers[0].name}')
    echo "Target pod: ${pod}, container: ${container}"
    
    if kubectl exec ${pod} -c ${container} -- tc qdisc add dev eth0 root netem delay ${latency_ms}ms 2>/dev/null; then
        echo "Latency injection active via tc. Will auto-remove in ${duration_sec}s..."
        echo "To remove manually: ./scripts/remove-latency.sh ${service}"
        sleep ${duration_sec}
        kubectl exec ${pod} -c ${container} -- tc qdisc del dev eth0 root 2>/dev/null || true
        echo "Latency removed."
    else
        echo "NOTE: 'tc' not available in container. Using ephemeral debug container approach..."
        echo "Trying kubectl debug..."
        
        local debug_pod=$(kubectl debug ${pod} -c netem --image=nicolaka/netshoot --target=${container} -- sleep ${duration_sec} 2>/dev/null | head -1 | awk '{print $4}')
        if [ -n "$debug_pod" ]; then
            echo "Debug pod: ${debug_pod}"
            kubectl exec ${debug_pod} -c netem -- tc qdisc add dev eth0 root netem delay ${latency_ms}ms
            echo "Latency injection active. Will auto-remove in ${duration_sec}s..."
            sleep ${duration_sec}
            kubectl exec ${debug_pod} -c netem -- tc qdisc del dev eth0 root 2>/dev/null || true
            echo "Latency removed."
            kubectl delete pod ${debug_pod} 2>/dev/null || true
        else
            echo "ERROR: Could not inject latency. 'tc' and 'kubectl debug' both failed."
            echo "Alternative: Use scale-down fault injection instead."
            echo "  ./scripts/fault-inject.sh scale-down ${service} 0 ${duration_sec}"
            return 1
        fi
    fi
}

inject_cpu_stress() {
    local service=$1
    local cpu_workers=${2:-2}
    local duration_sec=${3:-120}
    
    echo "=== Injecting CPU stress (${cpu_workers} workers) into ${service} via kubectl debug ==="
    
    local pod=$(kubectl get pods -l app=${service} -o jsonpath='{.items[0].metadata.name}')
    if [ -z "$pod" ]; then
        echo "ERROR: Could not find pod for service ${service}"
        return 1
    fi
    
    local container=$(kubectl get pods -l app=${service} -o jsonpath='{.items[0].spec.containers[0].name}')
    
    echo "Creating debug container with stress-ng..."
    kubectl debug ${pod} -c stress --image=progrium/stressor --target=${container} -- \
        stress-ng --cpu ${cpu_workers} --timeout ${duration_sec}s 2>/dev/null || \
        echo "NOTE: CPU stress requires debug container support. Alternative: use scale-down."
    
    echo "CPU stress active for ${duration_sec}s on ${service}"
}

scale_down() {
    local service=$1
    local replicas=${2:-0}
    local duration_sec=${3:-120}
    
    echo "=== Scaling ${service} to ${replicas} replicas for ${duration_sec}s ==="
    
    local current=$(kubectl get deployment ${service} -o jsonpath='{.spec.replicas}')
    echo "Current replicas: ${current}"
    
    kubectl scale deployment ${service} --replicas=${replicas}
    echo "Scaled to ${replicas} replicas."
    echo "To restore manually: kubectl scale deployment ${service} --replicas=${current}"
    
    echo "Waiting ${duration_sec}s before restoring..."
    sleep ${duration_sec}
    
    echo "Restoring ${service} to ${current} replicas..."
    kubectl scale deployment ${service} --replicas=${current}
    echo "Restored."
}

case "${1:-}" in
    latency)
        inject_latency "${2:-yelb-appserver}" "${3:-500}" "${4:-120}"
        ;;
    cpu)
        inject_cpu_stress "${2:-yelb-appserver}" "${3:-2}" "${4:-120}"
        ;;
    scale-down)
        scale_down "${2:-yelb-db}" "${3:-0}" "${4:-120}"
        ;;
    *)
        echo "Usage: $0 {latency|cpu|scale-down} [service] [value] [duration_sec]"
        echo ""
        echo "Examples:"
        echo "  $0 scale-down yelb-db 0 120       # Scale DB to 0 replicas for 120s (RECOMMENDED)"
        echo "  $0 scale-down yelb-appserver 0      # Scale appserver to 0 replicas"
        echo "  $0 latency yelb-appserver 500 120  # 500ms latency for 120s (requires 'tc')"
        echo "  $0 cpu yelb-appserver 2 120          # CPU stress (requires debug container)"
        echo ""
        echo "Available services: ${SERVICES}"
        echo ""
        echo "NOTE: scale-down is the most reliable fault injection method."
        echo "latency and cpu require tools (tc, stress-ng) in the container image."
        exit 1
        ;;
esac