"""realm-kubernetes battery. L1 every view by name; L2 figures against the cluster's API;
L3 the pushed filters narrow what is asked (externalCalls on the result envelope)."""
import base64, collections, json, os, ssl, sys, urllib.request

APPLIANCE = os.environ.get("APPLIANCE", "http://127.0.0.1:11043").rstrip("/")
AUTH = os.environ.get("AUTH") or os.environ.get("EMBABEL_AUTH")
API = os.environ.get("KUBERNETES_API_SERVER", "").rstrip("/")
TOKEN = os.environ.get("KUBERNETES_TOKEN")
NS = os.environ.get("NAMESPACE", "default")
if not (AUTH and API and TOKEN):
    sys.exit("set AUTH, KUBERNETES_API_SERVER and KUBERNETES_TOKEN")
CTX = ssl.create_default_context(cafile=os.environ.get("KUBERNETES_CA_FILE") or None)
HDR = {"Authorization": "Basic " + base64.b64encode(AUTH.encode()).decode(), "Content-Type": "application/json"}
failures = 0

def check(name, expected, actual):
    global failures
    if expected == actual:
        print(f"  ok   {name} = {str(expected)[:100]}")
    else:
        failures += 1
        print(f"  FAIL {name}: expected {str(expected)[:300]}, got {str(actual)[:300]}")

def kube(path):
    req = urllib.request.Request(API + path, headers={"Authorization": f"Bearer {TOKEN}"})
    with urllib.request.urlopen(req, context=CTX, timeout=60) as r:
        return json.load(r)["items"]

def post(path, body):
    req = urllib.request.Request(APPLIANCE + path, json.dumps(body).encode(), HDR)
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)

def view(name, args):
    body = post(f"/api/v1/views/{name}/invoke", {"args": args})
    if "data" not in body:
        raise SystemExit(f"view {name} answered without data: {json.dumps(body)[:500]}")
    return body["data"]

def app_of(o):
    labels = o["metadata"].get("labels") or {}
    return labels.get("app.kubernetes.io/name") or labels.get("app") or ""

print(f"== L1+L2: every view by name, reconciled against the cluster (namespace {NS}) ==")
pods = kube(f"/api/v1/namespaces/{NS}/pods")
truth = collections.Counter(app_of(p) for p in pods)
rows = view("KubeRunning", {"namespace": NS})
got = collections.Counter()
for r in rows:
    got[r["app"]] += r["pods"]
check("KubeRunning: pods per app", dict(truth), dict(got))

restarted = sorted(p["metadata"]["name"] for p in pods
                   if any(c.get("restartCount", 0) > 0 for c in p["status"].get("containerStatuses", [])[:1])
                   or not all(c.get("ready") for c in p["status"].get("containerStatuses", [{}])[:1]))
check("KubeCrashes: pods restarted or not ready", restarted, sorted(r["pod"] for r in view("KubeCrashes", {"namespace": NS})))

deps = kube(f"/apis/apps/v1/namespaces/{NS}/deployments")
check("KubeDeployments: deployments", sorted(d["metadata"]["name"] for d in deps),
      sorted(r["deployment"] for r in view("KubeDeployments", {"namespace": NS})))

warnings = kube(f"/api/v1/namespaces/{NS}/events?fieldSelector=type%3DWarning")
rows = view("KubeWarnings", {"namespace": NS, "limit": 100000})
check("KubeWarnings: warning events", len(warnings), len(rows))

version = next((app_of(p) and (p["metadata"].get("labels") or {}).get("app.kubernetes.io/version") for p in pods
                if (p["metadata"].get("labels") or {}).get("app.kubernetes.io/version")), None)
if version:
    n = sum(1 for p in pods if (p["metadata"].get("labels") or {}).get("app.kubernetes.io/version", "").startswith(version))
    rows = view("KubeIsRunning", {"namespace": NS, "version": version})
    check(f"KubeIsRunning: pods at version {version}", True, sum(r["pods"] for r in rows) >= n)
else:
    print("  SKIP KubeIsRunning: no pod in the namespace carries app.kubernetes.io/version")

rows = view("KubeLogFailures", {"namespace": NS})
check("KubeLogFailures answers by name", True, isinstance(rows, list))

print("== L3: pushed filters ==")
def calls(cypher):
    body = post("/api/v1/admin/kg/execute", {"cypher": cypher})
    return body, body.get("apiCalls")
body, n = calls(f"MATCH (n:KubeNamespace {{name: '{NS}'}})-[:HAS_EVENT]->(e:KubeEvent {{type: 'Warning'}}) RETURN count(e) AS n")
check("warnings read through the pushed type: count", len(warnings), (body.get("rows") or [{}])[0].get("n"))
check("warnings read through the pushed type: at most one call (0 when cached)", True, n is not None and n <= 1)
running = sum(1 for p in pods if p["status"].get("phase") == "Running")
body, n = calls(f"MATCH (n:KubeNamespace {{name: '{NS}'}})-[:HAS_POD]->(p:KubePod {{phase: 'Running'}}) RETURN count(p) AS n")
check("running pods through the pushed phase: count", running, (body.get("rows") or [{}])[0].get("n"))
check("running pods through the pushed phase: at most one call (0 when cached)", True, n is not None and n <= 1)

if failures:
    print(f"DRIFT FOUND: {failures} check(s) failed")
    sys.exit(1)
print("ALL CHECKS PASS")
