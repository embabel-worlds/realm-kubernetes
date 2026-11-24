#!/bin/sh
# Ground truth for realm-kubernetes: every view by name, and its figures reconciled exactly
# against the cluster's own API, read directly with the same read-only token.
#
#   APPLIANCE=http://127.0.0.1:11043 AUTH=user:pass \
#   KUBERNETES_API_SERVER=https://10.0.0.1:6443 KUBERNETES_TOKEN=... [KUBERNETES_CA_FILE=ca.pem] \
#   NAMESPACE=shop sh tests/verify.sh
#
# A cluster changes under the battery: pods restart and events age out. Each figure is read from
# the cluster immediately before the view that reports it, and compared to the row.
# The last line on success is exactly `ALL CHECKS PASS`; any drift exits nonzero.
set -e
cd "$(dirname "$0")/.."
exec python3 tests/verify.py "$@"
