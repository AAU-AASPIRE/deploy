# deploy
Deployment of an AASPIRE line: the server stack (BaSyx, MongoDB, Mosquitto, XMPP, InfluxDB, the DMP, the web UI, the services) by Docker Compose, and a Raspberry Pi set up as an IEC 61499 module.

| What | Where |
| --- | --- |
| The lab's AAS stack: BaSyx with MongoDB, Mosquitto, Prosody, InfluxDB, the DMP, the web UI, the skill service, the agents | `aas/compose.yaml`, `aas.py` (`up`, `status`, `rows`, `down`) |
| Publish every AAS of the line (aas-model's instances, the example line, the modules on their Pis) | `publish.py` |
| A module's Raspberry Pi: FORTE's container (installed by forte-runtime's `install.sh`), install, run the module, its log | `pi/`, `pi.py` |
| At the bench: status, homing, moves and skills with a watchdog; the stepper's test | `bench.py`, `steptest.py` |
| Docker's own networks out of the lab network (172.20.0.0/15) | `docker_pools.py` (`pi.py pools` on a Pi) |
| The modules run in Python (modpy) on a Pi | `modpy/` |

```powershell
python aas.py up                                                     # the stack on this computer
python publish.py                                                    # every AAS, created or replaced
python pi.py install --spec ../aseptic-line/cell/modules/capping.yaml --forte ../forte-runtime/bin/forte-aarch64
python bench.py status --spec ../aseptic-line/cell/modules/capping.yaml
```

The tools find the other repositories beside this one (`AAU-AASPIRE/<repo>`): the line's specs in
`aseptic-line`, FORTE in `forte-runtime`, the DMP (`aas-camel-dmp`) and the web UI
(`basyx-aas-web-ui`) for the stack's images. The services' and modpy's images are built from the
folder that holds the repositories (`aas/services.Dockerfile`, `modpy/Dockerfile`). Part of
[AASPIRE](https://github.com/AAU-AASPIRE/aaspire).
