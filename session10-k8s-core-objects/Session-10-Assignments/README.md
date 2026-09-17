# Session 10 - Kubernetes Core Objects and Deployment Strategies

This assignment demonstrates Kubernetes pod lifecycle states and four deployment strategies: Rolling Update, Blue-Green, Canary, and Recreate. The examples use Minikube and Nginx-based workloads.

## Prerequisites

Start a local Kubernetes cluster and use the Session 10 directory as the working directory:

```bash
minikube start
cd session10-k8s-core-objects
```

Check that the cluster is available:

```bash
kubectl get nodes
```

## 1. Rolling Update

Rolling Update gradually replaces old pods with new pods while the service remains available. The example uses four replicas, `maxSurge: 1`, and `maxUnavailable: 0`.

### Deploy version 1

```bash
kubectl apply -f 01-rolling-updates/deployment-v1.yaml
kubectl apply -f 01-rolling-updates/service.yaml
kubectl rollout status deployment/app-rolling
kubectl get pods -l app=app-rolling --show-labels
```

Test the v1 application:

```bash
curl http://$(minikube ip):30010
# Or get a local URL:
minikube service app-rolling-service --url
```

The response shows `VERSION: v1`.

### Update to version 2

Run the following in one terminal:

```bash
kubectl get pods -l app=app-rolling -w
```

In a second terminal, apply the new deployment:

```bash
kubectl apply -f 01-rolling-updates/deployment-v2.yaml
```

The pod watch shows v2 pods starting and becoming Ready before old v1 pods terminate. The service continues responding during the update:

```bash
while true; do curl -s http://$(minikube ip):30010 | grep VERSION; sleep 1; done
```

Verify the rollout and inspect its history:

```bash
kubectl rollout status deployment/app-rolling
kubectl get pods -l app=app-rolling --show-labels
kubectl rollout history deployment/app-rolling
```

All pods should show `version=v2`. Roll back to v1 with:

```bash
kubectl rollout undo deployment/app-rolling
kubectl get pods -l app=app-rolling --show-labels
```

Rolling Update is suitable for stateless applications where old and new versions can run together without breaking compatibility.

![Rolling Update assignment output](01-rolling-updates/Screenshot%202026-09-17%20230608.png)

## 2. Blue-Green Deployment

Blue-Green keeps two complete environments running. Blue is v1 and initially receives traffic; Green is v2 and can be tested before the service selector is switched.

### Deploy both environments

```bash
kubectl apply -f 02-blue-green/deployment-blue.yaml
kubectl apply -f 02-blue-green/deployment-green.yaml
kubectl get pods -l app=myapp --show-labels
```

Six pods should be running: three Blue pods and three Green pods.

### Send traffic to Blue

```bash
kubectl apply -f 02-blue-green/service-blue.yaml
kubectl describe svc myapp-service | Select-String Selector
kubectl get endpoints myapp-service
curl http://$(minikube ip):30020
# Or:
minikube service myapp-service --url
```

The service selector should be `app=myapp,slot=blue`, and the response should identify `BLUE ENVIRONMENT` and version v1.

### Switch traffic to Green

```bash
kubectl apply -f 02-blue-green/service-green.yaml
kubectl describe svc myapp-service | Select-String Selector
kubectl get endpoints myapp-service
curl http://$(minikube ip):30020
```

The selector changes to `app=myapp,slot=green`, and all service traffic moves to Green immediately. Roll back by applying the Blue service again:

```bash
kubectl apply -f 02-blue-green/service-blue.yaml
curl http://$(minikube ip):30020
```

After Green is confirmed stable, the old Blue deployment can be removed:

```bash
kubectl delete deployment app-blue
```

Blue-Green provides fast cutover and rollback, but requires resources for both environments at the same time.

![Blue-Green deployment assignment output](02-blue-green/Screenshot%202026-09-17%20230950.png)

## 3. Canary Deployment

Canary releases a new version to a small number of pods while most traffic continues going to the stable version. Kubernetes approximates the traffic split through the number of pods selected by one service.

### Deploy stable version

```bash
kubectl apply -f 03-canary/deployment-stable.yaml
kubectl rollout status deployment/app-stable
kubectl apply -f 03-canary/service.yaml
```

Test the service before deploying the canary:

```bash
for i in $(seq 1 10); do curl -s http://$(minikube ip):30030 | grep -o "STABLE v1\|CANARY v2"; done
```

With only the stable deployment running, all responses should be `STABLE v1`.

### Deploy the canary

```bash
kubectl apply -f 03-canary/deployment-canary.yaml
kubectl get pods -l app=myapp-canary --show-labels
```

The initial ratio is nine stable pods to one canary pod, approximately 90% stable and 10% canary:

```bash
for i in $(seq 1 20); do curl -s http://$(minikube ip):30030 | grep -o "STABLE v1\|CANARY v2"; done
```

The exact sample can vary, but approximately one in ten responses should be from `CANARY v2`.

### Increase, promote, or roll back

Increase canary traffic to approximately 30%:

```bash
kubectl scale deployment app-canary --replicas=3
kubectl scale deployment app-stable --replicas=7
kubectl get endpoints myapp-canary-service
```

Promote the canary to 100%:

```bash
kubectl scale deployment app-canary --replicas=9
kubectl scale deployment app-stable --replicas=0
kubectl delete deployment app-stable
```

If the canary is unhealthy, roll it back by removing its replicas and restoring the stable deployment:

```bash
kubectl scale deployment app-canary --replicas=0
kubectl scale deployment app-stable --replicas=9
```

The service selects both versions using the shared `app: myapp-canary` label. The `track` label identifies stable or canary pods but does not route traffic by itself.

![Canary traffic split](03-canary/Screenshot%202026-09-17%20231401.png)
![Canary deployment assignment output](03-canary/Screenshot%202026-09-17%20231427.png)

## 4. Recreate Deployment

The Recreate strategy stops all old pods before creating the new pods. This creates a deliberate downtime window but is useful when old and new versions cannot run together, such as incompatible schema migrations or single-writer storage.

### Deploy version 1

```bash
kubectl apply -f 04-recreate/deployment-v1.yaml
kubectl apply -f 04-recreate/service.yaml
kubectl get pods -l app=app-recreate
curl http://localhost:30040
```

The response identifies `STRATEGY: RECREATE` and `VERSION: v1`.

### Trigger the update

In one terminal, watch the pods:

```bash
kubectl get pods -l app=app-recreate -w
```

In another terminal, apply v2:

```bash
kubectl apply -f 04-recreate/deployment-v2.yaml
```

The v1 pods terminate first. For a short period there are zero running pods; then the v2 pods are created and become Ready. A request loop makes the outage visible:

```bash
while true; do curl -s --connect-timeout 1 http://localhost:30040 | grep -o 'VERSION: [^<]*' || echo '[OUTAGE] Connection failed'; sleep 0.5; done
```

Verify v2 and roll back if required:

```bash
curl http://localhost:30040
kubectl rollout status deployment/app-recreate
kubectl rollout undo deployment/app-recreate
```

Recreate should be chosen deliberately because it causes downtime during every replacement.

![Recreate deployment assignment output](04-recreate/Screenshot%202026-09-17%20231856.png)

## 5. Pod Lifecycle

The `pod-lifecycle` folder contains independent examples of common pod states and behaviors. Start a watch in one terminal:

```bash
kubectl get pods -w
```

Apply and inspect each example from another terminal:

```bash
kubectl apply -f pod-lifecycle/01-running.yaml
kubectl get pod lifecycle-running
kubectl describe pod lifecycle-running
kubectl logs lifecycle-running

kubectl apply -f pod-lifecycle/02-pending.yaml
kubectl get pod lifecycle-pending
kubectl describe pod lifecycle-pending

kubectl apply -f pod-lifecycle/03-succeeded.yaml
kubectl get pod lifecycle-succeeded
kubectl logs lifecycle-succeeded

kubectl apply -f pod-lifecycle/04-failed.yaml
kubectl get pod lifecycle-failed
kubectl logs lifecycle-failed

kubectl apply -f pod-lifecycle/05-crashloopbackoff.yaml
kubectl get pod lifecycle-crashloop -w
kubectl describe pod lifecycle-crashloop
kubectl logs lifecycle-crashloop --previous

kubectl apply -f pod-lifecycle/06-imagepullbackoff.yaml
kubectl get pod lifecycle-image-error
kubectl describe pod lifecycle-image-error

kubectl apply -f pod-lifecycle/07-readiness.yaml
kubectl get pod lifecycle-readiness -w
kubectl describe pod lifecycle-readiness

kubectl apply -f pod-lifecycle/08-liveness.yaml
kubectl get pod lifecycle-liveness -w

kubectl apply -f pod-lifecycle/09-startup.yaml
kubectl get pod lifecycle-startup -w

kubectl apply -f pod-lifecycle/10-init-container.yaml
kubectl get pod lifecycle-init -w

kubectl apply -f pod-lifecycle/11-multi-container.yaml
kubectl get pod lifecycle-multi-container
kubectl logs lifecycle-multi-container -c app

kubectl apply -f pod-lifecycle/12-termination.yaml
kubectl get pod lifecycle-termination -w
```

Useful inspection commands for any pod are:

```bash
kubectl get pod <pod-name> -o yaml
kubectl get pod <pod-name> -o jsonpath='{.status.containerStatuses[0].state}'
kubectl describe pod <pod-name>
kubectl delete pod <pod-name>
```

`Pending`, `Running`, `Succeeded`, `Failed`, and `Unknown` are official Pod phases. Values such as `CrashLoopBackOff`, `ImagePullBackOff`, `ContainerCreating`, and `Terminating` describe container or kubectl conditions rather than official Pod phases. A pod can be `Running` but not `Ready` when its readiness probe has not succeeded.

## Summary

- Rolling Update replaces pods gradually and is designed for zero-downtime updates.
- Blue-Green runs two complete environments and switches traffic by changing a service selector.
- Canary exposes a small percentage of traffic to the new version using pod ratios.
- Recreate stops the old version completely before starting the new version, creating downtime.
- Pod lifecycle states explain how Kubernetes schedules, starts, probes, restarts, and terminates containers.

## Cleanup

Delete resources created by the deployment-strategy labs when finished:

```bash
kubectl delete -f 01-rolling-updates/service.yaml
kubectl delete deployment app-rolling
kubectl delete -f 02-blue-green/service-blue.yaml
kubectl delete deployment app-blue app-green
kubectl delete -f 03-canary/service.yaml
kubectl delete deployment app-stable app-canary
kubectl delete -f 04-recreate/service.yaml
kubectl delete deployment app-recreate
```
