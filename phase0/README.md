# Phase 0: Observability Lab — Yelb (instead of Online Boutique)

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Minikube Cluster                          │
│                                                              │
│  ┌──────────┐   ┌───────────────┐   ┌──────────┐           │
│  │ yelb-ui  │──→│ yelb-appserver│──→│  yelb-db  │           │
│  │ (nginx)  │   │  (Ruby/Sinatra│   │(PostgreSQL│           │
│  └──────────┘   │  + OTEL)      │   └──────────┘           │
│                  └──────┬───────┘                           │
│                         │                                    │
│                  ┌──────┴───────┐                           │
│                  │ redis-server │                           │
│                  │   (cache)    │                           │
│                  └──────────────┘                           │
│                                                              │
│  ┌──────────────┐  ┌────────────────┐  ┌──────────────┐   │
│  │ Jaeger       │  │ OTEL Collector  │  │ Prometheus    │   │
│  │ (traces)     │←─│ (telemetry hub) │  │ + Grafana     │   │
│  └──────────────┘  └────────────────┘  └──────────────┘   │
│                                                              │
│  ┌──────────────────┐  ┌──────────────────┐                 │
│  │ Blackbox Exporter │  │ Traffic Gen      │                │
│  │ (HTTP probes)     │  │ (continuous load)│                │
│  └──────────────────┘  └──────────────────┘                │
└─────────────────────────────────────────────────────────────┘
```

## Yelb Services (replaces Online Boutique's 11 services)

| Service    | Role          | Technology      | Traces | Metrics        |
|------------|---------------|-----------------|--------|----------------|
| yelb-ui    | Frontend      | Angular + nginx | No     | Blackbox probe |
| yelb-appserver | Middleware   | Ruby + Sinatra + OTEL | Yes | Blackbox probe + OTEL |
| yelb-db    | Database      | PostgreSQL      | No     | Blackbox probe (TCP) |
| redis-server | Cache      | Redis           | No     | Blackbox probe (TCP) |

## Setup

### Prerequisites
- minikube (running, 4+ CPUs, 8GB+ RAM)
- kubectl
- helm

### Deploy

```bash
cd phase0
./scripts/setup.sh
```

### Verify

```bash
./scripts/verify.sh
```

### Access Dashboards

```bash
# Jaeger UI (traces)
kubectl port-forward svc/jaeger-query -n observability 16686:16686
# Open http://localhost:16686

# Prometheus UI (metrics)
kubectl port-forward svc/prometheus-kube-prometheus-prometheus 9090:9090
# Open http://localhost:9090

# Grafana (dashboards)
kubectl port-forward svc/prometheus-grafana 3000:80
# Open http://localhost:3000 (admin/prom-operator)
```

### Teardown

```bash
./scripts/teardown.sh
```

## Fault Injection

```bash
# Inject 500ms latency into yelb-appserver for 120 seconds
./scripts/fault-inject.sh latency yelb-appserver 500 120

# Inject 500ms latency into yelb-db for 120 seconds
./scripts/fault-inject.sh latency yelb-db 500 120

# Scale yelb-db to 0 replicas (simulate outage) for 120 seconds
./scripts/fault-inject.sh scale-down yelb-db 0 120

# Remove latency manually
./scripts/remove-latency.sh yelb-appserver
```

### Verify Fault Injection

1. Inject latency: `./scripts/fault-inject.sh latency yelb-appserver 500 120`
2. Wait 2 minutes
3. Check Jaeger: Appserver span durations should increase by ~500ms
4. Check Prometheus: `probe_duration_seconds{instance="http://yelb-appserver:4567/api/getvotes"}` should spike
5. After 120s, latency is auto-removed

## Observability Checklist

- [ ] Jaeger shows traces with yelb-appserver spans
- [ ] Prometheus queries return CPU/memory metrics for Yelb pods
- [ ] Prometheus shows HTTP probe success and latency for Yelb endpoints
- [ ] Grafana Yelb Observability Dashboard shows live data
- [ ] Injecting latency into a service shows up in both Jaeger and Prometheus