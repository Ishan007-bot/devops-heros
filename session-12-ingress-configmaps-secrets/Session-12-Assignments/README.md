# Session 12 - Ingress, ConfigMaps, and Secrets

This assignment demonstrates how Kubernetes stores application configuration, protects sensitive values, and routes HTTP/HTTPS traffic through an NGINX Ingress Controller. The final exercise combines ConfigMap, Secret, Deployments, Services, and Ingress into one working application.

## Prerequisites

Start Minikube and use the Session 12 directory as the working directory:

```powershell
minikube start
cd session-12-ingress-configmaps-secrets
kubectl config current-context
kubectl get nodes
```

The expected context is `minikube`.

> These commands work in PowerShell. Bash uses `\` for line continuation, but PowerShell uses the backtick character or a single line. The examples below use single-line commands where possible.

## 1. ConfigMap

A ConfigMap stores non-sensitive configuration outside the container image. This allows the same image to run in different environments with different settings.

### Apply and inspect the ConfigMap

```powershell
kubectl apply -f 01-configmap/app-config.yaml
kubectl get configmap yatri-app-config
kubectl describe configmap yatri-app-config
kubectl get configmap yatri-app-config -o jsonpath='{.data.LOG_LEVEL}'
```

The ConfigMap contains five values:

```text
ENVIRONMENT=production
LOG_LEVEL=INFO
PORT=5000
DEFAULT_CURRENCY=INR
MAX_BOOKING_DAYS=30
```

The `jsonpath` command prints `INFO`. ConfigMaps are appropriate for values such as log levels, ports, feature flags, and API URLs, but not passwords, tokens, or private keys.

![ConfigMap applied and inspected](01-configmap/Screenshot%202026-09-20%20213737.png)
![ConfigMap value output](01-configmap/Screenshot%202026-09-20%20213917.png)

### Cleanup

```powershell
kubectl delete configmap yatri-app-config
```

## 2. Secret

A Secret stores sensitive values separately from ordinary configuration. The values in this exercise are Base64-encoded, which is encoding rather than encryption.

### Generate and inspect Base64 values

Use `-n` so that a newline is not included in the encoded value:

```powershell
echo -n "yatri_admin" | base64
echo -n "secretpassword" | base64
echo -n "yatri_production_db" | base64
```

The resulting values are:

```text
POSTGRES_USER:     eWF0cmlfYWRtaW4=
POSTGRES_PASSWORD: c2VjcmV0cGFzc3dvcmQ=
POSTGRES_DB:       eWF0cmlfcHJvZHVjdGlvbl9kYg==
```

### Apply and inspect the Secret

```powershell
kubectl apply -f 02-secret/db-secret.yaml
kubectl get secret yatri-db-secret
kubectl describe secret yatri-db-secret
```

Expected result:

```text
NAME               TYPE     DATA   AGE
yatri-db-secret    Opaque   3      ...
```

Kubernetes masks Secret values when they are described. To decode the password for this classroom demonstration, use the following PowerShell command:

```powershell
$encoded = kubectl get secret yatri-db-secret -o jsonpath='{.data.POSTGRES_PASSWORD}'
[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($encoded))
```

It prints `secretpassword`. On Linux or Git Bash, the equivalent is:

```bash
kubectl get secret yatri-db-secret -o jsonpath='{.data.POSTGRES_PASSWORD}' | base64 --decode
```

![Secret creation and inspection](02-secret/Screenshot%202026-09-20%20214802.png)

### Cleanup

```powershell
kubectl delete secret yatri-db-secret
```

## 3. Ingress and TLS

An Ingress is a Layer 7 routing definition. It requires an Ingress Controller; on Minikube, use the NGINX addon. The routes in this exercise send `/api` traffic to the backend and `/` traffic to the frontend.

### Enable the Ingress Controller

```powershell
minikube addons enable ingress
kubectl get pods -n ingress-nginx
kubectl wait --namespace ingress-nginx --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=120s
```

### Apply HTTP routes

```powershell
kubectl apply -f 03-ingress/ingress-routes.yaml
kubectl get ingress yatri-ingress
kubectl describe ingress yatri-ingress
```

The Ingress uses the host `yatri.local`, routes `/api` to `yatri-backend-service`, and routes `/` to `yatri-frontend-service`.

![Ingress routes](03-ingress/Screenshot%202026-09-20%20215502.png)

### Generate a self-signed TLS certificate

In PowerShell, use one line or PowerShell backticks. Do not use Bash backslashes:

```powershell
openssl req -x509 -nodes -days 365 -newkey rsa:2048 -keyout tls.key -out tls.crt -subj "/CN=campus.local/O=CampusDevOps"
```

Create the Kubernetes TLS Secret:

```powershell
kubectl create secret tls campus-tls-cert --cert=tls.crt --key=tls.key
kubectl get secret campus-tls-cert
```

Apply the TLS and multi-host Ingress:

```powershell
kubectl apply -f 03-ingress/ingress-tls.yaml
kubectl get ingress campus-ingress-tls
```

The expected Ingress output includes the hosts `portal.campus.local` and `api.campus.local`, with ports `80,443`.

## 4. Full ConfigMap + Secret + Ingress Demo

This demo deploys:

- A frontend NGINX application at `/`, configured through a ConfigMap.
- A backend Python API at `/api/`, configured through a ConfigMap and database Secret.
- One NGINX Ingress that routes both services.

### Enable Ingress and wait for the controller

```powershell
minikube addons enable ingress
kubectl wait --namespace ingress-nginx --for=condition=ready pod --selector=app.kubernetes.io/component=controller --timeout=120s
```

### Apply the application resources

```powershell
kubectl apply -f 04-full-demo/configmap.yaml
kubectl apply -f 04-full-demo/secret.yaml
kubectl apply -f 04-full-demo/frontend.yaml
kubectl apply -f 04-full-demo/backend.yaml
kubectl rollout status deployment/yatri-backend --timeout=90s
kubectl apply -f 04-full-demo/ingress.yaml
```

Inspect the resources:

```powershell
kubectl describe configmap yatri-app-config
kubectl describe secret yatri-db-secret
kubectl get pods -l app=yatri-frontend
kubectl get pods -l app=yatri-backend
kubectl get svc yatri-frontend-service yatri-backend-service
kubectl describe ingress yatri-ingress
```

### Configure the local hostname

Find the Minikube IP:

```powershell
minikube ip
```

Add this mapping to the Windows hosts file as Administrator:

```text
<minikube-ip> yatri.local
```

The file is located at `C:\Windows\System32\drivers\etc\hosts`.

### Test the frontend and backend

```powershell
curl http://yatri.local
curl http://yatri.local/api/
```

The frontend returns the NGINX page. The backend returns values such as `ENVIRONMENT`, `LOG_LEVEL`, `DEFAULT_CURRENCY`, `POSTGRES_USER`, and `POSTGRES_DB`. The password is intentionally not printed by the API.

Confirm that configuration and Secret values were injected into the backend pod:

```powershell
kubectl exec deploy/yatri-backend -- env
```

To filter the output in PowerShell:

```powershell
kubectl exec deploy/yatri-backend -- env | Select-String 'ENVIRONMENT|LOG_LEVEL|POSTGRES'
```

![Full demo resources](04-full-demo/Screenshot%202026-09-20%20220442.png)
![Full demo Ingress](04-full-demo/Screenshot%202026-09-20%20220451.png)
![Frontend through Ingress](04-full-demo/Screenshot%202026-09-20%20220506.png)
![Backend through Ingress](04-full-demo/Screenshot%202026-09-20%20220526.png)

### Automated deployment

The full demo also includes a script that enables Ingress, applies the resources, waits for the pods, and configures the local host entry:

```bash
bash 04-full-demo/run-demo.sh
```

On Windows, run it from Git Bash or WSL. PowerShell does not execute Bash scripts directly unless a Bash environment is installed.

### Cleanup

```powershell
kubectl delete -f 04-full-demo/ingress.yaml
kubectl delete -f 04-full-demo/backend.yaml
kubectl delete -f 04-full-demo/frontend.yaml
kubectl delete -f 04-full-demo/secret.yaml
kubectl delete -f 04-full-demo/configmap.yaml
kubectl delete secret campus-tls-cert
Remove-Item .\tls.key, .\tls.crt -ErrorAction SilentlyContinue
```

## Key Learnings

- ConfigMaps hold non-sensitive configuration; Secrets hold sensitive values.
- Base64 encoding does not encrypt a Secret. Use RBAC and encryption at rest for production security.
- An Ingress resource needs a running Ingress Controller to route traffic.
- TLS certificates are stored in Secrets of type `kubernetes.io/tls`.
- Ingress can route by host and path through one entry point.
- PowerShell uses different syntax from Bash for line continuation and Base64 decoding.
