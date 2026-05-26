#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
MANIFESTS_DIR="${SCRIPT_DIR}/../manifests"

echo "============================================"
echo " Phase 0: Observability Lab - Setup"
echo "============================================"
echo ""

echo "[1/8] Checking minikube is running..."
if ! minikube status | grep -q "Running"; then
    echo "Starting minikube..."
    minikube start --cpus=4 --memory=8192
else
    echo "  Minikube is running."
fi
echo ""

echo "[2/8] Checking Jaeger is deployed in observability namespace..."
if ! kubectl get deploy jaeger -n observability &>/dev/null; then
    echo "Deploying Jaeger..."
    kubectl apply -f https://github.com/jaegertracing/jaeger-operator/releases/download/v1.53.0/jaeger-operator.yaml -n observability 2>/dev/null || true
    kubectl create namespace observability 2>/dev/null || true
    cat <<EOF | kubectl apply -f -
apiVersion: jaegertracing.io/v1
kind: Jaeger
metadata:
  name: jaeger
spec:
  strategy: allInOne
  allInOne:
    options:
      log-level: info
EOF
else
    echo "  Jaeger already deployed."
fi
echo ""

echo "[3/8] Deploying OTEL Collector..."
kubectl apply -f "${MANIFESTS_DIR}/otel-collector.yaml"
echo "Waiting for OTEL Collector to be ready..."
kubectl wait --for=condition=available deployment/otel-collector -n observability --timeout=120s
echo "  OTEL Collector is ready."
echo ""

echo "[4/8] Checking Prometheus + Grafana (kube-prometheus-stack)..."
if ! kubectl get deploy prometheus-kube-prometheus-operator &>/dev/null; then
    echo "Installing kube-prometheus-stack..."
    helm repo add prometheus-community https://prometheus-community.github.io/helm-charts 2>/dev/null || true
    helm repo update
    helm install prometheus prometheus-community/kube-prometheus-stack
    echo "Waiting for Prometheus to be ready..."
    kubectl wait --for=condition=available deployment/prometheus-kube-prometheus-operator --timeout=300s
else
    echo "  Prometheus + Grafana already deployed."
fi
echo ""

echo "[5/8] Applying ServiceMonitors..."
kubectl apply -f "${MANIFESTS_DIR}/otel-service-monitor.yaml"
echo "  OTEL Collector ServiceMonitor applied."
echo ""

echo "[6/8] Deploying/updating Yelb appserver with OTEL Collector endpoint..."
kubectl apply -f "${MANIFESTS_DIR}/yelb-appserver-updated.yaml"
echo "Waiting for appserver rollout..."
kubectl rollout status deployment/yelb-appserver --timeout=120s
echo ""

echo "[7/8] Deploying traffic generator..."
kubectl delete pod traffic-gen 2>/dev/null || true
kubectl apply -f "${MANIFESTS_DIR}/traffic-generator.yaml"
echo "Waiting for traffic generator to start..."
kubectl wait --for=condition=available deployment/traffic-gen --timeout=60s 2>/dev/null || \
    echo "  Note: traffic-gen may take a moment to pull the image."
echo ""

echo "[8/8] Deploying Grafana dashboard..."
kubectl apply -f "${MANIFESTS_DIR}/grafana-dashboard-configmap.yaml"
echo "  Dashboard ConfigMap applied."
echo ""

echo "============================================"
echo " Setup complete!"
echo "============================================"
echo ""
echo "Next steps:"
echo "  1. Generate some load: the traffic generator is already running"
echo "  2. Wait ~2 minutes for traces and metrics to accumulate"
echo "  3. Run verification: ./scripts/verify.sh"
echo "  4. Access dashboards:"
echo "     Jaeger:     kubectl port-forward svc/jaeger-query -n observability 16686:16686"
echo "     Prometheus:  kubectl port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090"
echo "     Grafana:     kubectl port-forward svc/prometheus-grafana 3000:80"
echo "  5. Try fault injection: ./scripts/fault-inject.sh latency yelb-appserver 500 120"