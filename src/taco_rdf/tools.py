"""Where the external tools some checks run are: Java, and a jar bundling Apache Jena (Fuseki's).

Each is taken from an environment variable if set (TACO_JAVA, TACO_FUSEKI_JAR); otherwise Java is looked
for on the PATH, under JAVA_HOME and in the usual install folders, newest first, and the jar beside the
project, where triplestore/README.md unpacks Fuseki.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from .namespaces import ROOT

FUSEKI_JAR = ROOT.parent / "tools" / "apache-jena-fuseki-6.2.0" / "fuseki-server.jar"


def java() -> str:
    """The java command to run, or 'java' if none is found (the call then fails with a clear error)."""
    if os.environ.get("TACO_JAVA"):
        return os.environ["TACO_JAVA"]
    on_path = shutil.which("java")
    if on_path:
        return on_path
    exe = "java.exe" if os.name == "nt" else "java"
    if os.environ.get("JAVA_HOME") and (Path(os.environ["JAVA_HOME"]) / "bin" / exe).is_file():
        return str(Path(os.environ["JAVA_HOME"]) / "bin" / exe)
    installs = (("LOCALAPPDATA", "Programs/Java"), ("ProgramFiles", "Java"),
                ("ProgramFiles", "Eclipse Adoptium"))
    roots = [Path(os.environ[v]) / sub for v, sub in installs if os.environ.get(v)]
    roots += [Path("/usr/lib/jvm"), Path("/Library/Java/JavaVirtualMachines")]
    found = sorted((p for r in roots if r.is_dir() for p in r.glob(f"*/**/bin/{exe}")), reverse=True)
    return str(found[0]) if found else "java"


def fuseki_jar() -> Path:
    """The jar whose arq.sparql and shacl commands the checks run."""
    return Path(os.environ.get("TACO_FUSEKI_JAR", FUSEKI_JAR))
