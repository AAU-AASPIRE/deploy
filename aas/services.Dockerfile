# AASPIRE's Python services for the lab's AAS stack (compose.yaml here): the skill service (modreg
# serve: matching, planning and checking for the web UI, the process AAS) and the line's agents
# (AAS-MAS, python -m lineagents). Built from the folder that holds the repositories side by side
# (AAU-AASPIRE); services.Dockerfile.dockerignore keeps the context to what is copied:
#   docker build -f deploy/aas/services.Dockerfile -t lab-services .     (in AAU-AASPIRE)
# The repositories are installed editable without their dependencies on each other (those name the
# GitHub repositories); the other dependencies are listed here. The tools find the ontologies, the
# line's specs beside them, and the agents modlink in aaspire-tools, as on a PC.
FROM python:3.12-slim
WORKDIR /app
RUN pip install --no-cache-dir "pydantic>=2.9,<3" "defusedxml>=0.7,<1" "pyyaml>=6,<7" "rdflib>=7,<8" \
        "gtpyhop-core==2.0.2" "basyx-python-sdk>=2.1,<3" "zeroconf>=0.132" "asyncua>=1.1" \
        "spade>=4.1,<5" "greenlet>=3" "paho-mqtt>=2" \
        "aas-model @ https://github.com/AAU-AASPIRE/aas-model/archive/68c4a0d1b351ce2c90d05cbb0fa5c4553cf87317.zip"
COPY iec61499-mgmt-py iec61499-mgmt-py
COPY aaspire-tools aaspire-tools
COPY AAS-MAS AAS-MAS
RUN for r in iec61499-mgmt-py aaspire-tools AAS-MAS; do \
        pip install --no-cache-dir --no-deps -e "./$r" || exit 1; done
COPY ontologies ontologies
COPY aseptic-line/cell/modules aseptic-line/cell/modules
# The skill service, and the agents' orders over HTTP (POST /orders).
EXPOSE 8090 8095
