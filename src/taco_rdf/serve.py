"""Read-only SPARQL 1.1 endpoint over the graph (taco-rdf serve)."""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from rdflib import Graph

_RESULTS = {
    "application/sparql-results+json": "json",
    "application/json": "json",
    "text/csv": "csv",
    "text/tab-separated-values": "tsv",
    "application/sparql-results+xml": "xml",
}
_GRAPHS = {
    "text/turtle": "turtle",
    "application/ld+json": "json-ld",
    "application/n-triples": "nt",
}


def _pick(accept: str, table: dict[str, str], default: str) -> tuple[str, str]:
    for part in accept.split(","):
        media = part.split(";")[0].strip()
        if media in table:
            return media, table[media]
    return default, table[default]


def make_handler(g: Graph) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            url = urlparse(self.path)
            if url.path != "/sparql":
                return self._send(404, "text/plain", b"SPARQL endpoint is at /sparql\n")
            query = parse_qs(url.query).get("query", [None])[0]
            if query is None:
                return self._send(400, "text/plain", b"missing 'query' parameter\n")
            self._answer(query)

        def do_POST(self) -> None:
            if urlparse(self.path).path != "/sparql":
                return self._send(404, "text/plain", b"SPARQL endpoint is at /sparql\n")
            body = self.rfile.read(int(self.headers.get("Content-Length") or 0)).decode("utf-8")
            ctype = (self.headers.get("Content-Type") or "").split(";")[0].strip()
            if ctype == "application/sparql-query":
                query = body
            elif ctype == "application/x-www-form-urlencoded":
                form = parse_qs(body)
                if "update" in form:
                    return self._send(403, "text/plain", b"read-only endpoint: updates are refused\n")
                query = form.get("query", [None])[0]
            else:
                return self._send(415, "text/plain", b"use application/sparql-query or a form\n")
            if query is None:
                return self._send(400, "text/plain", b"missing 'query'\n")
            self._answer(query)

        def do_OPTIONS(self) -> None:
            self._send(204, "text/plain", b"")

        def _answer(self, query: str) -> None:
            try:
                result = g.query(query)
            except Exception as exc:
                return self._send(400, "text/plain", f"query error: {exc}\n".encode())
            accept = self.headers.get("Accept") or ""
            if result.type in ("SELECT", "ASK"):
                table = _RESULTS if result.type == "SELECT" else {
                    m: f for m, f in _RESULTS.items() if f in ("json", "xml")}
                media, fmt = _pick(accept, table, "application/sparql-results+json")
            else:
                media, fmt = _pick(accept, _GRAPHS, "text/turtle")
            self._send(200, media, result.serialize(format=fmt, encoding="utf-8"))

        def _send(self, status: int, media: str, payload: bytes) -> None:
            self.send_response(status)
            self.send_header("Content-Type", f"{media}; charset=utf-8")
            self.send_header("Content-Length", str(len(payload)))
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, Accept")
            self.end_headers()
            self.wfile.write(payload)

    return Handler


def serve(g: Graph, host: str = "127.0.0.1", port: int = 8000) -> None:
    server = ThreadingHTTPServer((host, port), make_handler(g))
    print(f"SPARQL endpoint on http://{host}:{port}/sparql ({len(g):,} triples); Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
