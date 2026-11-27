# realm-kubernetes

> **Experimental.** This realm is new and still changing: types, views and parameters may change without notice, and it has been run on few systems. Check its answers before relying on them.

A Kubernetes cluster as a graph you can query, read live from the cluster's own API when a question
reaches it. Nothing is copied into the graph: a pod lives for minutes.

```cypher
MATCH (n:KubeNamespace {name: 'shop'})-[:HAS_POD]->(p:KubePod)
WHERE p.crashLooping
RETURN p.name, p.version, p.restarts, p.lastStopReason, p.lastExitCode
```

```
KubeNamespace ─HAS_POD▶ KubePod ─HAS_CONTAINER▶ KubeContainer
                                 ─HAS_LOG_EVENT▶ KubeLogEvent
                                 ─HAS_PREVIOUS_LOG_EVENT▶ KubeLogEvent
              ─HAS_DEPLOYMENT▶ KubeDeployment
              ─HAS_STATEFUL_SET▶ KubeStatefulSet
              ─HAS_SERVICE▶ KubeService
              ─HAS_ENDPOINT_SLICE▶ KubeEndpointSlice
              ─HAS_INGRESS▶ KubeIngress
              ─HAS_EVENT▶ KubeEvent
```

Routing is read as the cluster resolves it, not guessed from names: a `KubeService` names its pods by
selector, the cluster turns that into `KubeEndpointSlice`s that name the pods and count the ready ones,
and a `KubeIngress` names the services it routes to. Workloads carry the
standard application labels (`instance`, `component`, `partOf`) so a namespace groups into
applications by what its author declared.

Read-only. It makes list calls and reads pod logs, and nothing else; it never changes the cluster and never reads
a Secret.

## Views

| view | question |
|---|---|
| `KubeRunning(namespace)` | what is running, by application and version: image, pods, ready, restarted, crash-looping |
| `KubeIsRunning(namespace, version)` | is this commit, release or image digest running anywhere, and on how many pods |
| `KubeCrashes(namespace)` | which pods restarted or are not ready, and why: stop reason, exit code, out of memory, memory limit |
| `KubeDeployments(namespace)` | wanted, ready and updated replicas; whether a rollout is stuck |
| `KubeWarnings(namespace)` | what the cluster says went wrong lately |
| `KubeLogFailures(namespace, app)` | the failures the pods logged, the same failure counted once |
| `KubeServices(namespace)` | each service, its ports and selector, and how many pods answer for it right now |
| `KubeStatefulSets(namespace)` | the stateful workloads (databases, queues, caches): wanted, ready, rolled out |
| `KubeIngresses(namespace)` | how the namespace is reached from outside: hosts, paths, backend services |
| `KubeComponents(namespace)` | the workloads grouped into applications by `app.kubernetes.io/instance` and `component`, with the services fronting each |

Two rows for one application in `KubeRunning` are two versions side by side: a rollout in progress,
or one that is stuck.

## Setup

Two settings, asked for on install (or set in the world's `data/secrets.env`):

- `KUBERNETES_API_SERVER`: the API server's URL.
- `KUBERNETES_TOKEN`: a service account's token.
- `KUBERNETES_CA_CERT`: the cluster's certificate authority, when its API is signed by its own
  (most are). Paste `certificate-authority-data` from a kubeconfig as it is, or a PEM certificate.
  It is trusted for this realm's calls to the cluster and for nothing else. Needs an appliance that
  reads `ca-cert` on an API (embabel/me, November 2026).

Give the account the built-in `view` role, which cannot change anything and cannot read Secrets:

```sh
kubectl create serviceaccount embabel-reader -n shop
kubectl create clusterrolebinding embabel-reader-view --clusterrole=view --serviceaccount=shop:embabel-reader
kubectl create token embabel-reader -n shop --duration=720h
```

To scope it to one namespace instead, bind `view` with a RoleBinding in that namespace and add a
ClusterRole that may only `get` and `list` namespaces (the realm checks its token by listing them):

```sh
kubectl create rolebinding embabel-reader-view -n shop --clusterrole=view --serviceaccount=shop:embabel-reader
kubectl create clusterrole embabel-namespace-lister --verb=get,list --resource=namespaces
kubectl create clusterrolebinding embabel-reader-namespaces --clusterrole=embabel-namespace-lister --serviceaccount=shop:embabel-reader
```

An appliance running in Docker beside a kind cluster reaches the API server by joining the `kind`
network (`docker network connect kind <worlds container>`). Give it the control-plane container's
IPv4 address, `https://172.18.0.2:6443` or whatever `docker inspect <control-plane> -f
'{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}'` prints, which is in the server certificate's
SANs: the container's NAME resolves to its IPv6 address on the kind network, which the appliance's
JVM then tries first and cannot reach, and `host.docker.internal` is not in the certificate at all.
The join does not survive the container being recreated; repeat it after `embabel up`.

## Tracing a pod to its commit

A pod carries `imageDigest` (the exact image running) and `version` (the label
`app.kubernetes.io/version`). Label a deployment's pods with the commit they were built from and
`KubeIsRunning` answers "is this commit running anywhere".

## Limits

- **A pod's log is read as far back as its last 5,000 lines**, for its first container: the one
  running now (`HAS_LOG_EVENT`) and the one before its last restart (`HAS_PREVIOUS_LOG_EVENT`), as
  `KubeLogEvent`s, one per logged event with its whole stack trace. Older lines, and the logs of a
  pod that is gone, are the log store's to answer (realm-elastic-logs).
- A pod's first container is described on the pod; the others are `KubeContainer`s.
- The cluster keeps about an hour of events.
- One cluster per world.

## Verified

Against a k3s cluster running two versions of an application, one crash-looping: every figure in
`KubeRunning`, `KubeCrashes`, `KubeIsRunning` and `KubeDeployments` equalled what `kubectl` reported
(pods per version, ready, restart count, waiting reason, wanted/ready/updated replicas), and the
read-only token was refused when asked for Secrets.

0.2.0, against a kind cluster running the AWS retail sample (10 workloads, 10 services, 3 stateful
sets, no ingress): `KubeServices`, `KubeStatefulSets`, `KubeComponents` and `KubeIngresses` equalled
`kubectl` on every service, type, endpoint and ready-endpoint count, every stateful set, and every
workload's grouping labels; the namespace-scoped reader token was refused on another namespace's
pods, on Secrets, and on the service proxy (realm-retail-store `tests/verify.py`, 2026-11-27).
