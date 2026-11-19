# ruff: noqa: E501
"""An Excel workbook for one reviewer of the FoodOn type review, and back.

The review's forms (data/alignment/review/round-1/reviewer-1.csv and reviewer-2.csv, protocol 3,
docs/alignment-review-v3.md) are CSV. A reviewer works better in Excel, and Excel changes what it opens: it
splits a comma-separated file wrongly in Portuguese, and may change accents and numbers. So:

- export writes a workbook from a form: instructions in Portuguese, the form with its context columns locked and
  only the answer columns open (a decision checked as a FoodOn CURIE or none), and every class of the pinned
  FoodOn release to look up;
- import copies the answers of a returned workbook into the form, matched by food number. The context always
  comes from the form, never from the workbook; a workbook with a food missing or added, or a decision that is
  neither a CURIE nor none, is refused, and nothing is written.

    $env:PYTHONPATH = "src"; python scripts/review_workbook.py export data/alignment/review/round-1/reviewer-1.csv --label "Revisora 1" --out revisora-1.xlsx
    $env:PYTHONPATH = "src"; python scripts/review_workbook.py import data/alignment/review/round-1/reviewer-1.csv --workbook revisora-1.xlsx
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill, Protection
from openpyxl.worksheet.datavalidation import DataValidation

from taco_rdf.namespaces import ROOT

CLASSES = ROOT / "ontology" / "imports" / "foodon-classes.tsv"
TACO_PDF = "https://nepa.unicamp.br/wp-content/uploads/sites/27/2023/10/taco_4_edicao_ampliada_e_revisada.pdf"
OLS = "https://www.ebi.ac.uk/ols4/ontologies/foodon"
CONTEXT = ["food_number", "name_pt", "name_en", "group", "candidates"]
ANSWERS = ["decision", "justification", "searched_terms", "unsure"]
HEADERS = ["Nº", "Alimento (TACO, português)", "Food (TACO, English)", "Grupo", "Candidatos (sugestões)",
           "Decisão", "Justificativa", "Termos buscados", "Insegura?"]
WIDTHS = [6, 34, 32, 22, 70, 19, 48, 32, 11]
CURIE = re.compile(r"^FOODON_\d{8}$")
FONT, BOLD = Font(name="Arial", size=10), Font(name="Arial", size=10, bold=True)
HEAD_FILL = PatternFill("solid", fgColor="D9D9D9")
ANSWER_FILL = PatternFill("solid", fgColor="FFF2CC")
EXAMPLE = ["(exemplo)", "Mirtilo, cru", "Blueberry, raw", "Frutas e derivados",
           "FOODON_00003541 blueberry [OLS]\nFOODON_00001656 blueberry food product [name]", "FOODON_00003541",
           "O alimento é o fruto cru do mirtilo. A classe blueberry é esse fruto (está sob 'blueberry food product' e "
           "'berry fruit'); é a mais específica que a descrição justifica.", "", ""]

INSTRUCTIONS = """Revisão dos tipos FoodOn dos alimentos da TACO — {label}

O QUE É
Para cada um dos 597 alimentos da TACO (Tabela Brasileira de Composição de Alimentos, 4ª edição), escolha a classe do FoodOn da qual o alimento, como a TACO o descreve, é um membro, ou "none" se nenhuma servir. O FoodOn é uma ontologia de alimentos: cada classe tem um código FOODON_ seguido de 8 dígitos e um nome em inglês.

COMO TRABALHAR
• Use a aba "Formulário". Preencha só as colunas amarelas: Decisão, Justificativa, Termos buscados e Insegura?. As outras colunas estão travadas.
• Não acrescente nem apague linhas. Pode responder em várias sessões: salve o arquivo (.xlsx) e continue depois.
• Os candidatos são sugestões automáticas (pelo nome do alimento, por alimentos parecidos da TACO e de outra tabela, e por uma busca no FoodOn). São só sugestões: a ordem não indica a resposta, e você pode escolher qualquer classe da aba "Classes FoodOn".

COMO DECIDIR
1. Escolha uma classe quando tudo o que a classe afirma vale para o alimento como a TACO o descreve: o nome em português e em inglês, o preparo (Apêndice 2 da TACO) e a espécie (Quadro 7 da TACO).
2. Entre as classes que servem, escolha a mais específica que a descrição justifica. Uma classe mais geral está certa quando nenhuma mais específica é justificada.
3. Não escolha uma classe que exija uma espécie, variedade, preparo ou ingrediente que a TACO não informa. Semelhança não basta.
4. Nunca escolha uma classe de organismo inteiro ou de planta (por exemplo, a planta Phaseolus vulgaris, e não o feijão como alimento). Se só uma classe assim parecer servir, escolha a classe de alimento mais próxima e explique na justificativa.
5. Escreva "none" quando nenhuma classe servir, e diga em "Termos buscados" o que você procurou.
6. A classe escolhida precisa estar na aba "Classes FoodOn" (a versão do FoodOn fixada no projeto, de 20/09/2026). Para ver a definição e as classes acima de uma classe, use o navegador OLS: {ols}

AS COLUNAS AMARELAS
• Decisão: o código da classe (por exemplo FOODON_00003541) ou none.
• Justificativa: por que o alimento é membro da classe, ou por que nenhuma serve.
• Termos buscados: o que você procurou além dos candidatos. Obrigatório quando a decisão é none.
• Insegura?: escreva "sim" quando tiver dúvida; deixe vazio caso contrário.

EXEMPLO
A aba "Exemplo" mostra uma linha preenchida, com um alimento que não está no formulário.

INDEPENDÊNCIA
Responda sozinha. Até as duas revisoras terminarem, não converse sobre os itens com a outra revisora e não consulte o repositório do projeto no GitHub nem os relatórios do projeto, que mostram tipos já usados. Dúvidas sobre o método: fale com Vitória.

ONDE ENCONTRAR A TACO
O PDF da TACO, com o Apêndice 2 (preparos) e o Quadro 7 (nomes científicos): {pdf}

AO TERMINAR
Salve o arquivo e devolva-o para Vitória."""


def header(sheet) -> None:
    """The form's header row: grey over the context, yellow over the answers."""
    for j, (head, width) in enumerate(zip(HEADERS, WIDTHS, strict=True), start=1):
        cell = sheet.cell(row=1, column=j, value=head)
        cell.font, cell.fill = BOLD, ANSWER_FILL if j > len(CONTEXT) else HEAD_FILL
        cell.alignment = Alignment(wrap_text=True, vertical="top")
        sheet.column_dimensions[chr(ord("A") + j - 1)].width = width


def read_form(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    with path.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        return list(reader.fieldnames or []), list(reader)


def export(form: Path, out: Path, label: str, classes: Path = CLASSES) -> int:
    fields, rows = read_form(form)
    if fields != CONTEXT + ANSWERS:
        raise ValueError(f"{form} is not a type-review form: {fields}")
    wb = Workbook()
    guide = wb.active
    guide.title = "Instruções"
    guide.column_dimensions["A"].width = 120
    for i, line in enumerate(INSTRUCTIONS.format(label=label, ols=OLS, pdf=TACO_PDF).split("\n"), start=1):
        cell = guide.cell(row=i, column=1, value=line)
        cell.font = BOLD if line.isupper() or i == 1 else FONT
        cell.alignment = Alignment(wrap_text=True, vertical="top")
    guide.protection.sheet = True

    example = wb.create_sheet("Exemplo")
    header(example)
    for j, value in enumerate(EXAMPLE, start=1):
        cell = example.cell(row=2, column=j, value=value)
        cell.font, cell.alignment = FONT, Alignment(wrap_text=True, vertical="top")
        if j > len(CONTEXT):
            cell.fill = ANSWER_FILL
    example.row_dimensions[2].height = 75
    example.protection.sheet = True

    sheet = wb.create_sheet("Formulário")
    header(sheet)
    for i, r in enumerate(rows, start=2):
        candidates = r["candidates"].replace(" | ", "\n")
        values = [int(r["food_number"]), r["name_pt"], r["name_en"], r["group"], candidates] + [r[k] for k in ANSWERS]
        for j, value in enumerate(values, start=1):
            cell = sheet.cell(row=i, column=j, value=value)
            cell.font, cell.alignment = FONT, Alignment(wrap_text=True, vertical="top")
            if j > len(CONTEXT):
                cell.fill, cell.protection = ANSWER_FILL, Protection(locked=False)
        sheet.row_dimensions[i].height = max(30, 13 * (candidates.count("\n") + 1))
    last = len(rows) + 1
    decision = DataValidation(type="custom", formula1='OR(F2="none",AND(LEFT(F2,7)="FOODON_",LEN(F2)=15))',
                              allow_blank=True, showErrorMessage=True, errorTitle="Decisão",
                              error="Escreva o código da classe (FOODON_ e 8 dígitos) ou none.")
    unsure = DataValidation(type="list", formula1='"sim"', allow_blank=True, showErrorMessage=True,
                            errorTitle="Insegura?", error='Escreva "sim" ou deixe vazio.')
    sheet.add_data_validation(decision)
    sheet.add_data_validation(unsure)
    decision.add(f"F2:F{last}")
    unsure.add(f"I2:I{last}")
    sheet.freeze_panes = "C2"
    sheet.auto_filter.ref = f"A1:I{last}"
    sheet.protection.sheet = True
    sheet.protection.autoFilter = False
    sheet.protection.formatColumns = False
    sheet.protection.formatRows = False

    lookup = wb.create_sheet("Classes FoodOn")
    for j, (head, width) in enumerate((("Código", 18), ("Classe (FoodOn, release 2026-09-20)", 80)), start=1):
        cell = lookup.cell(row=1, column=j, value=head)
        cell.font, cell.fill = BOLD, HEAD_FILL
        lookup.column_dimensions[chr(ord("A") + j - 1)].width = width
    with classes.open(encoding="utf-8") as fh:
        pairs = [line.rstrip("\n").split("\t", 1) for line in fh if line.startswith("FOODON_")]
    for i, (curie, name) in enumerate(pairs, start=2):
        lookup.cell(row=i, column=1, value=curie).font = FONT
        lookup.cell(row=i, column=2, value=name).font = FONT
    lookup.freeze_panes = "A2"
    lookup.auto_filter.ref = f"A1:B{len(pairs) + 1}"
    lookup.protection.sheet = True
    lookup.protection.autoFilter = False

    wb.active = 0
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    print(f"wrote {out}: {len(rows)} foods, {len(pairs)} FoodOn classes")
    return 0


def answers_in(workbook: Path) -> dict[int, dict[str, str]]:
    """The answers of a workbook's form, by food number."""
    wb = load_workbook(workbook, read_only=True)
    try:
        rows = iter(wb["Formulário"].iter_rows(values_only=True))
        heads = next(rows, ())
        if list(heads[:len(HEADERS)]) != HEADERS or any(v not in (None, "") for v in heads[len(HEADERS):]):
            raise ValueError(f"{workbook}: the form's columns changed")
        out = {}
        for row_number, row in enumerate(rows, start=2):
            if any(v not in (None, "") for v in row[len(HEADERS):]):
                raise ValueError(f"{workbook}: row {row_number} has data outside the form's columns")
            if all(v in (None, "") for v in row):
                continue
            raw_number = row[0]
            if raw_number in (None, ""):
                raise ValueError(f"{workbook}: row {row_number} has data but no food number")
            integer = (isinstance(raw_number, int)
                       or (isinstance(raw_number, float) and raw_number.is_integer())
                       or (isinstance(raw_number, str) and re.fullmatch(r"[0-9]+", raw_number.strip())))
            if isinstance(raw_number, bool) or not integer:
                raise ValueError(f"{workbook}: row {row_number} has a non-integer food number {raw_number!r}")
            number = int(raw_number)
            if number in out:
                raise ValueError(f"{workbook}: food {number} occurs more than once")
            values = ["" if v is None else str(v).strip() for v in row[len(CONTEXT):len(HEADERS)]]
            out[number] = dict(zip(ANSWERS, values, strict=True))
        return out
    finally:
        wb.close()


def problems(form_rows: list[dict[str, str]], answers: dict[int, dict[str, str]]) -> list[str]:
    numbers = [int(r["food_number"]) for r in form_rows]
    out = [f"food {n} is missing from the workbook" for n in numbers if n not in answers]
    out += [f"food {n} is not in the form" for n in answers if n not in set(numbers)]
    for n, a in sorted(answers.items()):
        if a["decision"] and a["decision"] != "none" and not CURIE.match(a["decision"]):
            out.append(f"food {n}: decision {a['decision']!r} is neither a FoodOn CURIE nor none")
        if a["unsure"] not in ("", "sim"):
            out.append(f"food {n}: Insegura? is {a['unsure']!r}, not 'sim' or empty")
    return out


def import_(form: Path, workbook: Path) -> int:
    fields, rows = read_form(form)
    answers = answers_in(workbook)
    found = problems(rows, answers)
    if found:
        for p in found:
            print(f"PROBLEM: {p}", file=sys.stderr)
        print(f"{len(found)} problems; {form} is unchanged", file=sys.stderr)
        return 1
    for r in rows:
        a = answers[int(r["food_number"])]
        r.update(a | {"unsure": "yes" if a["unsure"] == "sim" else ""})
    with form.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, lineterminator="\r\n")
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {form}: {sum(bool(r['decision']) for r in rows)} of {len(rows)} foods answered")
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="command", required=True)
    e = sub.add_parser("export", help="write a reviewer's workbook from a form")
    e.add_argument("form", type=Path)
    e.add_argument("--out", type=Path, required=True)
    e.add_argument("--label", required=True, help='how the workbook names the reviewer, e.g. "Revisora 1"')
    i = sub.add_parser("import", help="copy a returned workbook's answers into its form")
    i.add_argument("form", type=Path)
    i.add_argument("--workbook", type=Path, required=True)
    args = p.parse_args()
    if args.command == "export":
        return export(args.form, args.out, args.label)
    return import_(args.form, args.workbook)


if __name__ == "__main__":
    sys.exit(main())
