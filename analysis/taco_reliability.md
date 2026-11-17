# Evidence on TACO's reliability

Written on 2026-11-05. This page collects what speaks for and against using TACO next to NEVO. It is
evidence, not proof: nothing here checks TACO's values against an analysis of the same samples. Page
numbers are the printed ones of TACO, 4th edition revised and expanded (NEPA-UNICAMP, 2011),
<https://nepa.unicamp.br/wp-content/uploads/sites/27/2023/10/taco_4_edicao_ampliada_e_revisada.pdf>.

## 1. How TACO was produced, from its own documentation

- **Laboratories.** The analyses were done only by laboratories whose competence was shown in
  interlaboratory studies (p. 7). They were chosen for their satisfactory results in those studies, and also
  for cost, sample transport and capacity (p. 13).
- **Interlaboratory studies.** Appendix 1 (p. 104) describes four collaborative trials, held in 2000, 2002,
  2004 and 2006.
  - They used certified reference materials from NIST and from the European Commission's BCR.
  - A laboratory's mean was scored against the certified value, and a z-score beyond ±3 was "considered
    analytically inadequate for the purposes of the table".
  - Twenty laboratories took part (p. 105). The trial reports are "available on the project's web page or
    on request to the technical team".
- **Sampling** (pp. 10–12; the plan is published in Galeazzi et al., *J Food Comp Anal* 2002, 15(4):499–505):
  - **Industrial products** were bought in 9 cities across Brazil's 5 regions: 3 to 5 leading brands per
    product, and 2 units per brand in each city.
  - **Beef and pork** came from 12 and 20 randomly chosen carcasses, of specified age, sex, fat and weight.
  - **Chicken** was 6 kg per cut from at least 3 brands.
  - **Fruit and vegetables** came from the 5 largest suppliers of the CEASA wholesale market in Campinas.
  - Every food was homogenised at ITAL, and 3 composite samples were sent to the laboratories (p. 12).
- **Methods** (pp. 13–15):
  - AOAC and Instituto Adolfo Lutz methods: oven drying for moisture, Kjeldahl nitrogen with Jones factors
    for protein, Soxhlet for lipids, enzymatic-gravimetric for dietary fibre;
  - ICP-OES for minerals, HPLC for the vitamins, gas chromatography for fatty acids and cholesterol.
- **Carbohydrate** is 100 minus water, protein, lipids, ash and alcohol, and "includes total dietary fibre"
  (p. 13). This is why `scripts/taco_to_nice_food.py` keeps it as total carbohydrate and derives available
  carbohydrate from it.
- **Re-analysis.** In phase V, analytes of phase II without satisfactory results were bought and
  determined again (p. 9).

## 2. What the comparisons in this project show

| Evidence | Result | Source |
| --- | --- | --- |
| Protein of TACO and NEVO foods typed with the same FoodOn class | 83 TACO foods; Spearman 0.94; TACO/NEVO median 0.95, quartiles 0.80 to 1.10 | [triplestore/README.md](../triplestore/README.md) |
| TACO and NEVO pairs whose composition says they are different foods | 20 of 115 pairs flagged for human review; 95 without strong disagreement | [taco_nevo_food_pair_check.md](taco_nevo_food_pair_check.md) |
| TACO against TBCA, the newer Brazilian table (provisional: 3,069 of TBCA's foods, unreviewed FoodOn candidates) | median over 10 nutrients: 73% of values within 20%, Spearman 0.94 | notebook, TBCA section |
| TBCA against NEVO, same conditions | 32% within 20%, Spearman 0.64; TACO against NEVO: 28%, 0.79 | notebook, TBCA section |

**What the TBCA comparison shows.** TBCA differs from NEVO about as much as TACO does. Calcium and sodium are
lower and fibre is higher in both Brazilian tables. The gap between TACO and NEVO therefore looks like a
matter of the foods and the country, not of TACO.

**Limit of that comparison.** 19% of TACO and TBCA values are identical, because TBCA reuses part of TACO.
Their agreement is not independent evidence.

## 3. What speaks against, or is not known

- **Age.** Samples were collected and analysed from 1999 to 2008, in phases II to V (pp. 8–9), and the
  table is from 2011. Varieties, recipes, brands and fortification have changed since.
- **Where the fresh foods come from.** Only industrial products were sampled in all 5 regions. The fresh
  foods each came from one place:
  - fruit, vegetables and chicken from Campinas, the fruit and vegetables from a wholesale market supplied
    by the main producing regions;
  - beef from one slaughterhouse in Lins (SP), pork from one in Rio do Sul (SC).
- **No uncertainty per value.** The table gives one value per food and nutrient, without its uncertainty or
  the number of samples behind it.
- **Not seen.** The trial reports of Appendix 1 have not been seen; they can be asked of the TACO team.
- **Still to be checked.** The 20 flagged pairs still need human review to decide whether TACO, NEVO or the
  FoodOn typing is wrong.
