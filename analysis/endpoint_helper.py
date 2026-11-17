"""Run the project's SPARQL queries against a triple store, as NICE-Food's analysis does.

open_query and sparql_query_to_dataframe follow functions/wrapper_helper.py in rivm-syso/nicekg_analysis: the
query is read from an .rq file, sent with SPARQLWrapper and returned as a pandas DataFrame of strings. bind
adds a VALUES clause in place of the pre-bound variables that taco_rdf.queries.run_query passes to rdflib.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd
from SPARQLWrapper import JSON, SPARQLWrapper

FUSEKI = "http://localhost:3030/taco_nevo/sparql"


def open_query(path: str | Path) -> str:
    """The text of an .rq file."""
    return Path(path).read_text(encoding="utf-8")


def bind(query: str, **values: str) -> str:
    """The query with each variable fixed to one value, e.g. bind(q, **{"class": "<http://...>"}).

    The VALUES clause opens the WHERE clause, so the store starts from the fixed values; at the end of the
    query, after the WHERE clause, Fuseki would join it only after evaluating everything else.
    """
    if not values:
        return query
    clause = f"VALUES ({' '.join(f'?{var}' for var in values)}) {{ ({' '.join(values.values())}) }}"
    if "WHERE {" in query:
        return query.replace("WHERE {", f"WHERE {{\n  {clause}", 1)
    return f"{query.rstrip()}\n{clause}\n"


def substitute(query: str, **values: str) -> str:
    """The query with each variable written as its value, as rdflib's pre-bound variables behave.

    Fuseki does not carry a VALUES clause into the branches of a UNION, so a query made of UNIONs, such as
    taco_nevo_food_graph.rq, scans every food unless the values are written in. Inside the WHERE clause each
    variable becomes its value; in the SELECT clause it becomes (value AS ?variable); comments and the
    clauses after WHERE are left alone.
    """
    start = query.index("WHERE {")
    depth, end = 0, len(query)
    for i in range(start, len(query)):
        depth += {"{": 1, "}": -1}.get(query[i], 0)
        if query[i] == "}" and depth == 0:
            end = i + 1
            break
    head, where, tail = query[:start], query[start:end], query[end:]
    for var, value in values.items():
        name = re.compile(rf"\?{re.escape(var)}\b")
        head = "\n".join(line if line.lstrip().startswith("#") else name.sub(f"({value} AS ?{var})", line)
                         for line in head.split("\n"))
        where = "\n".join(line if line.lstrip().startswith("#") else name.sub(value, line)
                          for line in where.split("\n"))
    return head + where + tail


def sparql_query_to_dataframe(query: str, endpoint: str = FUSEKI) -> pd.DataFrame:
    """The results of a SELECT query, one column per variable, every value a string.

    Comment lines are dropped first: SPARQLWrapper guesses the query type from keywords in the whole text,
    and a comment mentioning load or delete would make it send the query as an update.
    """
    sparql = SPARQLWrapper(endpoint)
    sparql.setReturnFormat(JSON)
    sparql.setQuery("\n".join(line for line in query.splitlines() if not line.lstrip().startswith("#")))
    results = sparql.queryAndConvert()
    bindings = results["results"]["bindings"]
    rows = [{var: cell["value"] for var, cell in binding.items()} for binding in bindings]
    return pd.DataFrame(rows, columns=results["head"]["vars"])
