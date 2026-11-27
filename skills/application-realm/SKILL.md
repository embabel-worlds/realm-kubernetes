---
name: application-realm
description: "Build an APPLICATION realm over an application that runs in one Kubernetes namespace — the business types read through its own HTTP APIs, the runtime model (which workload serves which capability) as views, reads admitted and writes held back — using what this kubernetes realm already sees. Use when someone points the world at a namespace and asks what the application does, wants to query it in business terms, or says \"a realm for this app\". Works over the MCP door alone: every step is a tool call."
---

# An application realm from a Kubernetes namespace

The kubernetes realm finds the running system. Its contracts explain what it can do. An admitted
application realm turns that into capabilities a question, an app or an agent can use. The rule
throughout: **discovery is not authorization.** Finding an endpoint never makes it callable; a
reviewed edit to `apis/apis.yml` does.

Three judgements are the owner's and nothing below makes them for you: what each workload IS for
the business, which operations WRITE whatever their HTTP method says, and which reads to ADMIT.
Everything else is mechanical. Write the judgements down where the realm will cite them.

## 0. What the operator hands you

- The namespace, and the kubernetes realm installed with a reader token for it. Prove it:
  `view_run KubeRunning {namespace}` answers rows.
- The services' API contracts (OpenAPI 3), one per `service`-role component: from the running
  service (`/v3/api-docs`, `/api-json`, `/openapi.json`) or from the source at the DEPLOYED tag
  (the image tag; a mutable tag proves nothing, say so). You cannot fetch these yourself over the
  door; ask for them, and ask which were read live and which from source.
- Later, a second token: a ServiceAccount whose only right is `get` on `services/proxy` for the
  services you admit (names AND `name:port`). You declare the key; the operator sets it.

## 1. Look before you model

| Ask | View | Write down |
|---|---|---|
| What is running? | `KubeRunning` | images and tags; is it one release? |
| How does it group? | `KubeComponents` | each `instance` (business component) and its `component` roles (service, mysql, redis…) |
| What fronts what? | `KubeServices` | service → ready endpoints; which are reachable from outside |
| How is it reached? | `KubeIngresses` | hosts and paths, or none (port-forward) |
| Is it healthy now? | `KubeDeployments`, `KubeStatefulSets`, `KubeWarnings` | restarts, OOM kills, probes failing |

Grouping comes from `app.kubernetes.io/instance` and `component`. Unlabelled workloads group under
an empty instance: ask the owner to name them, never infer from names.

## 2. Read the contracts, and what they are not

For every operation: service, operationId, method, path, **effect** (read or write: the semantics,
not the method; a GET that merges carts writes), idempotent or not, reversible or not, and
**source**: declared and verified live, declared only, deployed only (in the live document, in no
contract), declared and failing. Compare live documents with source contracts and keep the
differences: undocumented operations are the most important rows. A contract for a service no
workload runs is a source-only candidate: keep it as `reference/`, bind nothing to it.

Admit the smallest set of READS that answers the questions you were asked. Nothing that writes.
Nothing deployed-only. Nothing that failed when probed.

## 3. Write the realm

`realm_authoring_brief` first; then `realm_write` these files, `realm_validate` after each.

- `realm.yml`: `requires: { kubernetes: "[0.2.0,1.0.0)" }`; a `realmLabel` that is not a type name.
- `apis/<service>.yml`: each contract vendored UNCHANGED except `servers` rewritten to the proxy,
  `{server}/api/v1/namespaces/{namespace}/services/<svc>:80/proxy`, with `server` and `namespace`
  as variables, and operationIds prefixed with the realm's name (they resolve globally). Say so in
  the document's `info.description`. Every operation stays declared, writes included.
- `apis/apis.yml`: one entry per contract, `auth: bearer`, `token-env: <REALM>_API_TOKEN`,
  `server-variables: { server: ${KUBERNETES_API_SERVER}, namespace: ${<REALM>_NAMESPACE} }`,
  `ca-cert: ${KUBERNETES_CA_CERT}`, and `operation-ids` holding ONLY the admitted reads. The
  held-back ones go in a comment with why.
- `keys.yml`: the namespace (`secret: false`) and the token; `validate` with the cheapest admitted read.
- `types/`: one virtual type per business noun. A single-scope door for keyless reads (`scope`,
  identity, `default: this`); a pinned door for keyed reads (`{customerId}`); a lookup door with
  `materializedKeyField` for by-id reads. Money states its unit and currency. Lists that would
  converge wrongly as child nodes (an order's lines keyed by product) stay lists on the parent.
- `producers/`: one per admitted read. A PATH parameter takes `keyArgs: [name]`, never `keyArg`
  (list mode; the path would read `/carts/[bob]`). An empty that is an answer (a 404 for "no
  checkout") is `emptyErrorPatterns`. `pushdown: []` when the source filters nothing. Caches by
  volatility: reference data minutes, live data seconds.
- `views/`: the runtime model as LITERAL tables joined to the kubernetes realm's labels, which is
  the hand-reviewed application model: components → role and what it does; capabilities → the
  `instance/component` pairs they depend on, status judged from pod readiness, the failing one
  named; operations → the classification from step 2 with live endpoint counts; the pods on one
  business path with restarts and warnings. Then the business reads. Every description starts with
  the questions it answers (SELECT THIS for …); runtime views take `namespace` with a default.
- `skills/<realm>/SKILL.md`: moment of work → view → arguments. Say that Kubernetes green is not
  business green: readiness views judge pods, business views are the live probe.

## 4. Install, key, test like an adversary

`realm_install`; the operator sets the key; `realm_refresh` (an API entry resolves `${…}` at load).
Then every view with its defaults and each parameter varied, through `view_run`, and reconcile each
figure with what the operator reads from `kubectl` and the services directly. A view that has never
returned rows in front of you does not exist. Force the empties: a customer with no checkout, a
namespace with no ingress. Keep the questions a person would ask as `tests/questions.yml`.

## What this does not do

It does not derive the realm from evidence by itself: you make the three judgements. It does not
read metrics or traces. It covers one cluster per world.
