# Deployment

This project deploys to **k3s** via the Helm chart in [`charts/app`](charts/app),
delivered by **Argo CD** with a GitOps pipeline. There is **one environment**
(production). Docker Compose is for [local development](development.md) only —
it is never used to deploy.

## Topology

Two machines on a Tailscale tailnet:

| Machine | Cluster context | Runs |
|---|---|---|
| **App server** | `app` | k3s + Traefik, Argo CD + Image Updater + Argo Rollouts, the app + infra (Postgres/Redis/pgbouncer), **Harbor registry** |
| **Build server** | `build` | k3s, Argo Workflows + Events, buildkitd (may be powered off when idle) |

```
GitHub push (master) ──webhook──▶ BUILD SERVER
                       Argo Events EventSource → Sensor → Argo Workflows
                          BuildKit build → push :latest + :<sha>
                                     │ over the tailnet
                          Harbor  harbor.tail41bc66.ts.net/your-project/*
                                     │
                               APP SERVER
                       Argo CD + Image Updater (polls :latest digest)
                                     │
                       Argo Rollouts: blue-green (backend/frontend),
                                      canary (workers/beat)
```

- **Config comes from GitHub** — Argo CD watches `charts/app` on `master`.
- **Images come from Harbor** over the tailnet.
- The app server runs its own Postgres/Redis — one database, one environment.

## Helm chart (`charts/app/`)

`values.yaml` holds everything (single env — no per-env overlay). Workloads are
**Argo Rollouts**, not Deployments:

| Workload | Strategy | Notes |
|---|---|---|
| backend, frontend | blueGreen (active + `-preview` Services) | Ingress targets the active Service |
| worker-{default,emails} | canary, maxSurge 1 / maxUnavailable 0 | Celery warm shutdown finishes in-flight tasks (grace `workersGracePeriod`, 600s) |
| beat | canary, maxSurge 0 / maxUnavailable 1 | singleton scheduler — never two beats |
| db (StatefulSet) | — | postgres + **pgbackup sidecar** (WAL-G) in one pod (`2/2`), shared PGDATA volume |
| redis, pgbouncer | plain Deployments | pinned images, no auto-update |

Argo CD **sync waves**: infra (0) → `prestart` Job (1, Sync hook, re-created
every sync — runs alembic migrations + seeds the superuser) → app Rollouts (2).

## Prerequisites (one-time, per cluster)

Install on the **app** cluster:

- k3s (ships Traefik + `local-path` storage).
- [Argo CD](https://argo-cd.readthedocs.io/), [Argo Rollouts](https://argo-rollouts.readthedocs.io/) CRDs + controller, [Argo Image Updater](https://argocd-image-updater.readthedocs.io/) (v1.x, CR-driven).
- `kubectl apply -f argo/coredns-custom.yaml` then `kubectl -n kube-system rollout restart deploy/coredns` (lets pods resolve `*.ts.net` Harbor).

Install on the **build** cluster:

- Argo Workflows + Argo Events.
- `kubectl apply -f argo/workflows/buildkitd.yaml` (rootless BuildKit — see the file header for the host sysctl prereq).
- `kubectl apply -f argo/events/` (EventBus, EventSource, NodePort, Sensor), then expose the webhook (e.g. `tailscale funnel --bg http://localhost:30120`) and point your GitHub repo webhook (push events, JSON) at it.

## Secrets

Create these out-of-band (never committed):

| Secret | Namespace(s) | Cluster | Contents |
|---|---|---|---|
| `app-dotenv` | `app` | app | full app env, from your `.env` |
| `regcred` | `app`, `argocd` | app | Harbor docker-registry creds (image pull + Image Updater) |
| `regcred` | `argo` | build | same — BuildKit push |
| `github-creds` | `argo` | build | `username` + `token` (PAT, repo read) for cloning the private repo |
| repo credential | `argocd` | app | Argo CD repo access (label `argocd.argoproj.io/secret-type: repository`) |

`app-dotenv` is the **default home for all secret env** — `SECRET_KEY`,
`POSTGRES_PASSWORD`, `FIRST_SUPERUSER*`, `PROJECT_NAME` (required by pydantic —
no default!), SMTP, `S3_ACCESS_KEY_ID`/`S3_SECRET_ACCESS_KEY`, etc. Create it
from an env file:

```bash
kubectl --context app -n app create secret generic app-dotenv \
  --from-env-file=/path/to/prod.env
```

Harbor pull secret (quote the robot name — `$` expands otherwise):

```bash
kubectl --context app -n app create secret docker-registry regcred \
  --docker-server=harbor.tail41bc66.ts.net \
  --docker-username='robot$your-project+ci' --docker-password='<token>'
# repeat in the argocd namespace (Image Updater) and on the build cluster's argo ns
```

## Environment variable rules (READ BEFORE ADDING ENV)

Pods load env via `envFrom`: **Secret `app-dotenv` first, ConfigMap `app-env`
second → the ConfigMap wins on conflicts.**

- **Secret (`app-dotenv`)** = default home for everything (see above).
- **ConfigMap (chart `env:` block in `values.yaml`)** = ONLY:
  1. topology the chart must force (`POSTGRES_SERVER=pgbouncer`, `REDIS_URL`,
     `S3_ENDPOINT_URL`, domain/CORS) — your local `.env` may say `localhost`,
     the cluster value must win;
  2. keys other templates read (`POSTGRES_USER`/`POSTGRES_DB`, `S3_REGION`).

  Putting a user preference here silently overrides the Secret. Keep prefs out.
- Secret changes do NOT restart pods. After editing: re-sync the app (re-runs
  prestart) and delete pods that need the new env.

## What to change for your project

Search the placeholders and replace:

- `charts/app/values.yaml` — `domain`, `image.*.repo` (Harbor project path), `walg.s3Prefix`, `S3_*`, `FRONTEND_HOST`, `BACKEND_CORS_ORIGINS`.
- `argo/application.yaml` + `argo/00-appproject.yaml` — `repoURL`/`sourceRepos`, the Harbor `your-project` path in the image-list.
- `argo/workflows/ci-workflowtemplate.yaml` + `argo/events/sensor.yaml` — `repo` and the `your-project/*` image paths.

The registry host `harbor.tail41bc66.ts.net` is shared across projects — only
the project path differs.

## Deploy

Once bootstrapped, deploying is just:

```bash
git push origin master
```

Build (~1–2 min warm) → Image Updater (≤2 min digest poll) → blue-green roll.
Nothing manual.

### Watch a rollout

```bash
kubectl --context app -n argocd get applications
kubectl --context app -n app get rollouts,pods
kubectl --context build -n argo get wf            # builds
```

### Force a sync / re-run migrations (prestart)

```bash
kubectl --context app -n argocd patch application app \
  --type merge -p '{"operation":{"sync":{}}}'
```

Hooks use `BeforeHookCreation` — prestart is deleted + re-created each sync.

### Rollback

Every build also pushes an immutable `:<sha>` tag. Retag a previous SHA over
the rolling tag and Image Updater rolls back on the digest change:

```bash
crane copy harbor.tail41bc66.ts.net/your-project/backend:<old-sha> \
           harbor.tail41bc66.ts.net/your-project/backend:latest
```

(Or `git revert` + normal pipeline.)

## Manual install (no Argo CD)

The chart is plain Helm — you can install it directly for a one-off cluster.
The `prestart` Sync hook runs as an ordinary Job:

```bash
kubectl create namespace app
kubectl -n app create secret generic app-dotenv --from-env-file=prod.env
kubectl -n app create secret docker-registry regcred --docker-server=... ...
helm upgrade --install app ./charts/app -n app
```

Requires the Argo Rollouts CRDs + controller in the cluster (the Rollout
resources need the controller to progress).

## Database migrations under blue-green

Migrations run in the prestart Job **before** the green pods take traffic —
while the **blue pods still serve** the previous code. Any column/table the
blue code still uses must survive the migration, or blue pods 500 mid-rollout.

- Additive changes (new nullable columns, new tables, backfills) are always safe.
- **Never drop a column/table in the same release that removes the code using
  it.** Ship the `DROP` one release later, once no deployed code references it.

## URLs

Replace `app.example.com` with your domain.

- Frontend: `https://app.example.com`
- API docs: `https://app.example.com/docs`
- API base: `https://app.example.com/api`
