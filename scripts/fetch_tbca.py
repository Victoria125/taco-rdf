"""Download TBCA, the Brazilian food composition table of USP/FoRC, into data/external/tbca/.

TBCA's terms of use (https://www.tbca.net.br/) forbid reproducing or altering its content without the
coordinators' permission. This project uses it with the permission data/SOURCES.md records; the downloaded
pages and tables stay in data/external/, which git ignores, and nothing from them is published without that
permission in writing.

The script reads the paginated list of foods of TBCA's database for nutrient intake assessment (BD-AIN),
follows each food's link to its composition page, keeps every page it fetched in html/ so a rerun fetches
only what is missing, and waits between requests so as not to load the server. It writes:
- foods.csv: code, group, food type, scientific name and the Portuguese, English and Spanish descriptions;
- values.csv: one row per food and component, with the unit and the value per 100 g as TBCA gives it.
"""

from __future__ import annotations

import argparse
import csv
import html
import http.client
import re
import sys
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from taco_rdf.namespaces import ROOT

BASE = "https://www.tbca.net.br/base-dados/"
LIST = BASE + "composicao_alimentos.php?pagina={page}"
OUT = ROOT / "data" / "external" / "tbca"
USER_AGENT = "taco-rdf research script (https://github.com/Victoria125/taco-rdf)"
ROW = re.compile(r"<tr><td><a href='(int_composicao_alimentos\.php\?[^']+)'>([A-Z]{3}\d{4}[A-Z])</a></td>")
FIELD = re.compile(r"(Código|Grupo|Tipo de Alimento|Nome Científico|Descrição):\s*(.*?)\s*(?=Código:|Grupo:|"
                   r"Tipo de Alimento:|Nome Científico:|Descrição:|Valores|$)")
VALUE = re.compile(r"<tr><td>([^<]+)</td><td>([^<]*)</td><td>([^<]*)</td>")


def get(url: str, delay: float) -> str:
    """The page at url as text, after waiting delay seconds, with three tries."""
    for attempt in range(3):
        time.sleep(delay * (attempt + 1))
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=60) as r:
                raw = r.read()
            try:
                return raw.decode("utf-8")
            except UnicodeDecodeError:
                return raw.decode("latin-1")
        except (OSError, http.client.HTTPException) as exc:  # e.g. a response cut short (IncompleteRead)
            print(f"retrying {url}: {exc!r}", file=sys.stderr, flush=True)
    raise OSError(f"could not fetch {url}")


def food_links(delay: float) -> dict[str, str]:
    """Every food code in the list, with the URL of its composition page, page by page until one adds none."""
    links: dict[str, str] = {}
    page = 1
    while True:
        listing = get(LIST.format(page=page), delay)
        found = {code: BASE + html.unescape(href) for href, code in ROW.findall(listing)}
        new = {c: u for c, u in found.items() if c not in links}
        if not new:
            return links
        links.update(new)
        print(f"list page {page}: {len(links)} foods", flush=True)
        page += 1


def text(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def parse(page: str) -> tuple[dict[str, str], list[dict[str, str]]]:
    """A food's fields and its rows of components, from its composition page."""
    header = text(page.split("<table", 1)[0])
    fields = {name: value for name, value in FIELD.findall(header)}
    descriptions = [d.strip(" <>") for d in re.split(r"<<|>>", fields.get("Descrição", "")) if d.strip(" <>")]
    food = {"code": fields.get("Código", ""), "group": fields.get("Grupo", ""),
            "food_type": fields.get("Tipo de Alimento", ""),
            "scientific_name": fields.get("Nome Científico", ""),
            "name_pt": descriptions[0] if descriptions else "",
            "name_en": descriptions[1] if len(descriptions) > 1 else "",
            "name_es": descriptions[2] if len(descriptions) > 2 else ""}
    values = [{"code": food["code"], "component": text(c), "unit": text(u), "value_per_100g": text(v)}
              for c, u, v in VALUE.findall(page)]
    return food, values


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("-o", "--out", type=Path, default=OUT, help=f"folder to write to (default {OUT})")
    p.add_argument("--delay", type=float, default=1.0, help="seconds to wait before each request (default 1)")
    p.add_argument("--limit", type=int, help="fetch only this many food pages, to try the script")
    p.add_argument("--workers", type=int, default=1,
                   help="requests at a time, each still waiting --delay (default 1; keep it small)")
    args = p.parse_args()
    pages = args.out / "html"
    pages.mkdir(parents=True, exist_ok=True)
    links = food_links(args.delay)
    codes = sorted(links)[: args.limit] if args.limit else sorted(links)
    missing = [c for c in codes if not (pages / f"{c}.html").is_file()]
    print(f"{len(codes) - len(missing)} food pages already here, {len(missing)} to fetch", flush=True)

    def fetch(code: str) -> None:
        (pages / f"{code}.html").write_text(get(links[code], args.delay), encoding="utf-8")

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for i, _ in enumerate(pool.map(fetch, missing), 1):
            if i % 100 == 0 or i == len(missing):
                print(f"{i} of {len(missing)} food pages fetched", flush=True)
    foods, values = [], []
    for code in codes:
        food, rows = parse((pages / f"{code}.html").read_text(encoding="utf-8"))
        foods.append(food)
        values.extend(rows)
    for name, rows in (("foods.csv", foods), ("values.csv", values)):
        with (args.out / name).open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0]), lineterminator="\n")
            w.writeheader()
            w.writerows(rows)
    print(f"wrote {len(foods)} foods and {len(values)} values to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
