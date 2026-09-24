# How to publish taco-rdf (GitHub, Pages, Zenodo DOI, w3id)

Everything that can live in the repository is already in place: licences (`LICENSE`, `LICENSE-DATA.md`),
citation metadata (`CITATION.cff`, `.zenodo.json`), the static site generator (`taco-rdf publish`), the
GitHub Pages workflow (`.github/workflows/pages.yml`) and the w3id rules in this folder. What is left needs
your accounts, and **the order matters**: the w3id redirect points at GitHub Pages, and Zenodo only mints a
DOI for releases made *after* it is switched on.

This folder is not part of the taco-rdf package; `.htaccess` and `README.md` are copied into the w3id.org
repository (step 5). This file stays here.

## 1. Push to GitHub (public)

```powershell
git init -b main
git add .
git commit -m "taco-rdf 0.1.0"
git remote add origin https://github.com/Victoria125/taco-rdf.git   
git push -u origin main
```

## 2. Turn on GitHub Pages

Repository -> Settings -> Pages -> *Build and deployment* -> Source: **GitHub Actions**.
Then Actions -> *Publish site* -> *Run workflow* (it also runs on every push to `main`).
Check that <https://victoria125.github.io/taco-rdf/> and
<https://victoria125.github.io/taco-rdf/id/food/1.html> load.

## 3. Switch Zenodo on for the repository (before any release)

Log in to <https://zenodo.org> with GitHub -> *GitHub* (account menu) -> *Sync now* -> flip the switch next
to `Victoria125/taco-rdf`. Zenodo reads `.zenodo.json` for the record's metadata.

## 4. Make a release -> DOI

GitHub -> Releases -> *Draft a new release* -> tag `v0.1.0` -> *Publish release*. Within minutes Zenodo
archives that release and mints a DOI (shown on the Zenodo record, *Versions* sidebar). Then:

1. set `DOI = "10.5281/zenodo.NNNNNNN"` in `src/taco_rdf/metadata.py` (the graph gets `dcterms:identifier`
   and the landing page gets the DOI in its schema.org metadata);
2. add `doi: 10.5281/zenodo.NNNNNNN` to `CITATION.cff` and the DOI badge to `README.md`;
3. commit and push (the Pages workflow republishes).

Use the **concept DOI** (the one that always resolves to the latest version) in citations of the project, and
the version DOI when you need to pin exact values.

## 5. Register `https://w3id.org/taco-rdf/`

Only after step 2, because a redirect to a 404 is worse than no redirect.

1. Fork <https://github.com/perma-id/w3id.org>.
2. In the fork, create `ids/taco-rdf/` and copy this folder's `.htaccess` and `README.md` into it.
3. Commit (`Add taco-rdf`) and open a pull request against `perma-id/w3id.org` (branch `master`).
4. After a maintainer merges it, check content negotiation:

```powershell
curl.exe -sI https://w3id.org/taco-rdf/id/food/1                          # 303 -> .../id/food/1.html
curl.exe -sI -H "Accept: text/turtle" https://w3id.org/taco-rdf/id/food/1  # 303 -> .../id/food/1.ttl
curl.exe -sIL -H "Accept: text/turtle" https://w3id.org/taco-rdf/vocab     # ends at vocab.ttl, 200
```

## 6. Catalogues

* **DataCite / Zenodo**: done by step 4; the DOI record is harvested by DataCite, OpenAIRE and Google Scholar.
* **Google Dataset Search**: the landing page carries schema.org `Dataset` markup; it is picked up once the
  site is crawled (optionally submit the URL in Google Search Console).
* **FAIRsharing** (optional, <https://fairsharing.org/new>): register the dataset and link the DOI.

## SPARQL endpoint

`taco-rdf serve` runs a read-only SPARQL 1.1 Protocol endpoint (`/sparql`) over the graph. It is not hosted
publicly; GitHub Pages only serves static files. The dumps (`taco.ttl`, `taco.nt`) and the per-resource
documents are what make the data accessible over HTTP without it. To host the endpoint, run
`taco-rdf serve --host 0.0.0.0 --port 8000` on any machine with Python, behind HTTPS.
