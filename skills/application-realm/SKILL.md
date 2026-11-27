---
name: application-realm
description: "Build an APPLICATION realm over an application that runs in one Kubernetes namespace — the business types read through its own HTTP APIs, the runtime model (which workload serves which capability) as views, performance from Prometheus, reads admitted and writes held back — composed from every realm the owner's answers justify (source, CI, logs, metrics, databases), using what this kubernetes realm already sees. Use when someone points the world at a namespace and asks what the application does, wants to query it in business terms, or says \"a realm for this app\". Works over the MCP door alone: every step is a tool call."
---

# An application realm from a Kubernetes namespace

The kubernetes realm finds the running system. Its contracts explain what it can do. An admitted
application realm turns that into capabilities a question, an app or an agent can use. The rule
throughout: **discovery is not authorization.** Finding an endpoint never makes it callable; a
reviewed edit to `apis/apis.yml` does.

Three judgements are the owner's and nothing below makes them for you: what each workload IS for
the business, which operations WRITE whatever their HTTP method says, and which reads to ADMIT.
Everything else is mechanical. Write the judgements down where the realm will cite them.

## 0. Interview first: what surrounds this application

Before modelling anything, ask the owner. Every answer is a realm the application realm can
require, a question it can then answer, and a grant the owner must give. Ask them all; bring in as
many as the answers justify. Write the answers down in the realm's README, because they are the
composition's reasons.

| Ask | If yes, bring in | What it answers for this application | The grant |
|---|---|---|---|
| Which repository or repositories hold the source, and which directory each service lives in? | `github` (needs `dev-vocabulary`), `git`, `polyglot-code` (needs `code-model`) | which commit built the running image; what changed between two releases; where the code behind a failing endpoint is; who changed it | a read-only GitHub token (prefer a GitHub App installation token, scoped to those repositories) |
| How are images tagged, and does a tag name a commit? | nothing new; it decides how `KubePod.version` / `imageTag` join to `git` | image → commit with confidence, or "a mutable tag proves nothing" | none |
| Where does CI run? | `github-actions` | did this image come from a green build; is a red build mine | the same GitHub token |
| Which services are JVM / Spring Boot? | `spring`, `jvm-logs`, `java-project` | Boot line, endpoints, settings, memory limits; stack traces from the pod logs the kubernetes realm already reads | none beyond the realms |
| Where do logs go beyond the pods? | `elastic-logs` or `logs` | failures older than the pod's last 5,000 lines | a read-only index user |
| Is there a Prometheus, a managed metrics endpoint, or metrics on the services? | `prometheus` (deploy one if there is none: a namespaced Prometheus with static targets costs nothing the owner minds) | requests, errors, latency per service; traffic over a window | a token for the door in front of it, scoped to that one service |
| Which databases sit behind the services, and can a read-only user be issued? | a read-only SQL datasource in the world (a datasource, not a realm), per database, as EVIDENCE | which table holds orders; counts to reconcile the API against | a read-only database user, reachable port; never the application's Secrets |
| Is there a Sonar or another quality gate? | `sonar`, `code-understanding` | coverage on the file behind a failure | its token |
| Which failure-to-change question matters most? | `which-change` | a logged failure fingerprint → file → commit → pull request | nothing new |
| Which business questions matter most, and who owns the answers? | nothing new; it chooses what to admit and which capabilities to name | the three judgements below, made with the owner | none |

Two rules the answers must respect. **A business user is not made to install the developer
overlay**: `kubernetes` and `prometheus` are the application realm's hard `requires:`; the source,
CI and code realms go in a second, developer-facing composition realm that requires the first
(realm-project-petclinic is the exemplar), so the store's realm installs without a GitHub token.
**Every token is read-only and scoped**: a namespace, a repository, one service behind a proxy.
Where the appliance runs in the owner's cloud, say so in the README: keys belong in the platform's
secret store (Secrets Manager behind an IAM role), read into the wallet, never written into a realm.

## The composition, once the interview is done

- `requires:` names each realm you bring in, by Maven range, lower bound the version installed now.
- **Anchors**, pinned once as node views, so every query names the application's identities by
  one label: its repository (`MATCH (r:GitHubRepository {full_name: '…'}) RETURN r`), its code
  project, its CI workflows, its namespace. Petclinic's `ClinicRepository`, `ClinicCode`,
  `ClinicHistory`, `ClinicBuild` are the shape.
- **Cross-realm views only this application can ask**: image → commit (`KubePod.imageTag` to the
  release tag to `git`), a failing capability → the pods → their log failures → `WhichChange`,
  a release → the contract diff. Write only the ones the interview justified.
- The skill's table gains a row per realm brought in: moment → view → this application's arguments.

## 1. What the operator hands you

- The namespace, and the kubernetes realm installed with a reader token for it. Prove it:
  `view_run KubeRunning {namespace}` answers rows.
- The services' API contracts (OpenAPI 3), one per `service`-role component: from the running
  service (`/v3/api-docs`, `/api-json`, `/openapi.json`) or from the source at the DEPLOYED tag
  (the image tag; a mutable tag proves nothing, say so). You cannot fetch these yourself over the
  door; ask for them, and ask which were read live and which from source.
- Later, a second token: a ServiceAccount whose only right is `get` on `services/proxy` for the
  services you admit (names AND `name:port`). You declare the key; the operator sets it.

## 2. Look before you model

| Ask | View | Write down |
|---|---|---|
| What is running? | `KubeRunning` | images and tags; is it one release? |
| How does it group? | `KubeComponents` | each `instance` (business component) and its `component` roles (service, mysql, redis…) |
| What fronts what? | `KubeServices` | service → ready endpoints; which are reachable from outside |
| How is it reached? | `KubeIngresses` | hosts and paths, or none (port-forward) |
| Is it healthy now? | `KubeDeployments`, `KubeStatefulSets`, `KubeWarnings` | restarts, OOM kills, probes failing |

Grouping comes from `app.kubernetes.io/instance` and `component`. Unlabelled workloads group under
an empty instance: ask the owner to name them, never infer from names.

## 3. Read the contracts, and what they are not

For every operation (step 3): service, operationId, method, path, **effect** (read or write: the semantics,
not the method; a GET that merges carts writes), idempotent or not, reversible or not, and
**source**: declared and verified live, declared only, deployed only (in the live document, in no
contract), declared and failing. Compare live documents with source contracts and keep the
differences: undocumented operations are the most important rows. A contract for a service no
workload runs is a source-only candidate: keep it as `reference/`, bind nothing to it.

Admit the smallest set of READS that answers the questions you were asked. Nothing that writes.
Nothing deployed-only. Nothing that failed when probed.

## 4. Write the realm

`realm_authoring_brief` first; then `realm_write` these files, `realm_validate` after each.

- `realm.yml`: `requires:` on `kubernetes` and on every realm the interview brought in (ranges by
  Maven notation, lower bound the installed version); a `realmLabel` that is not a type name.
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

## 5. Install, key, test like an adversary

`realm_install`; the operator sets the key; `realm_refresh` (an API entry resolves `${…}` at load).
Then every view with its defaults and each parameter varied, through `view_run`, and reconcile each
figure with what the operator reads from `kubectl` and the services directly. A view that has never
returned rows in front of you does not exist. Force the empties: a customer with no checkout, a
namespace with no ingress. Keep the questions a person would ask as `tests/questions.yml`.

## What this does not do

It does not derive the realm from evidence by itself: you make the three judgements, with the
owner. It does not read traces. It covers one cluster per world.
