 # Session 11 - Kubernetes Services

This assignment demonstrates the five Kubernetes service types from the session folders. Each service was applied to a Minikube cluster and tested to understand how it is reached.

## Prerequisites

Start Minikube and use the assignment directory as the working directory:

```bash
minikube start
cd session-11-kubernetes-services/Session-11-Assingments
```

The final service list was:

```text
NAME                        TYPE           CLUSTER-IP       EXTERNAL-IP        PORT(S)
external-database-service   ExternalName   <none>           nencyravaliya.me   <none>
kubernetes                  ClusterIP      10.96.0.1        <none>             443/TCP
web-service-clusterip       ClusterIP      10.103.181.111   <none>             8080/TCP
web-service-headless        ClusterIP      None             <none>             80/TCP
web-service-loadbalancer    LoadBalancer   10.98.112.60     <pending>          80:30708/TCP
web-service-nodeport        NodePort       10.107.134.211   <none>             80:30080/TCP
```

![All services](../Session-11-Assingments/01-clusterip/Screenshot%202026-09-17%20221844.png)

The `CLUSTER-IP` column shows the main difference between the services: normal ClusterIP, NodePort, and LoadBalancer services receive an IP; a headless service shows `None`; and an ExternalName service has no cluster IP.

## 1. ClusterIP

Apply the deployment, service, and test client:

```bash
kubectl apply -f 01-clusterip/app-deployment.yaml
kubectl apply -f 01-clusterip/service.yaml
kubectl apply -f 01-clusterip/client-pod.yaml
```

Check the service endpoints and request the application through the service name:

```bash
kubectl get endpoints web-service-clusterip
kubectl exec curl-client -- curl -s http://web-service-clusterip:8080
```

Example output:

```text
NAME                    ENDPOINTS                                      AGE
web-service-clusterip   10.244.0.82:80,10.244.0.83:80,10.244.0.84:80   56s
```

The service keeps a list of pod IPs selected by labels. The service name remains stable even when individual pods are replaced. Here, port `8080` is the service port and `80` is the target port where Nginx listens.

![ClusterIP endpoint and request test](../Session-11-Assingments/01-clusterip/Screenshot%202026-09-17%20221902.png)
![ClusterIP service output](../Session-11-Assingments/01-clusterip/Screenshot%202026-09-17%20221949.png)
![ClusterIP test result](../Session-11-Assingments/01-clusterip/Screenshot%202026-09-17%20221959.png)

The `Endpoints` deprecation warning means that newer Kubernetes versions prefer the `discovery.k8s.io/v1` `EndpointSlice` API. The endpoint information is still the same.

## 2. NodePort

Apply the NodePort resources:

```bash
kubectl apply -f 02-nodeport/app-deployment.yaml
kubectl apply -f 02-nodeport/service.yaml
```

Inspect the service and get a reachable Minikube URL:

```bash
kubectl get svc web-service-nodeport
minikube service web-service-nodeport --url
```

Example output:

```text
NAME                 TYPE       CLUSTER-IP       EXTERNAL-IP   PORT(S)
web-service-nodeport NodePort   10.107.134.211   <none>        80:30080/TCP

http://127.0.0.1:59679
```

Port `80` is exposed inside the cluster and port `30080` is exposed on the node. On Windows with Minikube's Docker driver, `minikube service --url` creates a local tunnel because the node itself runs inside a container. Keep that command running while using the URL.

![NodePort service](../Session-11-Assingments/02-nodeport/Screenshot%202026-09-17%20222308.png)
![NodePort URL](../Session-11-Assingments/02-nodeport/Screenshot%202026-09-17%20222324.png)
![NodePort request](../Session-11-Assingments/02-nodeport/Screenshot%202026-09-17%20222354.png)
![NodePort output](../Session-11-Assingments/02-nodeport/Screenshot%202026-09-17%20222411.png)

## 3. LoadBalancer

Apply the LoadBalancer resources and inspect the service:

```bash
kubectl apply -f 03-loadbalancer/app-deployment.yaml
kubectl apply -f 03-loadbalancer/service.yaml
kubectl get svc web-service-loadbalancer
```

Example output:

```text
NAME                     TYPE           CLUSTER-IP     EXTERNAL-IP   PORT(S)
web-service-loadbalancer LoadBalancer   10.98.112.60   <pending>     80:30708/TCP
```

`LoadBalancer` normally asks a cloud provider to create an external load balancer. On Minikube there is no cloud provider, so `EXTERNAL-IP` remains `<pending>`. Running `minikube tunnel` can provide Minikube's local LoadBalancer behavior. This service also receives a NodePort because LoadBalancer builds on NodePort, which builds on ClusterIP.

![LoadBalancer service](../Session-11-Assingments/03-loadbalancer/Screenshot%202026-09-17%20222935.png)
![LoadBalancer output](../Session-11-Assingments/03-loadbalancer/Screenshot%202026-09-17%20222944.png)

## 4. ExternalName

Apply the ExternalName service and DNS test client:

```bash
kubectl apply -f 04-externalname/service.yaml
kubectl apply -f 04-externalname/client-pod.yaml
kubectl get svc external-database-service
kubectl exec dns-test-client -- nslookup external-database-service
```

Example output:

```text
NAME                        TYPE           CLUSTER-IP   EXTERNAL-IP        PORT(S)
external-database-service   ExternalName   <none>       nencyravaliya.me   <none>

external-database-service.default.svc.cluster.local canonical name = nencyravaliya.me
```

An ExternalName service has no selector, pod, or cluster IP. CoreDNS returns a CNAME for an external hostname. The application can keep using `external-database-service` even if the real database hostname changes later.

![ExternalName service](../Session-11-Assingments/04-externalname/Screenshot%202026-09-17%20232225.png)
![ExternalName DNS result](../Session-11-Assingments/04-externalname/Screenshot%202026-09-17%20232246.png)

The DNS lookup may print `NXDOMAIN` lines while trying search-path suffixes first. The fully qualified name resolves to the configured CNAME, so those intermediate lines do not mean the ExternalName configuration failed.

## 5. Headless service

Apply the StatefulSet, headless service, and DNS test client:

```bash
kubectl apply -f 05-headless/statefulset.yaml
kubectl apply -f 05-headless/service.yaml
kubectl apply -f 05-headless/client-pod.yaml
kubectl exec headless-dns-client -- nslookup web-service-headless
kubectl get pods -l app=web-headless -o wide
```

Example output:

```text
NAME                   TYPE        CLUSTER-IP   EXTERNAL-IP   PORT(S)
web-service-headless   ClusterIP   None         <none>        80/TCP

Name:    web-service-headless.default.svc.cluster.local
Address: 10.244.0.95
Name:    web-service-headless.default.svc.cluster.local
Address: 10.244.0.94
Name:    web-service-headless.default.svc.cluster.local
Address: 10.244.0.92
```

The `clusterIP: None` setting makes the service headless. DNS returns all matching pod IPs instead of one virtual IP, allowing the client to choose a specific pod. The StatefulSet also gives the pods stable names such as `web-stateful-0.web-service-headless`.

![Headless service DNS](../Session-11-Assingments/05-headless/Screenshot%202026-09-17%20224238.png)
![Headless service pods](../Session-11-Assingments/05-headless/Screenshot%202026-09-17%20224247.png)

## What I learned

- ClusterIP provides an internal virtual IP.
- NodePort adds a port on each node and still includes ClusterIP behavior.
- LoadBalancer adds an external load balancer in supported cloud environments and also includes NodePort and ClusterIP behavior.
- ExternalName is a DNS alias and does not create a virtual IP or select pods.
- A headless service returns the IP addresses of all matching pods instead of load-balancing through one virtual IP.
- Services find pods using labels. If a selector does not match pod labels, the endpoint list is empty and requests fail.
- The full Kubernetes service DNS name is `<service>.<namespace>.svc.cluster.local`; the short service name works inside the same namespace because of the DNS search path.
