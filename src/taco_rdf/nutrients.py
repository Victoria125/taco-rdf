from __future__ import annotations

from dataclasses import dataclass

SHEET_COMPOSITION = 0
SHEET_FATTY_ACIDS = 1
SHEET_AMINO_ACIDS = 2

UNIT_HEADER_TO_QUDT = {
    "(%)": "PERCENT",
    "(kcal)": "KiloCAL",
    "(kJ)": "KiloJ",
    "(g)": "GM",
    "(mg)": "MilliGM",
    "(mcg)": "MicroGM",
}

CATEGORIES = {
    "proximate": ("Composição centesimal", "Proximate composition"),
    "energy": ("Energia", "Energy"),
    "mineral": ("Minerais", "Minerals"),
    "vitamin": ("Vitaminas", "Vitamins"),
    "fatty_acid": ("Ácidos graxos", "Fatty acids"),
    "amino_acid": ("Aminoácidos", "Amino acids"),
}


@dataclass(frozen=True)
class Nutrient:
    key: str
    sheet: int
    col: int
    header: str
    unit_header: str
    label_pt: str
    label_en: str
    category: str

    @property
    def qudt_unit(self) -> str:
        return UNIT_HEADER_TO_QUDT[self.unit_header]


def _n(key, sheet, col, header, unit, pt, en, category):
    return Nutrient(key, sheet, col, header, unit, pt, en, category)


C, F, A = SHEET_COMPOSITION, SHEET_FATTY_ACIDS, SHEET_AMINO_ACIDS

NUTRIENTS: tuple[Nutrient, ...] = (
    _n("moisture", C, 2, "Umidade", "(%)", "Umidade", "Moisture", "proximate"),
    _n("energy_kcal", C, 3, "Energia", "(kcal)", "Energia (kcal)", "Energy (kcal)", "energy"),
    _n("energy_kj", C, 4, "", "(kJ)", "Energia (kJ)", "Energy (kJ)", "energy"),
    _n("protein", C, 5, "Proteína", "(g)", "Proteína", "Protein", "proximate"),
    _n("lipids", C, 6, "Lipídeos", "(g)", "Lipídeos", "Lipids", "proximate"),
    _n("cholesterol", C, 7, "Colesterol", "(mg)", "Colesterol", "Cholesterol", "proximate"),
    _n("carbohydrate", C, 8, "idrato", "(g)", "Carboidrato", "Carbohydrate", "proximate"),
    _n("dietary_fiber", C, 9, "Alimentar", "(g)", "Fibra alimentar", "Dietary fibre", "proximate"),
    _n("ash", C, 10, "Cinzas", "(g)", "Cinzas", "Ash", "proximate"),
    _n("calcium", C, 11, "Cálcio", "(mg)", "Cálcio", "Calcium", "mineral"),
    _n("magnesium", C, 12, "Magnésio", "(mg)", "Magnésio", "Magnesium", "mineral"),
    _n("manganese", C, 14, "Manganês", "(mg)", "Manganês", "Manganese", "mineral"),
    _n("phosphorus", C, 15, "Fósforo", "(mg)", "Fósforo", "Phosphorus", "mineral"),
    _n("iron", C, 16, "Ferro", "(mg)", "Ferro", "Iron", "mineral"),
    _n("sodium", C, 17, "Sódio", "(mg)", "Sódio", "Sodium", "mineral"),
    _n("potassium", C, 18, "Potássio", "(mg)", "Potássio", "Potassium", "mineral"),
    _n("copper", C, 19, "Cobre", "(mg)", "Cobre", "Copper", "mineral"),
    _n("zinc", C, 20, "Zinco", "(mg)", "Zinco", "Zinc", "mineral"),
    _n("retinol", C, 21, "Retinol", "(mcg)", "Retinol", "Retinol", "vitamin"),
    _n("re", C, 22, "RE", "(mcg)", "Equivalente de retinol (RE)", "Retinol equivalents (RE)", "vitamin"),
    _n("rae", C, 23, "RAE", "(mcg)", "Equivalente de atividade de retinol (RAE)",
       "Retinol activity equivalents (RAE)", "vitamin"),
    _n("thiamin", C, 24, "Tiamina", "(mg)", "Tiamina", "Thiamin", "vitamin"),
    _n("riboflavin", C, 25, "Riboflavina", "(mg)", "Riboflavina", "Riboflavin", "vitamin"),
    _n("pyridoxine", C, 26, "Piridoxina", "(mg)", "Piridoxina", "Pyridoxine", "vitamin"),
    _n("niacin", C, 27, "Niacina", "(mg)", "Niacina", "Niacin", "vitamin"),
    _n("vitamin_c", C, 28, "C", "(mg)", "Vitamina C", "Vitamin C", "vitamin"),
    _n("sfa", F, 2, "turados", "(g)", "Ácidos graxos saturados", "Saturated fatty acids", "fatty_acid"),
    _n("mufa", F, 3, "insaturados", "(g)", "Ácidos graxos monoinsaturados",
       "Monounsaturated fatty acids", "fatty_acid"),
    _n("pufa", F, 4, "insaturados", "(g)", "Ácidos graxos poli-insaturados",
       "Polyunsaturated fatty acids", "fatty_acid"),
    _n("fa_12_0", F, 5, "12:0", "(g)", "Ácido graxo 12:0", "Fatty acid 12:0", "fatty_acid"),
    _n("fa_14_0", F, 6, "14:0", "(g)", "Ácido graxo 14:0", "Fatty acid 14:0", "fatty_acid"),
    _n("fa_16_0", F, 7, "16:0", "(g)", "Ácido graxo 16:0", "Fatty acid 16:0", "fatty_acid"),
    _n("fa_18_0", F, 8, "18:0", "(g)", "Ácido graxo 18:0", "Fatty acid 18:0", "fatty_acid"),
    _n("fa_20_0", F, 9, "20:0", "(g)", "Ácido graxo 20:0", "Fatty acid 20:0", "fatty_acid"),
    _n("fa_22_0", F, 10, "22:0", "(g)", "Ácido graxo 22:0", "Fatty acid 22:0", "fatty_acid"),
    _n("fa_24_0", F, 11, "24:0", "(g)", "Ácido graxo 24:0", "Fatty acid 24:0", "fatty_acid"),
    _n("fa_14_1", F, 13, "14:1", "(g)", "Ácido graxo 14:1", "Fatty acid 14:1", "fatty_acid"),
    _n("fa_16_1", F, 14, "16:1", "(g)", "Ácido graxo 16:1", "Fatty acid 16:1", "fatty_acid"),
    _n("fa_18_1", F, 15, "18:1", "(g)", "Ácido graxo 18:1", "Fatty acid 18:1", "fatty_acid"),
    _n("fa_20_1", F, 16, "20:1", "(g)", "Ácido graxo 20:1", "Fatty acid 20:1", "fatty_acid"),
    _n("fa_18_2_n6", F, 17, "18:2 n-6", "(g)", "Ácido graxo 18:2 n-6", "Fatty acid 18:2 n-6", "fatty_acid"),
    _n("fa_18_3_n3", F, 18, "18:3 n-3", "(g)", "Ácido graxo 18:3 n-3", "Fatty acid 18:3 n-3", "fatty_acid"),
    _n("fa_20_4", F, 19, "20:4", "(g)", "Ácido graxo 20:4", "Fatty acid 20:4", "fatty_acid"),
    _n("fa_20_5", F, 20, "20:5", "(g)", "Ácido graxo 20:5", "Fatty acid 20:5", "fatty_acid"),
    _n("fa_22_5", F, 21, "22:5", "(g)", "Ácido graxo 22:5", "Fatty acid 22:5", "fatty_acid"),
    _n("fa_22_6", F, 22, "22:6", "(g)", "Ácido graxo 22:6", "Fatty acid 22:6", "fatty_acid"),
    _n("fa_18_1t", F, 23, "18:1t", "(g)", "Ácido graxo 18:1 trans", "Fatty acid 18:1 trans", "fatty_acid"),
    _n("fa_18_2t", F, 24, "18:2t", "(g)", "Ácido graxo 18:2 trans", "Fatty acid 18:2 trans", "fatty_acid"),
    _n("tryptophan", A, 2, "Triptofano", "(g)", "Triptofano", "Tryptophan", "amino_acid"),
    _n("threonine", A, 3, "Treonina", "(g)", "Treonina", "Threonine", "amino_acid"),
    _n("isoleucine", A, 4, "Isoleucina", "(g)", "Isoleucina", "Isoleucine", "amino_acid"),
    _n("leucine", A, 5, "Leucina", "(g)", "Leucina", "Leucine", "amino_acid"),
    _n("lysine", A, 6, "Lisina", "(g)", "Lisina", "Lysine", "amino_acid"),
    _n("methionine", A, 7, "Metionina", "(g)", "Metionina", "Methionine", "amino_acid"),
    _n("cystine", A, 8, "Cistina", "(g)", "Cistina", "Cystine", "amino_acid"),
    _n("phenylalanine", A, 9, "Fenilalanina", "(g)", "Fenilalanina", "Phenylalanine", "amino_acid"),
    _n("tyrosine", A, 10, "Tirosina", "(g)", "Tirosina", "Tyrosine", "amino_acid"),
    _n("valine", A, 12, "Valina", "(g)", "Valina", "Valine", "amino_acid"),
    _n("arginine", A, 13, "Arginina", "(g)", "Arginina", "Arginine", "amino_acid"),
    _n("histidine", A, 14, "Histidina", "(g)", "Histidina", "Histidine", "amino_acid"),
    _n("alanine", A, 15, "Alanina", "(g)", "Alanina", "Alanine", "amino_acid"),
    _n("aspartic_acid", A, 16, "Aspártico", "(g)", "Ácido aspártico", "Aspartic acid", "amino_acid"),
    _n("glutamic_acid", A, 17, "Glutâmico", "(g)", "Ácido glutâmico", "Glutamic acid", "amino_acid"),
    _n("glycine", A, 18, "Glicina", "(g)", "Glicina", "Glycine", "amino_acid"),
    _n("proline", A, 19, "Prolina", "(g)", "Prolina", "Proline", "amino_acid"),
    _n("serine", A, 20, "Serina", "(g)", "Serina", "Serine", "amino_acid"),
)

ALCOHOL = Nutrient(
    key="alcohol",
    sheet=-1,
    col=-1,
    header="",
    unit_header="(g)",
    label_pt="Teor alcoólico",
    label_en="Alcohol content",
    category="proximate",
)

BY_KEY: dict[str, Nutrient] = {n.key: n for n in (*NUTRIENTS, ALCOHOL)}
