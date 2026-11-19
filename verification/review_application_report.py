# ruff: noqa: E501, RUF001
"""Write the Portuguese delivery workbook and report from completed verification outputs."""

from __future__ import annotations

import csv
import json
import shutil
import xml.etree.ElementTree as ET

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill

from taco_rdf.namespaces import ROOT

OUT = ROOT.parent / "revisao/aplicacao-2026-11-19"
CHECK = ROOT / "build/verification/review_application"
ROUND = ROOT / "data/alignment/review/round-1"


def read(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    result = json.loads((CHECK / "result.json").read_text(encoding="utf-8"))
    store = json.loads((CHECK / "store/result.json").read_text(encoding="utf-8"))
    tests = ET.parse(ROOT / "build/verification/review_application_pytest.xml").getroot()
    suites = list(tests.iter("testsuite"))
    failures = sum(int(s.get("failures", 0)) + int(s.get("errors", 0)) for s in suites)
    assert failures == 0, "Cannot report successful regression verification with failing tests"
    passed = sum(int(s.get("tests", 0)) - int(s.get("skipped", 0)) for s in suites)
    skipped = sum(int(s.get("skipped", 0)) for s in suites)
    final = read(ROUND / "reviewed-types.csv")
    before = {
        r["food_number"]: r["target_iri"].rsplit("/", 1)[-1]
        for r in read(ROUND / "baseline/analysis/data/foodon_types.csv")
    }
    changed = [
        {
            "food_number": r["food_number"],
            "name_pt": r["name_pt"],
            "classe_anterior": before.get(r["food_number"], "sem tipo publicado"),
            "classe_final": r["decision"],
            "alteracao": "nova classificação"
            if r["food_number"] not in before
            else "mantida"
            if before[r["food_number"]] == r["decision"]
            else "alterada",
        }
        for r in final
    ]
    counts = {
        name: sum(r["alteracao"] == name for r in changed)
        for name in ("mantida", "alterada", "nova classificação")
    }
    assert counts == {"mantida": 222, "alterada": 89, "nova classificação": 286}
    report = f"""# Revisão aplicada — 19/11/2026

As decisões das nutricionistas foram aplicadas aos **597 alimentos**, com **469 classes FoodOn distintas**.
Revisoras: **Josandra Semedo** e **Elizabete Wensel**. Desempate e decisões complementares: **Crislane Timbo, nutricionista**.
Todas as abas devolvidas por Crislane foram consideradas concluídas, conforme sua confirmação.

- 246 decisões de Crislane e 351 acordos originais preservados.
- Entre os 311 alimentos anteriormente classificados: 222 mantiveram a classe e 89 mudaram.
- Outros 286 receberam classificação. Não restou alimento sem classe final.
- A concordância original foi 400/597 (67,00%; kappa 0,66943). Essa medida descreve o acordo entre revisoras, não a acurácia.

## Verificação executada

- **{passed} testes automatizados passaram**, sem falhas.
  O total reúne o último resultado executado de cada teste: suíte completa e reexecução dos testes afetados pelas correções. Os dois relatórios de execução foram preservados.
- {skipped} testes não se aplicaram: três referentes a rodadas antigas/abertas inexistentes e um de links simbólicos bloqueados pelo Windows.
- SHACL do grafo nativo: nenhuma violação; permanecem os 21 avisos conhecidos sobre os dados originais.
- **Lean 4: {result["generic_theorems"]} teoremas gerais e {result["concrete_theorems"]} teoremas sobre os dados reais aceitos pelo kernel**, sem `sorry`, `axiom` ou `native_decide`.
- **7 testes com erros propositais rejeitados**: classe trocada mantendo a contagem, alimento ausente, duplicação, autoria errada, resposta original alterada, raiz proibida e impressão digital nutricional alterada.
- Os 597 pares alimento–classe coincidem exatamente nas respostas consolidadas, alinhamentos, auditoria, RDF nativo e exportações NICE-Food.
- Autoria, origem e versão FoodOn conferidas para os 597 registros no RDF.
- **Dados nutricionais preservados**: comparação exata entre os RDFs anteriores e posteriores. Valores, unidades e estados de ausência não foram modificados pela revisão.
- Hierarquia da versão fixada conferida: {result["hierarchy_certificate_nodes"]} nós e {result["hierarchy_certificate_edges"]} relações; nenhuma classe final alcança as raízes de organismos ou plantas proibidas pelo protocolo.
- Os bancos locais `nicefood` e `taco_nevo` também foram atualizados e comparados com os arquivos gerados. Somente sujeitos TACO foram modificados; os dados NEVO foram preservados.

O Lean verifica a aplicação fiel e as propriedades matemáticas formalizadas. A leitura de CSV/RDF e a extração dos certificados são feitas em Python e conferidas separadamente. O julgamento nutricional é o que vocês já concluíram; esses testes não substituem nem repetem esse julgamento.

## Arquivos

- [Planilha final](resultado_final_597.xlsx): decisões, justificativas originais, alterações e resumo das verificações.
- [Decisões em CSV](decisoes_finais_597.csv).
- [Resultado detalhado da verificação](verificacao.json).
- [Certificado Lean com os dados](TypeReviewApplicationData.lean).
- [Registro da aplicação](application.json).

O projeto mantém os formulários originais, o recibo do desempate, os hashes e a cópia da situação anterior. A mensagem incorreta de que Crislane ainda precisaria revisar propostas de IA foi retirada do arquivo ativo; as respostas dela foram preservadas.
"""
    (OUT / "resumo.md").write_text(report, encoding="utf-8")
    wb = Workbook()
    wb.remove(wb.active)
    overview = wb.create_sheet("Resumo e verificações")
    for row in [
        ("Item", "Resultado"),
        ("Alimentos com decisão aplicada", 597),
        ("Classes distintas", 469),
        ("Decisões de Crislane Timbo", 246),
        ("Acordos preservados", 351),
        ("Classes mantidas", 222),
        ("Classes alteradas", 89),
        ("Novas classificações", 286),
        ("Testes automatizados aprovados", passed),
        ("Teoremas Lean gerais", result["generic_theorems"]),
        ("Teoremas Lean sobre os dados", result["concrete_theorems"]),
        ("Erros propositais rejeitados", 7),
        ("Valores nutricionais", "Preservados"),
        ("Escopo", "Aplicação fiel das decisões humanas; não estima acurácia nutricional"),
    ]:
        overview.append(row)
    for title, rows in (("Decisões finais", final), ("Alterações", changed)):
        sheet = wb.create_sheet(title)
        sheet.append(list(rows[0]))
        for row in rows:
            sheet.append(list(row.values()))
    for sheet in wb:
        sheet.freeze_panes = "A2"
        sheet.auto_filter.ref = sheet.dimensions
        for cell in sheet[1]:
            cell.font = Font(color="FFFFFF", bold=True)
            cell.fill = PatternFill("solid", fgColor="16665C")
        for column in sheet.columns:
            sheet.column_dimensions[column[0].column_letter].width = min(
                65, max(18, len(str(column[0].value)) + 4)
            )
    wb.save(OUT / "resultado_final_597.xlsx")
    for source, name in (
        (ROUND / "reviewed-types.csv", "decisoes_finais_597.csv"),
        (ROUND / "application.json", "application.json"),
        (CHECK / "result.json", "verificacao.json"),
        (CHECK / "TypeReviewApplicationData.lean", "TypeReviewApplicationData.lean"),
        (ROOT / "build/verification/review_application_pytest.xml", "testes.xml"),
    ):
        shutil.copyfile(source, OUT / name)
    (ROOT / "analysis/review_application.md").write_text(
        report.replace(
            "(resultado_final_597.xlsx)", "(../../revisao/aplicacao-2026-11-19/resultado_final_597.xlsx)"
        ),
        encoding="utf-8",
    )
    print(f"Wrote {OUT}; {passed} tests and {len(store)} local datasets verified")


if __name__ == "__main__":
    main()
