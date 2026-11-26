"""The lab stack as one system: what one repository changes must not break how it works with the others.

Run against a stack that is up (`python aas.py up --stations`), with the repositories beside this one:

    python -m pytest tests/test_stack.py --stack

It publishes aas-model's AASs of the stations, the planar table, its shuttles and the filling line (from aas-model
beside this repository, not the one installed), and checks, in order:

1. the state store answers and holds the lab vocabulary (state-store, ontologies);
2. the DMP installs every mapping of every published AAS (aas-model, aas-camel-dmp);
3. a skill call goes from BaSyx through the DMP to a simulated station and back, and the station's state reaches the
   state store: Occupy puts the unit in OccupiedBy, Release clears it (station-simulator, the DMP's state sinks);
4. the web UI answers and proxies the DMP's status for its AIMC plugin (basyx-aas-web-ui).

Without --stack every test is skipped; without the stations (`--stations`), 3 is.
"""
from __future__ import annotations

import base64
import json
import os
from pathlib import Path
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

import pytest

AAS = os.environ.get("AAS_URL", "http://localhost:8081")
DMP = os.environ.get("DMP_URL", "http://localhost:8085")
STORE = os.environ.get("STATE_STORE_URL", "http://localhost:7878")
WEB_UI = os.environ.get("WEB_UI_URL", f"http://localhost:{os.environ.get('WEB_UI_PORT', '3000')}")
BASE = "https://smartproductionlab.aau.dk"
LAB = f"{BASE}/semantics/"
STATION = f"{BASE}/aas/LoadingStationAAS"
# The line's resources aas-model describes and the simulated stations run.
PUBLISHED = ("stopperingStation", "cappingStation", "dispensingStation", "loadingStation", "unloadingStation",
             "planarTable", "planarShuttle1", "planarShuttle2", "planarShuttle3", "aauFillingLine")


@pytest.fixture(scope="session", autouse=True)
def stack(request):
    if not request.config.getoption("--stack"):
        pytest.skip("the lab stack is not up (run python aas.py up --stations, then pytest --stack)")


def b64(identifier: str) -> str:
    return base64.urlsafe_b64encode(identifier.encode()).decode().rstrip("=")


def http(method: str, url: str, body=None, accept: str = "application/json", timeout: float = 30):
    data = None if body is None else (body if isinstance(body, bytes) else json.dumps(body).encode())
    headers = {"Accept": accept, **({"Content-Type": "application/json"} if body is not None else {})}
    request = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as answer:
            text = answer.read().decode("utf-8")
            return answer.status, (json.loads(text) if text and "json" in answer.headers.get("Content-Type", "") else text)
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode("utf-8", "replace")


def sparql(query: str) -> dict:
    data = urllib.parse.urlencode({"query": query}).encode()
    request = urllib.request.Request(f"{STORE}/query", data=data, headers={"Accept": "application/sparql-results+json"})
    with urllib.request.urlopen(request, timeout=10) as answer:
        return json.load(answer)


def until(check, timeout: float, what: str):
    """Wait until ``check()`` returns something truthy; fail naming ``what`` and the last value."""
    deadline, last = time.monotonic() + timeout, None
    while time.monotonic() < deadline:
        last = check()
        if last and last is not None and last is not False:
            return last
        time.sleep(1)
    pytest.fail(f"{what} (last: {last!r})")


@pytest.fixture(scope="session")
def published():
    """aas-model's AASs of the line, created or replaced in the AAS environment; their AIMCs' ids."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "aas-model" / "src"))
    from basyx.aas.adapter.json import json_serialization
    from aas_model.builder import build_from_model
    from aas_model.resource_instances import RESOURCE_FACTORIES

    aimcs = []
    for name in PUBLISHED:
        store = build_from_model(RESOURCE_FACTORIES[name]())
        env = json.loads(json_serialization.object_store_to_json(store))
        for submodel in env["submodels"]:
            status, _ = http("POST", f"{AAS}/submodels", submodel)
            if status == 409:
                status, _ = http("PUT", f"{AAS}/submodels/{b64(submodel['id'])}", submodel)
            assert status < 300, f"{submodel['id']}: {status}"
            if submodel["idShort"] == "AssetInterfacesMappingConfiguration":
                aimcs.append(submodel["id"])
        for shell in env["assetAdministrationShells"]:
            status, _ = http("POST", f"{AAS}/shells", shell)
            if status == 409:
                status, _ = http("PUT", f"{AAS}/shells/{b64(shell['id'])}", shell)
            assert status < 300, f"{shell['id']}: {status}"
    return aimcs


def test_the_state_store_holds_the_vocabulary():
    found = sparql(f'PREFIX lab: <{LAB}> SELECT ?c WHERE {{ GRAPH <{BASE}/state/vocabulary> '
                   '{ lab:OccupiedBy lab:cardinality ?c } }')
    assert [b["c"]["value"] for b in found["results"]["bindings"]] == ["single"]


def test_the_dmp_installs_every_mapping_of_the_published_aass(published):
    def installed():
        status, found = http("GET", f"{DMP}/management/status")
        if status != 200 or not found.get("converged"):
            return None
        mine = []
        for aimc in published:
            _, answer = http("GET", f"{DMP}/management/mappings?aimc={urllib.parse.quote(aimc, safe='')}")
            mine += (answer or {}).get("mappings") or []
        broken = [(m.get("aimc") or "", m["listIndex"], m["state"], m.get("diagnostics")) for m in mine
                  if m["state"] != "installed"]
        return (len(mine), broken) if mine and not broken else None
    count, _ = until(installed, 180, "every mapping of the published AASs installed")
    assert count >= 20


def test_a_skill_call_reaches_the_station_and_its_state_the_store(published, request):
    if not request.config.getoption("--stations"):
        pytest.skip("the stations are not up (aas.py up --stations, pytest --stack --stations)")
    skills = f"{AAS}/submodels/{b64(STATION + '/submodels/Skills')}/submodel-elements"
    unit = str(uuid.uuid4())
    call = {"inputArguments": [], "clientTimeoutDuration": "PT30S", "inoutputArguments": [
        {"value": {"modelType": "Property", "idShort": "Uuid", "valueType": "xs:string", "value": unit}}]}
    query = (f'SELECT ?o WHERE {{ GRAPH ?g {{ <{STATION}> <{LAB}OccupiedBy> ?o }} }}')

    def occupied_by():
        return [b["o"]["value"] for b in sparql(query)["results"]["bindings"]]

    def answered(skill):
        status, answer = http("POST", f"{skills}/{skill}.Start.Start/invoke", call, timeout=60)
        assert status == 200, f"{skill}: {status} {answer}"
        assert answer.get("success"), answer
        return {v["value"]["idShort"]: v["value"].get("value") for v in answer.get("outputArguments") or []}

    assert until(lambda: answered("Occupy").get("State") == "SUCCESS", 60, "Occupy answered SUCCESS")
    until(lambda: occupied_by() == [f"urn:uuid:{unit}"], 30, "the store says the station serves the unit")
    assert answered("Release").get("State") == "SUCCESS"
    until(lambda: occupied_by() == [], 30, "OccupiedBy cleared")


def test_the_web_ui_answers_and_proxies_the_dmps_status():
    status, _ = http("GET", WEB_UI, accept="text/html")
    assert status == 200
    # The AIMC plugin reads what the DMP made of each mapping through the web UI's proxy.
    status, found = http("GET", f"{WEB_UI}/api/dmp/status")
    assert status == 200 and isinstance(found, dict) and "mappings" in found, found
