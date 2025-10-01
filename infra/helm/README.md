# Fintech Helm Chart

This chart deploys the Fintech FastAPI service with Prometheus metrics, OpenTelemetry tracing, and optional blue/green rollouts.

## Usage
```bash
helm dependency update infra/helm/fintech
helm template fintech infra/helm/fintech \
  --set image.repository=ghcr.io/your-org/fintech \
  --set image.tag=sha-abcdef \
  --set blueGreen.enabled=true \
  --set blueGreen.activeColor=green
```

## Values
- `replicaCount`: number of pods for the active colour (default 2).
- `hpa.enabled`: toggles autoscaling using CPU utilisation.
- `blueGreen.enabled`: when true, the Service targets `blueGreen.activeColor` and a standby deployment is created using `blueGreen.standbyColor`.
- `env`: map of environment variables injected into the container.

## Files
- `templates/deployment.yaml` – primary deployment (defaults to `blue`).
- `templates/deployment-standby.yaml` – standby deployment when blue/green is enabled.
- `templates/service.yaml` – ClusterIP service exposing port 80.
- `templates/hpa.yaml` – optional HorizontalPodAutoscaler.
