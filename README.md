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
              ─HAS_EVENT▶ KubeEvent
```

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
