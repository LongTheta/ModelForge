# Deploy AegisML locally (Kubernetes)

Step-by-step instructions to run the **AegisML** inference service on a **local Kubernetes cluster** using **kind** (recommended) or **minikube**. The guide uses the **dev** overlay: `aegisml/k8s/overlays/dev` (namespace `aegisml-dev`, single replica).

**What you will do:** create a cluster → build and load the container image → apply manifests → port-forward → call `/predict`.

### On this page

- [Prerequisites](#prerequisites)
- [Path A: kind](#path-a-kind-recommended)
- [Path B: minikube](#path-b-minikube)
- [Troubleshooting](#troubleshooting)
- [Quick reference](#quick-reference)

### At a glance (kind)

1. `kind create cluster --name aegisml`
2. `docker build -f aegisml/docker/Dockerfile -t registry.example.com/aegisml:aegisml-latest aegisml` (from repo root)
3. `kind load docker-image registry.example.com/aegisml:aegisml-latest --name aegisml`
4. `kubectl apply -k aegisml/k8s/overlays/dev`
5. `kubectl port-forward -n aegisml-dev svc/aegisml-inference 8080:8080`
6. `curl` → `/healthz`, `/readyz`, `POST /predict` (see **Path A — Step 6** below)

### Without Kubernetes (optional)

To run the container **only with Docker** (no cluster), see **`aegisml/docker-compose.yml`**: from **`aegisml/`** run `docker compose up --build`, then hit `http://127.0.0.1:8080` the same way. This guide focuses on **kind** / **minikube**.

---

## Prerequisites

| Tool | Notes |
|------|--------|
| [Docker](https://docs.docker.com/get-docker/) | Engine running (Docker Desktop on Windows/macOS is fine). |
| [kubectl](https://kubernetes.io/docs/tasks/tools/) | v1.14+ (built-in Kustomize for `kubectl apply -k`). |
| **kind** *or* **minikube** | Install one; you do not need both. |
| Shell | Bash, zsh, **PowerShell 5+**, Git Bash, or WSL. |

**Repository layout:** all paths assume the **repository root** contains an `aegisml/` directory (the ModelForge / AegisML repo). Change directory to that root before running commands.

**Pick one path:**

- **[Path A — kind](#path-a-kind-recommended)** — fast, lightweight, loads images with `kind load docker-image`.
- **[Path B — minikube](#path-b-minikube)** — build inside the minikube Docker daemon so the node sees the image without `kind load`.

---

## Path A: kind (recommended)

### Step 1 — Create the cluster

```bash
kind create cluster --name aegisml
kubectl config use-context kind-aegisml
kubectl cluster-info
```

You should see `Kubernetes control plane is running at ...`.

**Optional:** list clusters with `kind get clusters`.

### Step 2 — Build the container image

The dev overlay expects image **`registry.example.com/aegisml:aegisml-latest`** (see `aegisml/k8s/overlays/dev/kustomization.yaml`). Build from the **repository root** with context `aegisml/`:

```bash
docker build \
  -f aegisml/docker/Dockerfile \
  --build-arg GIT_COMMIT=local \
  --build-arg VERSION=local-dev \
  -t registry.example.com/aegisml:aegisml-latest \
  aegisml
```

Confirm the image exists:

```bash
docker image ls registry.example.com/aegisml:aegisml-latest
```

### Step 3 — Load the image into kind

kind nodes do not use your host Docker cache unless you load the image:

```bash
kind load docker-image registry.example.com/aegisml:aegisml-latest --name aegisml
```

**Important:** after **every** image rebuild, run `kind load docker-image` again before expecting a new Pod to pick it up.

### Step 4 — Apply manifests (dev overlay)

From the **repository root**:

```bash
kubectl apply -k aegisml/k8s/overlays/dev
```

This creates (among other objects) namespace **`aegisml-dev`**, the Deployment, Service, and ConfigMap.

Wait for the rollout:

```bash
kubectl rollout status deployment/aegisml-inference -n aegisml-dev --timeout=180s
kubectl get pods -n aegisml-dev -o wide
```

Expect **`Running`** and **`READY 1/1`**. The first start can take **30–90 seconds** while the model loads and probes succeed (`startupProbe` / `readinessProbe` on `/readyz`).

### Step 5 — Port-forward the Service

The Service is **ClusterIP**. Forward local **8080** to the service:

```bash
kubectl port-forward -n aegisml-dev svc/aegisml-inference 8080:8080
```

Leave this process running. Use another terminal for tests.

### Step 6 — Test `/predict` and health endpoints

**Health checks**

```bash
curl -sS http://127.0.0.1:8080/healthz
curl -sS http://127.0.0.1:8080/readyz
```

`/healthz` returns `{"status":"ok"}`. `/readyz` returns `{"status":"ready"}` when the classifier is loaded; if the model is still starting, you may get **503** with a JSON body `{"error":{"code":"model_not_ready",...}}`—wait and retry.

**Predict (main test)**

```bash
curl -sS -X POST http://127.0.0.1:8080/predict \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"production outage sev1 customer impact\"}"
```

You should see JSON with **`label`**, **`confidence`**, **`scores`**, and **`model_version`**.

**Optional — metrics**

```bash
curl -sS http://127.0.0.1:8080/metrics | head -20
```

**Windows (no `curl`):** in PowerShell you can use:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8080/healthz" -Method Get
Invoke-RestMethod -Uri "http://127.0.0.1:8080/predict" -Method Post -ContentType "application/json" -Body '{"text":"production outage sev1 customer impact"}'
```

### Step 7 — Tear down (kind)

```bash
kubectl delete -k aegisml/k8s/overlays/dev
kind delete cluster --name aegisml
```

---

## Path B: minikube

### Step 1 — Start minikube

```bash
minikube start
kubectl config use-context minikube
minikube status
```

### Step 2 — Point Docker at minikube’s daemon

Images must be built **where the node can see them** (minikube’s Docker), not only on the host.

**macOS / Linux (bash):**

```bash
eval "$(minikube docker-env)"
```

**PowerShell:**

```powershell
minikube docker-env | Invoke-Expression
```

Verify Docker points at minikube (output should mention the minikube context):

```bash
docker info
```

### Step 3 — Build the image (same tag as dev overlay)

From the **repository root**:

```bash
docker build \
  -f aegisml/docker/Dockerfile \
  --build-arg GIT_COMMIT=local \
  --build-arg VERSION=local-dev \
  -t registry.example.com/aegisml:aegisml-latest \
  aegisml
```

You do **not** run `kind load` on minikube.

### Step 4 — Apply manifests and wait

```bash
kubectl apply -k aegisml/k8s/overlays/dev
kubectl rollout status deployment/aegisml-inference -n aegisml-dev --timeout=180s
kubectl get pods -n aegisml-dev
```

### Step 5 — Access the Service

**Option A — port-forward (same as kind)**

```bash
kubectl port-forward -n aegisml-dev svc/aegisml-inference 8080:8080
```

**Option B — minikube service URL**

```bash
minikube service aegisml-inference -n aegisml-dev --url
```

Use the printed URL for `curl` / browser tests.

### Test the API (same as kind)

Use the same **`curl`** / PowerShell commands as in **Path A — Step 6** (health, `/predict`, optional `/metrics`).

### Step 7 — Reset Docker to your host (optional)

After `minikube docker-env`, switch back when you are done:

**bash:** `eval "$(minikube docker-env -u)"`  
**PowerShell:** `minikube docker-env -u | Invoke-Expression`

### Step 8 — Tear down (minikube)

```bash
kubectl delete -k aegisml/k8s/overlays/dev
minikube delete
```

---

## Troubleshooting

### Wrong Kubernetes context

**Symptoms:** `kubectl apply` targets another cluster; resources appear in the wrong place.

**Fix:**

```bash
kubectl config get-contexts
# kind:
kubectl config use-context kind-aegisml
# minikube:
kubectl config use-context minikube
```

### `ImagePullBackOff` or `ErrImagePull`

**Causes:** Node cannot find `registry.example.com/aegisml:aegisml-latest`.

**Fix (kind):**

1. Rebuild with the **exact** tag the overlay uses: `registry.example.com/aegisml:aegisml-latest`.
2. Run `kind load docker-image registry.example.com/aegisml:aegisml-latest --name aegisml` again.
3. Confirm cluster name matches: `kind get clusters`.

**Fix (minikube):**

1. Run `eval "$(minikube docker-env)"` (or PowerShell equivalent) **before** `docker build`.
2. Rebuild the image and delete the pod to recreate: `kubectl delete pod -n aegisml-dev -l app.kubernetes.io/component=inference`.

### Pod `CrashLoopBackOff`

**Inspect:**

```bash
kubectl describe pod -n aegisml-dev -l app.kubernetes.io/component=inference
kubectl logs -n aegisml-dev -l app.kubernetes.io/component=inference --tail=100
kubectl logs -n aegisml-dev -l app.kubernetes.io/component=inference --previous
```

**Common causes:** wrong CPU architecture for image layers, app panic, or mis-set `AEGISML_*` env (compare with `aegisml/k8s/base` and overlays).

### Pod stays `0/1` Ready

**Causes:** Readiness (`/readyz`) or startup probe failing while the model loads or on errors.

**Fix:**

1. Check logs (above).
2. If `/healthz` works but `/readyz` does not, the process is up but the model is not ready—inspect application logs.
3. Wait up to **~60–90s** on first start; then re-check `kubectl get pods -n aegisml-dev`.

### `connection refused` on `127.0.0.1:8080`

**Causes:** Port-forward not running, wrong port, or wrong namespace/service name.

**Fix:**

```bash
kubectl get svc -n aegisml-dev
kubectl port-forward -n aegisml-dev svc/aegisml-inference 8080:8080
```

If port **8080** is busy locally:

```bash
kubectl port-forward -n aegisml-dev svc/aegisml-inference 18080:8080
curl -sS http://127.0.0.1:18080/healthz
```

### `kubectl apply -k` fails

**Causes:** Very old `kubectl` without Kustomize, or invalid YAML.

**Fix:** Upgrade kubectl, or render and apply manually:

```bash
kubectl kustomize aegisml/k8s/overlays/dev | kubectl apply -f -
```

Validate without applying:

```bash
kubectl kustomize aegisml/k8s/overlays/dev | kubectl apply --dry-run=client -f -
```

### Namespace stuck or resources left over

```bash
kubectl get all -n aegisml-dev
kubectl delete -k aegisml/k8s/overlays/dev --wait=true
```

If the namespace hangs in `Terminating`, search for stuck finalizers or foreground resources (advanced); often `kubectl delete namespace aegisml-dev --force --grace-period=0` is a last resort (use with care).

### Windows-specific issues

- Use **one** consistent environment (PowerShell, Git Bash, or WSL) for Docker, kubectl, and kind/minikube.
- Ensure Docker Desktop is **running** and **Kubernetes** is not conflicting if you enabled Docker’s bundled K8s (prefer kind/minikube with Docker Desktop’s engine only).
- Path separators: stay in the repo root; avoid mixing `cd` drives mid-script.

### minikube: image still not found

- Confirm `minikube docker-env` was active **during** `docker build`.
- Run `minikube image ls` (newer minikube) or inspect inside: `minikube ssh -- docker images`.

### `422` from `POST /predict`

**Cause:** Request body failed validation (e.g. empty `"text"`, or missing JSON).

**Fix:** Send a non-empty string:

```bash
curl -sS -X POST http://127.0.0.1:8080/predict \
  -H "Content-Type: application/json" \
  -d "{\"text\":\"production outage sev1 customer impact\"}"
```

---

## Quick reference

| Step | kind | minikube |
|------|------|----------|
| Cluster | `kind create cluster --name aegisml` | `minikube start` |
| Image | `docker build ...` then `kind load docker-image ... --name aegisml` | `eval $(minikube docker-env)` then `docker build ...` |
| Deploy | `kubectl apply -k aegisml/k8s/overlays/dev` | same |
| Access | `kubectl port-forward -n aegisml-dev svc/aegisml-inference 8080:8080` | port-forward or `minikube service ... --url` |
| Test | `curl` → `/healthz`, `/predict` | same |

---

## Next steps

- **Production-shaped overlay:** `kubectl apply -k aegisml/k8s/overlays/prod` (different namespace, replicas, resources)—use a **real registry** image, not only a locally loaded tag.
- **GitOps:** point Argo CD at `aegisml/k8s/overlays/dev` or `prod` and replace `registry.example.com/...` with your GitLab Container Registry path.
