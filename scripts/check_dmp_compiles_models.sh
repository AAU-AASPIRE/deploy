#!/usr/bin/env bash
# Does the DMP (aas-camel-dmp) compile every resource aas-model authors? With both beside this repository: writes
# aas-model's whole catalog, as registration publishes it, to a temporary directory
# (aas-camel-dmp/fixtures/contracts.py --catalog) and runs the DMP's RawModelContractFixtureTest on that directory.
# Nothing is written into either repository: the DMP's checked-in fixtures are its own regression inputs and do not
# follow aas-model.
#
# Needs uv, Maven and JDK 25. Usage, from anywhere:
#
#     scripts/check_dmp_compiles_models.sh [extra Maven options, e.g. -o]
set -euo pipefail

repos="$(cd "$(dirname "$0")/../.." && pwd)"
model="$repos/aas-model"
dmp="$repos/aas-camel-dmp"
cases="$(mktemp -d)"
trap 'rm -rf "$cases"' EXIT

echo "aas-model $(git -C "$model" rev-parse --short HEAD), aas-camel-dmp $(git -C "$dmp" rev-parse --short HEAD)"

(cd "$dmp/fixtures" &&
  MQTT_SCHEMAS_DIR="$model/MQTTSchemas" \
  uv run --quiet --no-project --with-editable "$model" python -m contracts --catalog --out "$cases")

(cd "$dmp" &&
  mvn -q "$@" -pl dmp.component -am test -Dtest=RawModelContractFixtureTest -Dsurefire.failIfNoSpecifiedTests=false \
    -Ddmp.contracts.dir="$cases")
echo "the DMP compiles every resource of aas-model's catalog"
