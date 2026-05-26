#!/bin/bash
set -e

JAEGER_URL="${JAEGER_URL:-http://localhost:16686}"
PROMETHEUS_URL="${PROMETHEUS_URL:-http://localhost:9090}"

echo "============================================"
echo " Phase 0: Observability Lab - Verification"
echo "============================================"
echo ""

FAILURES=0

echo "--- [1/5] Checking Yelb services are running ---"
for svc in yelb-ui yelb-appserver yelb-db redis-server; do
    ready=$(kubectl get deploy ${svc} -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "0")
    if [ "$ready" = "1" ]; then
        echo "  [OK] ${svc}: running"
    else
        echo "  [FAIL] ${svc}: not ready (replicas: ${ready:-0})"
        FAILURES=$((FAILURES + 1))
    fi
done
echo ""

echo "--- [2/5] Checking Jaeger traces ---"
echo "  Port-forwarding Jaeger..."
kubectl port-forward svc/jaeger-query -n observability 16686:16686 &
PF_PID=$!
sleep 2

services=$(curl -s "${JAEGER_URL}/api/services" 2>/dev/null || echo "")
if echo "$services" | grep -q "yelb"; then
    svc_list=$(echo "$services" | python3 -c "import sys, json; d=json.load(sys.stdin); print(', '.join(d['data']))" 2>/dev/null || echo "parse error")
    echo "  [OK] Jaeger has traces from: ${svc_list}"
    
    trace_count=$(curl -s "${JAEGER_URL}/api/traces?service=yelb-appserver&limit=5" 2>/dev/null | \
        python3 -c "import sys, json; d=json.load(sys.stdin); print(len(d.get('data', [])))" 2>/dev/null || echo "0")
    if [ "$trace_count" -gt 0 ]; then
        echo "  [OK] Found ${trace_count} recent traces from yelb-appserver"
    else
        echo "  [WARN] No recent traces from yelb-appserver (traffic may not be flowing yet)"
    fi
else
    echo "  [FAIL] Jaeger has no yelb service traces"
    FAILURES=$((FAILURES + 1))
fi
kill $PF_PID 2>/dev/null || true
echo ""

echo "--- [3/5] Checking OTEL Collector ---"
otel_status=$(kubectl get deploy otel-collector -n observability -o jsonpath='{.status.readyReplicas}' 2>/dev/null || echo "")
if [ "$otel_status" = "1" ]; then
    echo "  [OK] OTEL Collector is running"
else
    echo "  [WARN] OTEL Collector not found or not ready (status: ${otel_status:-not deployed})"
fi
echo ""

echo "--- [4/5] Checking Prometheus metrics ---"
echo "  Port-forwarding Prometheus..."
kubectl port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090 &
PF_PID=$!
sleep 2

up_count=$(curl -s "${PROMETHEUS_URL}/api/v1/query?query=up" 2>/dev/null | \
    python3 -c "import sys, json; d=json.load(sys.stdin); print(len(d['data']['result']))" 2>/dev/null || echo "0")
echo "  [INFO] Prometheus scraping ${up_count} targets"

yelb_metrics=$(curl -s "${PROMETHEUS_URL}/api/v1/query?query=yelb_http_server_request_duration_seconds_count" 2>/dev/null | \
    python3 -c "import sys, json; d=json.load(sys.stdin); r=d['data']['result']; print(f'{len(r)} series' if r else 'no data')" 2>/dev/null || echo "error")
echo "  [INFO] Yelb appserver metrics in Prometheus: ${yelb_metrics}"

container_metrics=$(curl -s "${PROMETHEUS_URL}/api/v1/query?query=container_cpu_usage_seconds_total{namespace=\"default\"}" 2>/dev/null | \
    python3 -c "import sys, json; d=json.load(sys.stdin); print(f'{len(d[\"data\"][\"result\"])} series')" 2>/dev/null || echo "0")
echo "  [INFO] Container metrics in Prometheus: ${container_metrics}"

kill $PF_PID 2>/dev/null || true
echo ""

echo "--- [5/5] Checking traffic generator ---"
traffic_pod=$(kubectl get pods -l app=traffic-gen -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || echo "")
if [ -n "$traffic_pod" ]; then
    traffic_status=$(kubectl get pod "$traffic_pod" -o jsonpath='{.status.phase}' 2>/dev/null || echo "Unknown")
    if [ "$traffic_status" = "Running" ]; then
        echo "  [OK] Traffic generator is running (pod: ${traffic_pod})"
    else
        echo "  [WARN] Traffic generator pod status: ${traffic_status}"
    fi
else
    echo "  [WARN] No traffic generator pod found"
fi
echo ""

echo "============================================"
if [ $FAILURES -eq 0 ]; then
    echo " RESULT: ALL CHECKS PASSED"
else
    echo " RESULT: ${FAILURES} CHECK(S) FAILED"
fi
echo "============================================"
echo ""
echo "Access dashboards:"
echo "  Jaeger:  kubectl port-forward svc/jaeger-query -n observability 16686:16686"
echo "  Prometheus: kubectl port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090"
echo "  Grafana: kubectl port-forward svc/prometheus-grafana 3000:80 (admin/prom-operator)"