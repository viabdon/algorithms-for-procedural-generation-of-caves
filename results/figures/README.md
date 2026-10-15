# Figuras e arquivos de inspeção

Os artefatos ficam agrupados pela etapa do experimento, independentemente de
serem HTML, PNG ou PLY:

| Pasta | Conteúdo |
| --- | --- |
| `01_nuvem_e_recortes/` | Recortes da nuvem exportados para inspeção |
| `02_reconstrucao_poisson/` | Inspeções de uma reconstrução Poisson específica |
| `03_linha_central/` | Contração LBC, grafos, cortes e vistas da linha central |
| `04_orientacao_normais/` | Revisões das normais com a linha central |
| `05_comparacao_malhas/` | Visualizações que comparam candidatas e filtros |
| `06_geracao_procedural/` | Visualizações de volumes produzidos pelos geradores |

Os arquivos gerados são locais e ignorados pelo Git. Os scripts de plotagem
usam essas pastas como destino padrão; `--output` permite escolher outro local.
