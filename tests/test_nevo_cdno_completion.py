"""NEVO's values get a CDNO class only where TACO's values of the same NEVO code carry exactly one."""

from __future__ import annotations

import importlib.util

from taco_rdf.namespaces import ROOT

spec = importlib.util.spec_from_file_location("nevo_cdno_completion",
                                              ROOT / "scripts" / "nevo_cdno_completion.py")
assert spec is not None and spec.loader is not None
completion = importlib.util.module_from_spec(spec)
spec.loader.exec_module(completion)

NUT = "https://data.rivm.nl/data/nvip/bigfood/nevo/nutrient#"
OBO = "http://purl.obolibrary.org/obo/"


def test_a_code_gets_the_one_class_taco_gives_it():
    without = [{"n": NUT + "FAT", "label": "Fat total", "values": "3346"},
               {"n": NUT + "TRP", "label": "Tryptophan", "values": "14"},
               {"n": NUT + "ALC", "label": "Alcohol total", "values": "1673"},
               {"n": NUT + "X", "label": "Two classes", "values": "5"}]
    taco = [{"n": NUT + "FAT", "c": OBO + "CDNO_0200068", "label": "concentration of lipid"},
            {"n": NUT + "TRP", "c": OBO + "CDNO_0200065", "label": "concentration of tryptophan"},
            {"n": NUT + "PROT", "c": OBO + "CDNO_0200040", "label": "concentration of protein"},
            {"n": NUT + "X", "c": OBO + "CDNO_1", "label": "one"},
            {"n": NUT + "X", "c": OBO + "CDNO_2", "label": "two"}]
    found = completion.completion(without, taco)
    assert [(r["nevo_code"], r["cdno_class"], r["nevo_values"]) for r in found] == [
        ("FAT", "CDNO_0200068", "3346"), ("TRP", "CDNO_0200065", "14")]
