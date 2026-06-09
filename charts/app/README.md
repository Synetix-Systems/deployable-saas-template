# `app` Helm chart

Deploys the full stack to k3s: backend + frontend (Argo Rollouts blue-green),
Celery workers + beat (canary), and infra (Postgres + WAL-G, pgbouncer, Redis).
Normally delivered by Argo CD (see [`../../argo`](../../argo) and
[`../../deployment.md`](../../deployment.md)); can also be `helm install`ed
directly.

## Requirements

- A k3s/Kubernetes cluster with Traefik (k3s default) and a default StorageClass (`local-path`).
- **Argo Rollouts CRDs + controller** — the backend/frontend/worker/beat workloads are `Rollout`s.
- Secrets `app-dotenv` (app env) and `regcred` (Harbor pull) in the target namespace — see deployment.md.

## Install

```bash
helm upgrade --install app ./charts/app -n app --create-namespace
```

The `prestart` Job (Argo Sync hook; an ordinary Job under plain Helm) runs
alembic migrations + seeds the first superuser before the app pods take traffic.

## Layout

| Template | Resources |
|---|---|
| `backend-rollout.yaml` / `frontend-rollout.yaml` | Rollout + active/preview Services (blue-green) |
| `workers-rollout.yaml` | one Rollout per `values.workers` queue + beat |
| `db.yaml` | Postgres StatefulSet (postgres+WAL-G image) with pgbackup sidecar, PVC |
| `pgbouncer.yaml` / `redis.yaml` | connection pooler / Celery broker+backend |
| `prestart-job.yaml` | migrations + seed (sync-wave 1) |
| `configmaps.yaml` | `app-env` topology ConfigMap + pg_hba / entrypoint scripts |
| `ingress.yaml` | Traefik, single host: `/api`,`/docs`,`/redoc`→backend, `/`→frontend |

## Key values

| Key | Default | Notes |
|---|---|---|
| `domain` | `app.example.com` | ingress host + email links — CHANGE ME |
| `image.registry` | `harbor.tail41bc66.ts.net` | shared Harbor over the tailnet |
| `image.{backend,frontend,postgres}.repo` | `your-project/*` | Harbor project path — CHANGE ME |
| `image.{backend,frontend}.image` | `""` | full ref; Argo Image Updater writes the digest here |
| `backend.replicas` / `frontend.replicas` | `2` / `2` | |
| `workers` | `{default, emails}` | queue → `{concurrency, replicas}`; names match `celery_app` routes |
| `workersGracePeriod` | `600` | max warm-shutdown drain (sec) before SIGKILL; raise above your longest task |
| `walg.s3Prefix` / `walg.endpoint` | placeholders | external S3 backup target — CHANGE ME |
| `env.*` | topology | ConfigMap, **overrides** the `app-dotenv` Secret on conflicts |

See [`values.yaml`](values.yaml) for the full list. The frontend image bakes
its API origin at build time, but this template's SPA calls the API same-origin
at `/api`, so no per-domain rebuild is needed.
