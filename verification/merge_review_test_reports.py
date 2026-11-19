"""Keep the latest executed result of each test, preserving both original run reports."""
import xml.etree.ElementTree as ET

from taco_rdf.namespaces import ROOT


def main():
    folder = ROOT / "build/verification"
    paths = [folder / "review_application_pytest_initial.xml", folder / "review_application_pytest_recheck.xml"]
    results = {}
    initial_failures = set()
    for i, path in enumerate(paths):
        for case in ET.parse(path).iter("testcase"):
            key = case.get("classname"), case.get("name")
            if i == 0 and (case.find("failure") is not None or case.find("error") is not None):
                initial_failures.add(key)
            if i == 1:
                initial_failures.discard(key)
            results[key] = case
    assert not initial_failures, f"Failing tests were not rerun: {initial_failures}"
    assert not any(c.find("failure") is not None or c.find("error") is not None for c in results.values())
    skipped = sum(c.find("skipped") is not None for c in results.values())
    root = ET.Element("testsuites")
    suite = ET.SubElement(root, "testsuite", name="Latest results: full suite plus affected-test rerun",
                          tests=str(len(results)), failures="0", errors="0", skipped=str(skipped))
    properties = ET.SubElement(suite, "properties")
    ET.SubElement(properties, "property", name="source_reports", value=";".join(p.name for p in paths))
    suite.extend(results[key] for key in sorted(results))
    ET.ElementTree(root).write(folder / "review_application_pytest.xml", encoding="utf-8", xml_declaration=True)
    print(f"{len(results) - skipped} passed, {skipped} skipped; latest executed results, two preserved runs")


if __name__ == "__main__":
    main()
