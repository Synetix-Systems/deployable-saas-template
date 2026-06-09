# Argo manifests

GitOps + CI for the k3s deployment. See [../deployment.md](../deployment.md) for
the full setup; this is the file inventory and apply order.

## App cluster (`argocd` / `kube-system` namespaces)

| File | Apply to | Purpose |
|---|---|---|
| `coredns-custom.yaml` | `kube-system` | forward `*.ts.net` → Tailscale MagicDNS so pods can pull from Harbor. Then `kubectl -n kube-system rollout restart deploy/coredns`. |
| `00-appproject.yaml` | `argocd` | Argo CD AppProject scoping the app. |
| `application.yaml` | `argocd` | the single Application — tracks `master`, renders `charts/app`, Image Updater annotations. |
| `image-updater.yaml` | `argocd` | Image Updater CR (v1.x) pointing at the Application. |

## Build cluster (`argo` / `argo-events` namespaces)

| File | Apply to | Purpose |
|---|---|---|
| `workflows/buildkitd.yaml` | `argo` | rootless BuildKit daemon (host sysctl prereq in the file header). |
| `workflows/ci-workflowtemplate.yaml` | `argo` | builds backend/frontend/postgres → Harbor `:latest` + `:<sha>`. |
| `events/eventbus.yaml` | `argo-events` | NATS EventBus. |
| `events/eventsource-webhook.yaml` | `argo-events` | receives git push webhooks (`:12000/push`). |
| `events/eventsource-ingress.yaml` | `argo-events` | NodePort `:30120` to expose the webhook (e.g. via `tailscale funnel`). |
| `events/sensor.yaml` | `argo-events` | on `master` push → submit the `app-ci` Workflow. |

## Before applying — replace placeholders

- `your-org/your-repo` → your GitHub repo (`00-appproject.yaml`, `application.yaml`, `ci-workflowtemplate.yaml`, `events/sensor.yaml`).
- `your-project` → your Harbor project path (`application.yaml`, `ci-workflowtemplate.yaml`).
- `harbor.tail41bc66.ts.net` is the shared registry host — change only if yours differs.

Required secrets (`regcred`, `github-creds`, `app-dotenv`, Argo CD repo cred)
are listed in [../deployment.md](../deployment.md#secrets).
