#!/bin/bash
set -e

echo "============================================"
echo " Phase 0: Observability Lab - Teardown"
echo "============================================"
echo ""

echo "[1/4] Removing OTEL Collector..."
kubectl delete -f manifests/otel-collector.yaml 2>/dev/null || true
kubectl delete -f manifests/otel-service-monitor.yaml 2>/dev/null || true

echo "[2/4] Removing traffic generator..."
kubectl delete -f manifests/traffic-generator.yaml 2>/dev/null || true

echo "[3/4] Removing Grafana dashboard..."
kubectl delete -f manifests/grafana-dashboard-configmap.yaml 2>/dev/null || true

echo "[4/4] Restoring original appserver..."
kubectl apply -f - <<EOF
apiVersion: apps/v1
kind: Deployment
metadata:
  name: yelb-appserver
  namespace: default
spec:
  replicas: 1
  selector:
    matchLabels:
      app: yelb-appserver
      tier: middletier
  template:
    metadata:
      labels:
        app: yelb-appserver
        tier: middletier
    spec:
      containers:
      - name: yelb-appserver
        image: yelb-appserver-otel:latest
        imagePullPolicy: Never
        ports:
        - containerPort: 4567
        env:
        - name: OTEL_SERVICE_NAME
          value: yelb-appserver
        - name: OTEL_EXPORTER_OTLP_ENDPOINT
          value: http://jaeger-collector.observability:4318
        - name: OTEL_TRACES_SAMPLER
          value: always_on
EOF

echo ""
echo "Teardown complete."
echo "Note: Yelb services, Jaeger, and Prometheus/Grafana are still running."
echo "To fully clean up: minikube delete"