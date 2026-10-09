# Session 21 - DevOps Final Capstone: TaskBoard (Python)

This assignment takes the TaskBoard application (React + FastAPI + PostgreSQL) through the full path described in the session README: run it locally, test it, put it in Git/GitHub, containerise it, run CI/CD with a Trivy security gate, describe the AWS infrastructure with Terraform, deploy it to Kubernetes with Helm, expose it with Ingress, autoscale it with an HPA, monitor it with Prometheus + Grafana, and troubleshoot broken workloads.

```text
Developer → Git / GitHub → GitHub Actions (pytest → frontend build → Docker build → Trivy → GHCR)
         → Terraform (AWS VPC + EKS) → Helm → Kubernetes (Ingress, HPA) → Prometheus → Grafana
```

| | |
| :--- | :--- |
| **GitHub repository** | https://github.com/Ishan007-bot/session21-taskboard (public) |
| **Green pipeline runs** | [run #1](https://github.com/Ishan007-bot/session21-taskboard/actions/runs/37999694489) · [run #2 (live-demo commit)](https://github.com/Ishan007-bot/session21-taskboard/actions/runs/37999983958) |
| **Images** | `ghcr.io/ishan007-bot/taskboard-backend:<commit-sha>` and `ghcr.io/ishan007-bot/taskboard-frontend:<commit-sha>` |
| **Kubernetes** | local `kind` cluster `taskboard` (ingress-nginx, metrics-server, kube-prometheus-stack) |
| **Terraform** | `init` / `fmt` / `validate` / `plan` against real AWS (`ap-south-1`) |

## Prerequisites

All commands were run in **Windows PowerShell**.

| Tool | Version |
| :--- | :--- |
| Python | 3.12.10 |
| Node.js | 22.13.1 |
| Docker Desktop | 28.5.2 |
| kind / kubectl | v0.33.0 (Kubernetes v1.37.0) / v1.34.1 |
| Helm | v4.3.0 |
| Terraform | v1.16.5 (AWS provider v5.100.0) |
| Trivy | 0.75.0 |
| GitHub CLI | 2.92.0 |

The project was run from a working copy outside `devops-heros` (`Desktop\Devops\session21-taskboard`). That copy became the GitHub repository, so `.venv`, `node_modules`, Terraform state and test databases never land in this repo. Every file that had to change is copied into [fixed-files/](fixed-files/), with the same paths as the project.

## Bugs found and fixed while running the project

Running everything exactly as the README describes surfaced these problems. Each one is a separate commit in the GitHub repository.

| # | Area | Problem (as shipped) | Fix |
| :- | :--- | :--- | :--- |
| 1 | Compose | `postgres` publishes `5432:5432`; port 5432 was already used by a local PostgreSQL service | Host port changed to `5433:5432` |
| 2 | Compose | `depends_on: [postgres]` only waits for the container to *start*, so the backend ran `alembic upgrade head` before Postgres accepted connections, crashed and stayed down | Postgres `healthcheck` (`pg_isready`) + `condition: service_healthy` |
| 3 | Git | `.gitignore` did not exclude `.venv`, `__pycache__`, `.pytest_cache` or `test.db` (required by the rubric) | Added them |
| 4 | Tests | `TestClient(app)` without `with` never runs the startup event, so the `tasks` table was never created: `test_create_task_validation` failed with `no such table: tasks`. Only 3 tests existed (rubric asks for 5+) | `tests/conftest.py` fixture with a fresh SQLite schema per test; 12 tests covering every endpoint |
| 5 | Docker | Frontend image ran Nginx as **root** (rubric requires non-root) | `nginxinc/nginx-unprivileged`, `USER 101`, port **8080** |
| 6 | Security | Trivy gate (`HIGH,CRITICAL`, `--ignore-unfixed`, exit code 1) failed both images: backend had 3 HIGH CVEs in Starlette 0.41.3; frontend had 41 HIGH/CRITICAL in the Alpine 3.21 base | FastAPI 0.143.0 + prometheus-fastapi-instrumentator 8.1.0 (Starlette 1.7.0); `nginx-unprivileged:1.29-alpine` + `apk upgrade`. Both scans: **0** |
| 7 | Terraform | Every block was written on one line, which HCL rejects: `Invalid single-argument block definition` | Rewritten as normal multi-line HCL, `terraform.tfvars.example` added |
| 8 | Helm | Frontend Nginx proxies `/api` to `http://backend:8000` (the compose name). No Service called `backend` exists in the chart, so Nginx exited: `host not found in upstream "backend"` → CrashLoopBackOff | Added a `backend` alias Service |
| 9 | Helm | Ingress sent `/api` to Service `taskboard-backend` port `8080`, but the chart creates `taskboard-taskboard-backend` on port `8000` | Ingress uses `{{ include "taskboard.fullname" . }}-backend:8000` |
| 10 | Helm | Backend pods crash-looped until Postgres was ready (same race as #2) | `wait-for-postgres` init container (`pg_isready`) |
| 11 | Helm | Frontend container/probes/Service still pointed at port 80 | Changed to 8080 (follows fix #5) |
| 12 | Script | `load-test.sh` called `/api/health`, which does not exist (`/health` is not under `/api`), so every request was a 404 | URL changed to `/api/tasks` |
| 13 | CI | `ghcr.io/${{ github.repository_owner }}` keeps the uppercase in `Ishan007-bot`; Docker image names must be lowercase | A step lowercases the owner into `$OWNER` |
| 14 | CI | The `deploy` job needs a `KUBE_CONFIG_DATA` secret for a cluster GitHub can reach; a local kind cluster is not reachable, so the job could only fail | The job runs only when the repository variable `DEPLOY_ENABLED` is `true`; otherwise it is skipped (grey), not failed |
| 15 | CI | Trivy now installs from Aqua's official apt repository (the same method as Session 17) instead of a third-party action tag | Same flags: `--severity HIGH,CRITICAL --ignore-unfixed --exit-code 1` |

---

## 1. Application (Part A + B)

### 1.1 Docker Compose (`docker compose up --build`)

The first run failed because port 5432 belongs to a local `postgres.exe` service:

![Compose port conflict](01-application/01-compose-port-conflict.png)

After moving Postgres to host port 5433, the stack built. The backend then exited because it started before Postgres was ready:

![Fix port and build](01-application/02-fix-port-and-build.png)

![Backend startup race](01-application/03-backend-startup-race.png)

A Postgres healthcheck with `condition: service_healthy` fixes the startup order. Compose now shows `Healthy` before starting the backend, and Alembic runs `0001_create_tasks`:

![Healthcheck fix](01-application/04-healthcheck-fix.png)

![Compose ps](01-application/05-compose-ps.png)

### 1.2 Frontend (http://localhost:3000)

| Empty board | Create-task modal |
| :---: | :---: |
| ![Empty](01-application/06-ui-empty.png) | ![Modal](01-application/07-ui-create-modal.png) |

| Task created | Dashboard after API calls |
| :---: | :---: |
| ![Created](01-application/08-ui-task-created.png) | ![Dashboard](01-application/10-ui-dashboard.png) |

| "In progress" filter | Mobile width (400px) |
| :---: | :---: |
| ![Filter](01-application/11-ui-filter-in-progress.png) | ![Mobile](01-application/12-ui-mobile.png) |

### 1.3 REST API (create / read / update / delete)

Three tasks created with `POST`, one updated with `PUT`, one read with `GET` and deleted with `DELETE`. Reading it again returns `404 Task not found`, and `/api/tasks/stats` counts by status:

![API CRUD](01-application/09-api-crud.png)

Swagger UI at http://localhost:8000/docs:

![Swagger](01-application/13-swagger-docs.png)

### 1.4 `/health`, `/ready`, `/metrics`

- `/health` is the cheap liveness check.
- `/ready` runs a real query, so it fails when the database is down.
- `/metrics` exposes Prometheus counters per handler, method and status.
- The frontend's `/health` route is proxied by Nginx to the backend.

![Health ready metrics](01-application/14-health-ready-metrics.png)

### 1.5 Database

The `tasks` table is managed by Alembic (`alembic_version = 0001_create_tasks`):

![Postgres table](01-application/15-postgres-table.png)

### 1.6 Backend run directly (Part B)

The README's `python -m venv` + `source .venv/bin/activate` becomes `.\.venv\Scripts\python.exe` in PowerShell. The compose backend was stopped first so port 8000 was free, and `DATABASE_URL` points at the compose Postgres on 5433:

![venv install](01-application/16-backend-venv-install.png)

![Alembic](01-application/17-backend-alembic.png)

Uvicorn was started in a second (background) process; its log and the `curl` checks are shown:

![Uvicorn direct](01-application/18-uvicorn-direct.png)

---

## 2. Testing (Part C)

The rubric needs `.venv`, `__pycache__` etc. ignored, so `.gitignore` was fixed first:

![gitignore fix](02-testing/01-gitignore-fix.png)

The original suite fails: `TestClient(app)` is created without `with`, so FastAPI's startup event (`create_all`) never runs and SQLite has no `tasks` table:

![pytest original fails](02-testing/02-pytest-original-fails.png)

The fix is `tests/conftest.py`:

- It sets `DATABASE_URL=sqlite:///./test.db` before the app is imported, so the tests never touch Postgres.
- It gives every test a fresh schema (`drop_all` and then `with TestClient(app)`, which runs startup).

The tests grew from 3 to 12. They cover `/`, `/health`, `/ready`, `/metrics`, list, get, the 404 path, create, validation (empty title, unknown priority), update, delete and stats.

![Tests fixed](02-testing/03-tests-fixed.png)

![pytest -v](02-testing/04-pytest-v-pass.png)

![pytest -q](02-testing/05-pytest-q-pass.png)

**Why tests run before images are pushed:** in the pipeline, `build-scan-push` has `needs: test`. If pytest fails, the job stops, no image is built, and nothing broken reaches the registry. This is the first quality gate.

---

## 3. Git and GitHub (Part D)

The repository started from the unchanged project as the first commit:

![git init](03-git-github/01-git-init.png)

Every fix became its own commit with a descriptive message. The repo was then created as **public** and pushed with `gh repo create ... --push`, which does `git remote add origin` + `git push -u origin main` in one step:

![Create repo and push](03-git-github/02-create-repo-push.png)

There are 14 commits in total:

![Commit history](03-git-github/03-commit-history.png)

![Repository page](03-git-github/04-repo-page.png)

| Term | Meaning |
| :--- | :--- |
| Git | Version control: the full history of every file |
| GitHub | The remote platform for sharing, reviewing and automating (Actions, GHCR) |
| Commit | An immutable checkpoint of the project with a message, author and parent |
| Branch | An isolated line of development (`main` here) |
| Pull request | A reviewed, tested proposal to merge a branch; the workflow also runs on `pull_request` |

---

## 4. Docker (Part E)

### 4.1 Backend image

`python:3.12-slim` → install requirements → copy Alembic + app → user `appuser` (uid 10001) → `alembic upgrade head && uvicorn`:

![Build backend](04-docker/01-build-backend.png)

### 4.2 Frontend image (multi-stage)

`node:22-alpine` runs `npm install` + `npm run build`, and only `dist/` is copied into the Nginx runtime image:

![Build frontend](04-docker/02-build-frontend.png)

The final image has **no `node`/`npm`**, only the static files. The backend runs as uid 10001, but the original frontend ran as **root**:

![Images and users](04-docker/03-images-and-users.png)

### 4.3 Running the backend image

`docker run` uses `host.docker.internal:5433` to reach the Postgres container published on the host:

![Run backend container](04-docker/04-run-backend-container.png)

### 4.4 Frontend as non-root

The fix:

- base `nginxinc/nginx-unprivileged`, which listens on 8080;
- `USER 101`;
- `nginx.conf` set to `listen 8080`;
- compose mapping `3000:8080`.

![Frontend non-root fix](04-docker/05-frontend-nonroot-fix.png)

![Compose rebuild](04-docker/06-compose-rebuild.png)

---

## 5. CI/CD - GitHub Actions (Part F)

The workflow [`.github/workflows/ci-cd.yml`](fixed-files/.github/workflows/ci-cd.yml) runs on every push and pull request to `main`:

```text
test  ──►  build-scan-push  ──►  deploy
 pytest      docker build ×2       helm upgrade --install
 npm build   trivy scan ×2         (only when DEPLOY_ENABLED=true)
             docker push ×2 (GHCR, tag = commit SHA)
```

Workflow changes: lowercase GHCR owner, Trivy from apt, and the gated deploy job.

![Workflow changes](05-cicd/01-workflow-changes.png)

**Run #1** (push of the whole project) was green in 1m40s:

![First run](05-cicd/02-first-run-summary.png)

The test job ran 12 pytest tests and the Vite production build:

![Test job log](05-cicd/03-test-job-log.png)

Both images were pushed to GHCR, tagged with the commit SHA (`eb00f98…`), not `latest`:

![GHCR push log](05-cicd/04-ghcr-push-log.png)

### Live demo: commit a change → pipeline → deployment

The application change replaces the hard-coded greeting and profile ("Good morning, Nensi" / "Nensi Ravaliya") with Ishan's name. It was committed and pushed, and that push started run #2:

![Demo commit push](05-cicd/05-demo-commit-push.png)

![Demo run green](05-cicd/06-demo-run-green.png)

![Actions page](05-cicd/07-actions-page.png)

![Run graph](05-cicd/08-run-graph.png)

The `deploy` job shows as **skipped** because `DEPLOY_ENABLED` is not set. GitHub's runners cannot reach a kind cluster on a laptop. Section 8.4 shows the same `helm upgrade --set backend.tag=<sha>` done locally for that commit.

---

## 6. Security scanning - Trivy (Part G)

Local scans with the same gate as the pipeline (`--severity HIGH,CRITICAL --ignore-unfixed --exit-code 1`).

The original backend had 3 HIGH findings in **Starlette 0.41.3**, pulled in by FastAPI 0.115.6:

- CVE-2025-62727: DoS via Range header merging;
- CVE-2026-48818: SSRF/NTLM leak via UNC paths in StaticFiles;
- CVE-2026-54283: `request.form()` limits ignored.

![Trivy backend before](06-security-trivy/01-trivy-local-backend.png)

The original frontend had 41 HIGH/CRITICAL findings in the old **Alpine 3.21** base: openssl, libxml2, musl, zlib, nghttp2, tiff, c-ares, libexpat and libpng.

![Trivy frontend before](06-security-trivy/02-trivy-local-frontend.png)

Fixes applied:

- FastAPI 0.143.0 with prometheus-fastapi-instrumentator 8.1.0, which allows Starlette 1.x. Instrumentator 7.0.2 pinned Starlette below 1.0, so it kept resolving to a vulnerable 0.x.
- The frontend runtime moved to `nginx-unprivileged:1.29-alpine` (Alpine 3.23) plus `apk upgrade`.

All 12 tests still pass on the new versions.

![CVE fixes](06-security-trivy/03-cve-fixes.png)

![Trivy backend clean](06-security-trivy/04-trivy-clean-backend.png)

![Trivy frontend clean](06-security-trivy/05-trivy-clean-frontend.png)

The same clean result inside the pipeline:

![CI Trivy log](06-security-trivy/06-ci-trivy-log.png)

**What Trivy scanned and what the result means:** Trivy scanned both container images: the OS packages (Debian 13 for the backend, Alpine 3.23 for the frontend) and the installed Python packages. It compared them with known CVEs. The gate fails the job on any HIGH or CRITICAL finding that already has a fixed version (`--ignore-unfixed`). The final result is 0 for both images, so the pipeline pushed them; the first scan proved the gate works, because it would have blocked 44 known issues.

Trivy is only one of the security layers:

| Layer | Example |
| :--- | :--- |
| SAST | CodeQL, Bandit (source code) |
| Dependency scanning | pip-audit, Trivy `python-pkg` |
| Secret scanning | Gitleaks, GitHub secret scanning |
| Container scanning | Trivy image scan (this pipeline) |
| Runtime security | non-root containers, network policies, Falco |

---

## 7. Terraform - AWS VPC + EKS (Part H)

The original files were single-line blocks, which Terraform refuses to parse:

![Original HCL error](07-terraform/01-original-hcl-error.png)

The same configuration was rewritten as normal HCL, and `terraform.tfvars.example` was added:

![HCL fixed](07-terraform/02-hcl-fixed.png)

`init` downloads the `terraform-aws-modules/vpc` (5.8.1) and `eks` (20.37.1) modules and the providers. `fmt -check` and `validate` pass:

![init fmt validate](07-terraform/03-init-fmt-validate.png)

`terraform plan` against the real AWS account `014512981147` gives **54 to add**:

![Plan summary](07-terraform/04-plan-summary.png)

![Plan details](07-terraform/05-plan-vpc-eks-details.png)

What the plan creates in `ap-south-1`:

| Resource | Detail |
| :--- | :--- |
| VPC | `taskboard-vpc`, `10.20.0.0/16` |
| Public subnets | `10.20.101.0/24` (ap-south-1a), `10.20.102.0/24` (ap-south-1b) + Internet Gateway route |
| Private subnets | `10.20.1.0/24`, `10.20.2.0/24` + a single NAT gateway (with Elastic IP) |
| EKS cluster | `taskboard-eks`, Kubernetes 1.31, public endpoint, KMS-encrypted secrets, CloudWatch log group, OIDC provider |
| Node group | managed group `main`, `t3.medium`, min 2 / desired 2 / max 4, in the private subnets |
| Access | the identity running Terraform gets cluster-admin (`enable_cluster_creator_admin_permissions`) |

> **Why there is no `apply`/`destroy` here:**
> - The only AWS identity available (`terraform-student`) has no EC2/EKS permissions.
> - That account's AWS Organization also blocks S3 (see Sessions 18-19).
> - An EKS control plane plus NAT gateway is billed per hour.
> - LocalStack's free edition cannot emulate EKS.
>
> The code is valid and fully planned. With permissions, the next steps are `terraform apply`, then `aws eks update-kubeconfig --region ap-south-1 --name taskboard-eks`, then `terraform destroy`. Nothing was created, so the state is empty (section 12).

---

## 8. Kubernetes + Helm (Part I + J)

### 8.1 Local cluster

A kind cluster stands in for EKS. [`k8s/kind-config.yaml`](fixed-files/k8s/kind-config.yaml) labels the node `ingress-ready=true` and maps host ports 80/443, so ingress-nginx is reachable on `localhost`:

![kind cluster](08-kubernetes-helm/01-kind-cluster.png)

ingress-nginx is the Ingress **Controller**; the Ingress object on its own does nothing. metrics-server is needed by the HPA. On kind it needs `--kubelet-insecure-tls`.

![Ingress and metrics-server](08-kubernetes-helm/02-ingress-metrics-server.png)

The locally built images were loaded into the node, and `k8s/namespace.yaml` was applied:

![Load images and namespace](08-kubernetes-helm/03-load-images-namespace.png)

![Helm lint and template](08-kubernetes-helm/04-helm-lint-template.png)

### 8.2 First install - and what broke

`helm upgrade --install` succeeded, but the pods did not become ready:

![First install](08-kubernetes-helm/05-helm-install-first.png)

- **frontend:** `host not found in upstream "backend"`. Nginx refuses to start when a `proxy_pass` host does not resolve, and the chart has no `backend` Service.
- **backend:** `connection refused` to Postgres. Alembic ran before Postgres was ready.
- The Ingress template also pointed at the wrong Service name and port. It was not visible yet, because ingress is disabled in the default values.

![Debug crashloop](08-kubernetes-helm/06-debug-crashloop.png)

### 8.3 Chart fixes

The fixes were the `backend` alias Service, frontend port 8080, the correct Ingress backend and a `wait-for-postgres` init container:

![Chart fixes](08-kubernetes-helm/07-chart-fixes.png)

![Helm upgrade fixed](08-kubernetes-helm/08-helm-upgrade-fixed.png)

Everything is now Running:

- 2× backend, 2× frontend, 1× Postgres;
- the PVC is `Bound` (5Gi);
- the HPA reads CPU.

![Pods svc helm](08-kubernetes-helm/09-pods-svc-helm.png)

In-cluster checks from a curl pod:

- the init container logged `accepting connections`;
- `/ready` returns READY;
- the `backend` alias works;
- the frontend proxies `/api`.

![In-cluster checks](08-kubernetes-helm/10-in-cluster-checks.png)

| Concept | In this chart |
| :--- | :--- |
| Chart | `helm/taskboard` (`Chart.yaml` 1.0.0) |
| Values | `values.yaml` (defaults), `values-dev.yaml` (ingress on, 1 replica, HPA off), `values-prod.yaml` |
| Templates | backend/frontend Deployments and Services, Postgres (Secret, Service, Deployment, PVC), Ingress, HPA, ServiceMonitor |
| Release | `taskboard` in namespace `taskboard` |
| Upgrade / rollback | every `helm upgrade` adds a revision (`helm history`); `helm rollback taskboard <rev>` returns to one |
| Deployment | keeps the requested replicas; replaces any pod that dies |
| Service | stable name + virtual IP in front of changing pod IPs |
| PostgreSQL | runs in-cluster with a PVC here; in production on AWS a managed database (Amazon RDS) is usually better: backups, failover and patching are handled for you |

### 8.4 Deploying the live-demo commit

This is the same thing the pipeline's deploy job does:

1. Build images tagged with the commit SHA (`4d2630c…`).
2. Load them into the cluster.
3. Run `helm upgrade --set backend.tag=<sha> --set frontend.tag=<sha>`.

The GHCR packages are private by default, and the local GitHub CLI token has no `read:packages` scope, so the cluster pulled locally built copies of the same commit.

![Deploy commit SHA](08-kubernetes-helm/11-deploy-commit-sha.png)

The UI through the Ingress now shows the change. The tasks created earlier survived the upgrades, because they live on the PVC:

![UI after demo change](08-kubernetes-helm/12-ui-after-demo-change.png)

---

## 9. Ingress + HPA (Part K + L)

### 9.1 Ingress

`values-dev.yaml` enables the Ingress for host `taskboard.local`, routing `/api` to the backend Service (8000) and `/` to the frontend Service (80 → 8080):

![Helm dev values ingress](09-ingress-hpa/01-helm-dev-values-ingress.png)

Instead of editing the Windows `hosts` file, which needs admin rights, requests send `Host: taskboard.local`. The browser maps `taskboard.local` to `127.0.0.1`. The ingress-nginx log shows each request going to the right upstream:

![Ingress curl](09-ingress-hpa/02-ingress-curl.png)

| UI via Ingress | API via Ingress |
| :---: | :---: |
| ![UI via ingress](09-ingress-hpa/03-ui-via-ingress.png) | ![API via ingress](09-ingress-hpa/04-api-via-ingress.png) |

### 9.2 HPA

The load-test script pointed at a route that returns 404:

![Load test URL fix](09-ingress-hpa/05-load-test-url-fix.png)

The HPA was enabled on top of the dev values:

- `minReplicas: 2`, `maxReplicas: 6`;
- target 60% CPU of the 100m request.

Idle usage was about 3%:

![Enable HPA](09-ingress-hpa/06-enable-hpa.png)

Four in-cluster load generators (`busybox` loops calling `/api/tasks`) created real CPU pressure:

![Start load](09-ingress-hpa/07-start-load.png)

CPU rose to about 264% of the request, and the HPA scaled **2 → 4 → 6** (the maximum) within about two minutes:

![HPA scaling](09-ingress-hpa/08-hpa-scaling.png)

After the load pods were deleted, CPU fell to 3%. After the 5-minute scale-down stabilisation window, the HPA went back to **2** (`All metrics below target`):

![HPA scale down](09-ingress-hpa/09-hpa-scale-down.png)

---

## 10. Monitoring - Prometheus + Grafana (Part M)

`kube-prometheus-stack` was installed with [`monitoring/prometheus-values.yaml`](../monitoring/prometheus-values.yaml). Setting `serviceMonitorSelectorNilUsesHelmValues: false` makes Prometheus pick up ServiceMonitors from every namespace.

![Install kube-prometheus-stack](10-monitoring/01-install-kube-prometheus-stack.png)

![Monitoring pods](10-monitoring/02-monitoring-pods.png)

The chart's ServiceMonitor scrapes the backend Service's `http` port at `/metrics` every 15s:

![ServiceMonitor and metrics](10-monitoring/03-servicemonitor-metrics.png)

Prometheus (through `kubectl port-forward svc/kube-prometheus-stack-prometheus -n monitoring 9091:9090`) showed:

- all 6 backend pods as targets, `health = up`, while the HPA was at 6;
- the request rate per handler (about 266 req/s on `/api/tasks`).

![Prometheus API](10-monitoring/04-prometheus-api.png)

The Targets page, after scale-down, shows the TaskBoard pool `2 / 2 up`:

![Prometheus targets UP](10-monitoring/06-prometheus-targets-up.png)

![Prometheus request rate](10-monitoring/07-prometheus-request-rate.png)

### Grafana

A dashboard was imported through the Grafana API from [`monitoring/taskboard-dashboard.json`](fixed-files/monitoring/taskboard-dashboard.json), using the chart's built-in `prometheus` data source:

![Grafana dashboard import](10-monitoring/05-grafana-dashboard-import.png)

The live panels answer the session's questions:

| Question | Panel |
| :--- | :--- |
| How much traffic is arriving? | Requests/sec, and by handler |
| Which endpoint is slow? | p95 latency by handler |
| Are errors increasing? | 5xx error rate |
| Is CPU increasing? | Backend CPU by pod |
| Is the HPA scaling? | Backend replicas (HPA) |

The load test is clearly visible: about 267 req/s, CPU rising on every pod, and replicas going 2 → 6.

![Grafana dashboard](10-monitoring/08-grafana-taskboard-dashboard.png)

---

## 11. Troubleshooting lab (Part N)

### 11.1 Broken image

`ghcr.io/example/taskboard-backend:does-not-exist` leads to `ErrImagePull` / `ImagePullBackOff`:

![Broken image apply](11-troubleshooting/01-broken-image-apply.png)

`describe` and the events show the cause: the registry refused the pull (`403 Forbidden`: the repository does not exist or is private).

![Broken image describe](11-troubleshooting/02-broken-image-describe.png)

The fix had two steps:

1. Point the Deployment at a real image (`kubectl set image`). The pull problem was gone, but the container then exited, because this standalone Deployment has no `DATABASE_URL`.
2. Add the env var (`kubectl set env`). The pod then ran `1/1 Running`.

![Broken image fix](11-troubleshooting/03-broken-image-fix.png)

```text
ImagePullBackOff → describe pod → wrong image/tag → fix image → next error (app config) → fix env → Running
```

### 11.2 Broken Service

The Service selects `app: label-that-does-not-exist`, so it has **no endpoints**. `curl` to it fails with exit code 7 (connection refused). `--show-labels` shows the real pods are labelled `app=taskboard-backend`.

![Broken service](11-troubleshooting/04-broken-service.png)

Patching the selector to `app: taskboard-backend` and `targetPort` to `8000` gives it endpoints, and `/health` answers:

![Broken service fix](11-troubleshooting/05-broken-service-fix.png)

**Lesson:** a Service finds pods only by labels. No matching labels means no endpoints, which means no traffic. `kubectl get endpoints` is the fastest check.

---

## 12. Cleanup

Removed:

- both Helm releases;
- the kind cluster;
- the compose stack and its volume (`down -v`).

Terraform state is empty, because nothing was applied.

![Cleanup](12-cleanup/01-cleanup.png)

---

## Final demo checklist (Part O)

| # | Step | Where |
| :- | :--- | :--- |
| 1 | Application: create a task | §1.2 |
| 2 | API: create / read / update / delete | §1.3, Swagger §1.3 |
| 3 | Database: `tasks` table | §1.5 |
| 4 | Git: small application change committed | §5 live demo |
| 5 | CI: push → tests running | §5 |
| 6 | Docker: two images | §4 |
| 7 | Security: Trivy scanning both images | §6 |
| 8 | Registry: SHA-tagged images in GHCR | §5 (push log) |
| 9 | Terraform: AWS infrastructure code + plan | §7 |
| 10 | Kubernetes: `get pods` / `get svc` | §8 |
| 11 | Helm: `helm list` / `history` | §8 |
| 12 | Ingress hostname | §9.1 |
| 13 | HPA | §9.2 |
| 14 | Prometheus + Grafana | §10 |
| 15 | Failure simulation | §11 |

## Grading rubric coverage

| Module | Evidence | Notes |
| :--- | :--- | :--- |
| M1 Application | §1 | 4+ REST endpoints, Alembic migration, responsive UI |
| M2 Testing | §2 | 12 tests, SQLite test DB through `conftest.py`, `pytest.ini` |
| M3 Git/GitHub | §3 | Public repo, 14 descriptive commits, `.gitignore` covers `.env`/`__pycache__`/`node_modules`/`.venv` |
| M4 Docker | §4 | Both images non-root, multi-stage frontend, `compose up --build` runs all 3 services |
| M5 CI/CD | §5 | Push to `main` → pytest → frontend build → 2 images → GHCR, tagged with the commit SHA |
| M6 Trivy | §6 | Both images scanned in CI, fails on HIGH/CRITICAL; findings explained |
| M7 Terraform | §7 | Valid HCL, `init`/`plan` (54 resources), tfvars example. `apply`/`destroy` not possible on the available account |
| M8 Kubernetes + Helm | §8, §9.1 | Namespace, chart, 2+ replicas each, ClusterIP Services, Ingress `/` + `/api`, all pods Running |
| M9 Observability | §10 | `/metrics`, ServiceMonitor targets UP, Grafana with live request/latency/CPU panels |
| M10 Documentation | this README + repo README | Live demo: commit → green pipeline → updated deployment |

## Key learnings

- **"Works on my machine" hides ordering bugs.** `depends_on` and Kubernetes both start containers without waiting for the database to be *ready*. Healthchecks, init containers and readiness probes make the order explicit.
- **Names are configuration.** The same Nginx config pointed at `backend`, which exists in Compose but not in the Helm release. Service names, ports and the release-prefixed `fullname` must agree across Deployment, Service, Ingress and ServiceMonitor.
- **A security gate is only useful if it can fail.** The first Trivy run would have blocked 44 known HIGH/CRITICAL issues. Fixing them meant reading the dependency chain, not only bumping the top-level package.
- **Tests must create their own world.** A fixture that builds a fresh schema per test makes them independent, fast and safe from production data.
- **HPA needs three things:** resource requests, a metrics source (metrics-server), and real load. Scale-up is fast; scale-down waits about 5 minutes on purpose to avoid flapping.
- **Plan is the safe half of Terraform.** `plan` showed exactly what an EKS environment costs in resources (54 objects including a NAT gateway and EKS control plane) before anything was created.
