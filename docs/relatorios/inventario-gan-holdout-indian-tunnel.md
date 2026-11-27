# Inventário do fold holdout_indian_tunnel para a GAN piloto

Este inventário preserva a configuração anterior ao fold ativo. Os links para o antigo manifesto, a auditoria e os recibos dependem do acervo local. [Fold ativo `holdout_carste`](inventario-gan-holdout-carste.md)

O fold reúne **38 recortes de quatro cavernas**, todos com voxels de **16 cm**. A GAN recebe máscaras de ar em **64³**. São 36 grades nativas e duas janelas derivadas que preservam cada voxel de ar. Os oito recortes auditados que excederam a janela ou sua margem ficaram fora do fold. O inventário registra as referências candidatas congeladas no manifesto `32b90e9ea313`, com status `gallery_proxy_pending_review`. [Manifesto](../../data/processed/experiments/gan_piloto_16cm_indian_tunnel/splits.json) · [Auditoria](../../data/processed/experiments/gan_piloto_16cm_indian_tunnel/reference_audit.json)

| Partição | Caverna | Levantamento | Recortes |
| --- | --- | --- | ---: |
| Treino | Archamps | PostEtroiture | 5 |
| Treino | Archamps | PreEtroiture | 7 |
| Treino | Cascade de Môtiers | MainGallery | 17 |
| Validação | Markov Spodmol | MainGallery | 8 |
| Teste | Indian Tunnel | Full | 1 |
| **Total** | | | **38** |

## Recorte por recorte

A posição em metros é medida ao longo do ramo daquele plano. A fração de ar usa as **262.144 células da máscara que a GAN recebe**. Reparo e tampa auxiliar contam células acrescentadas em máscaras próprias, além das duas tampas de extremidade. No total, 5 recortes têm reparo local e 26 usam tampa auxiliar sintética. O link do plano abre o recibo da execução com parâmetros, semente, origem da grade e caminhos dos artefatos.

| Partição | Caverna / levantamento | Recorte | Estações (m) | Grade original ZYX | Voxels de ar | Ar | Reparo local | Tampa auxiliar | Plano e recibo |
| --- | --- | --- | ---: | --- | ---: | ---: | ---: | ---: | --- |
| Treino | Archamps / PostEtroiture | `ramo_001_002` | 9,24–17,03 | 64³ | 9.893 | 3,77% | 2 | 0 | [`piloto_2mm_6_trechos_revisao_tampas`](../../data/processed/reference_sections/archamps/PostEtroiture/holdout_indian_tunnel/piloto_2mm_6_trechos_revisao_tampas/ramo_001_002/64x64x64/run.json) |
| Treino | Archamps / PostEtroiture | `ramo_001_003` | 17,03–25,47 | 64³ | 7.490 | 2,86% | 2 | 0 | [`piloto_2mm_6_trechos_revisao_tampas`](../../data/processed/reference_sections/archamps/PostEtroiture/holdout_indian_tunnel/piloto_2mm_6_trechos_revisao_tampas/ramo_001_003/64x64x64/run.json) |
| Treino | Archamps / PostEtroiture | `ramo_001_004` | 25,47–33,90 | 64³ | 8.139 | 3,10% | 0 | 0 | [`piloto_2mm_6_trechos_revisao_tampas`](../../data/processed/reference_sections/archamps/PostEtroiture/holdout_indian_tunnel/piloto_2mm_6_trechos_revisao_tampas/ramo_001_004/64x64x64/run.json) |
| Treino | Archamps / PostEtroiture | `ramo_001_005` | 33,90–43,62 | 64×64×68 † | 12.455 | 4,75% | 0 | 69 | [`piloto_2mm_6_trechos_revisao_tampas`](../../data/processed/reference_sections/archamps/PostEtroiture/holdout_indian_tunnel/piloto_2mm_6_trechos_revisao_tampas/ramo_001_005/64x64x68/run.json) |
| Treino | Archamps / PostEtroiture | `ramo_001_006` | 43,62–50,62 | 64³ | 8.022 | 3,06% | 0 | 46 | [`piloto_2mm_6_trechos_revisao_tampas`](../../data/processed/reference_sections/archamps/PostEtroiture/holdout_indian_tunnel/piloto_2mm_6_trechos_revisao_tampas/ramo_001_006/64x64x64/run.json) |
| Treino | Archamps / PreEtroiture | `ramo_001_004` | 26,77–35,32 | 64³ | 7.961 | 3,04% | 0 | 21 | [`ramos_cortes_16cm`](../../data/processed/reference_sections/archamps/PreEtroiture/holdout_indian_tunnel/ramos_cortes_16cm/ramo_001_004/64x64x64/run.json) |
| Treino | Archamps / PreEtroiture | `ramo_001_005` | 35,32–44,03 | 64³ | 8.223 | 3,14% | 0 | 24 | [`pre_5cm_16cm`](../../data/processed/reference_sections/archamps/PreEtroiture/holdout_indian_tunnel/pre_5cm_16cm/ramo_001_005/64x64x64/run.json) |
| Treino | Archamps / PreEtroiture | `ramo_001_007` | 52,74–61,45 | 64³ | 7.344 | 2,80% | 0 | 53 | [`ramos_cortes_16cm`](../../data/processed/reference_sections/archamps/PreEtroiture/holdout_indian_tunnel/ramos_cortes_16cm/ramo_001_007/64x64x64/run.json) |
| Treino | Archamps / PreEtroiture | `ramo_001_008` | 61,45–70,32 | 64³ | 7.499 | 2,86% | 0 | 19 | [`auto_sementes_originais_16cm`](../../data/processed/reference_sections/archamps/PreEtroiture/holdout_indian_tunnel/auto_sementes_originais_16cm/ramo_001_008/64x64x64/run.json) |
| Treino | Archamps / PreEtroiture | `ramo_001_009` | 70,32–78,87 | 64³ | 8.136 | 3,10% | 3 | 0 | [`ramos_cortes_16cm`](../../data/processed/reference_sections/archamps/PreEtroiture/holdout_indian_tunnel/ramos_cortes_16cm/ramo_001_009/64x64x64/run.json) |
| Treino | Archamps / PreEtroiture | `ramo_002_007` | 48,92–57,00 | 64×64×70 † | 13.796 | 5,26% | 0 | 13 | [`pre_5cm_16cm`](../../data/processed/reference_sections/archamps/PreEtroiture/holdout_indian_tunnel/pre_5cm_16cm/ramo_002_007/64x64x70/run.json) |
| Treino | Archamps / PreEtroiture | `ramo_004_001` | 0,16–4,67 | 64³ | 4.331 | 1,65% | 0 | 0 | [`pre_5cm_16cm`](../../data/processed/reference_sections/archamps/PreEtroiture/holdout_indian_tunnel/pre_5cm_16cm/ramo_004_001/64x64x64/run.json) |
| Treino | Cascade de Môtiers / MainGallery | `ramo_002_003` | 14,37–21,31 | 64³ | 9.952 | 3,80% | 0 | 170 | [`las5cm_16cm_rev`](../../data/processed/reference_sections/cascadedemotiers/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_002_003/64x64x64/run.json) |
| Treino | Cascade de Môtiers / MainGallery | `ramo_015_002` | 7,58–14,67 | 64³ | 10.193 | 3,89% | 0 | 13 | [`las5cm_16cm_rev`](../../data/processed/reference_sections/cascadedemotiers/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_015_002/64x64x64/run.json) |
| Treino | Cascade de Môtiers / MainGallery | `ramo_015_003` | 14,67–21,77 | 64³ | 3.349 | 1,28% | 0 | 112 | [`las5cm_16cm_rev`](../../data/processed/reference_sections/cascadedemotiers/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_015_003/64x64x64/run.json) |
| Treino | Cascade de Môtiers / MainGallery | `ramo_016_002` | 6,44–12,24 | 64³ | 6.052 | 2,31% | 0 | 0 | [`contornos_16cm`](../../data/processed/reference_sections/cascadedemotiers/MainGallery/holdout_indian_tunnel/contornos_16cm/ramo_016_002/64x64x64/run.json) |
| Treino | Cascade de Môtiers / MainGallery | `ramo_018_003` | 13,72–20,34 | 64³ | 11.329 | 4,32% | 0 | 190 | [`las5cm_16cm_rev`](../../data/processed/reference_sections/cascadedemotiers/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_018_003/64x64x64/run.json) |
| Treino | Cascade de Môtiers / MainGallery | `ramo_027_002` | 7,30–13,79 | 64³ | 4.104 | 1,57% | 4 | 0 | [`contornos_16cm`](../../data/processed/reference_sections/cascadedemotiers/MainGallery/holdout_indian_tunnel/contornos_16cm/ramo_027_002/64x64x64/run.json) |
| Treino | Cascade de Môtiers / MainGallery | `ramo_035_002` | 8,32–16,16 | 64³ | 15.117 | 5,77% | 0 | 4 | [`las5cm_16cm_rev`](../../data/processed/reference_sections/cascadedemotiers/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_035_002/64x64x64/run.json) |
| Treino | Cascade de Môtiers / MainGallery | `ramo_035_003` | 16,16–24,00 | 64³ | 14.510 | 5,54% | 0 | 9 | [`las5cm_16cm_rev`](../../data/processed/reference_sections/cascadedemotiers/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_035_003/64x64x64/run.json) |
| Treino | Cascade de Môtiers / MainGallery | `ramo_035_004` | 24,00–31,84 | 64³ | 15.140 | 5,78% | 0 | 12 | [`las5cm_16cm_rev`](../../data/processed/reference_sections/cascadedemotiers/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_035_004/64x64x64/run.json) |
| Treino | Cascade de Môtiers / MainGallery | `ramo_035_005` | 31,84–39,68 | 64³ | 15.904 | 6,07% | 0 | 19 | [`las5cm_16cm_rev`](../../data/processed/reference_sections/cascadedemotiers/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_035_005/64x64x64/run.json) |
| Treino | Cascade de Môtiers / MainGallery | `ramo_035_006` | 39,68–47,52 | 64³ | 16.085 | 6,14% | 0 | 17 | [`las5cm_16cm_rev`](../../data/processed/reference_sections/cascadedemotiers/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_035_006/64x64x64/run.json) |
| Treino | Cascade de Môtiers / MainGallery | `ramo_035_007` | 47,52–55,36 | 64³ | 19.047 | 7,27% | 0 | 34 | [`las5cm_16cm_rev`](../../data/processed/reference_sections/cascadedemotiers/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_035_007/64x64x64/run.json) |
| Treino | Cascade de Môtiers / MainGallery | `ramo_035_009` | 63,21–68,65 | 64³ | 14.304 | 5,46% | 0 | 0 | [`paredes_medidas_16cm`](../../data/processed/reference_sections/cascadedemotiers/MainGallery/holdout_indian_tunnel/paredes_medidas_16cm/ramo_035_009/64x64x64/run.json) |
| Treino | Cascade de Môtiers / MainGallery | `ramo_038_002` | 8,82–17,17 | 64³ | 3.488 | 1,33% | 1 | 0 | [`las5cm_16cm_rev`](../../data/processed/reference_sections/cascadedemotiers/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_038_002/64x64x64/run.json) |
| Treino | Cascade de Môtiers / MainGallery | `ramo_038_003` | 17,17–26,15 | 64³ | 4.477 | 1,71% | 0 | 53 | [`las5cm_16cm_rev`](../../data/processed/reference_sections/cascadedemotiers/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_038_003/64x64x64/run.json) |
| Treino | Cascade de Môtiers / MainGallery | `ramo_038_004` | 26,15–33,86 | 64³ | 4.490 | 1,71% | 0 | 17 | [`las5cm_16cm_rev`](../../data/processed/reference_sections/cascadedemotiers/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_038_004/64x64x64/run.json) |
| Treino | Cascade de Môtiers / MainGallery | `ramo_038_005` | 33,86–42,20 | 64³ | 2.495 | 0,95% | 0 | 76 | [`las5cm_16cm_rev`](../../data/processed/reference_sections/cascadedemotiers/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_038_005/64x64x64/run.json) |
| Validação | Markov Spodmol / MainGallery | `ramo_011_003` | 12,29–18,19 | 64³ | 6.475 | 2,47% | 0 | 37 | [`las5cm_16cm_rev`](../../data/processed/reference_sections/markovspodmol/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_011_003/64x64x64/run.json) |
| Validação | Markov Spodmol / MainGallery | `ramo_011_004` | 18,19–24,09 | 64³ | 5.798 | 2,21% | 0 | 0 | [`las5cm_16cm_rev`](../../data/processed/reference_sections/markovspodmol/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_011_004/64x64x64/run.json) |
| Validação | Markov Spodmol / MainGallery | `ramo_011_005` | 24,09–29,99 | 64³ | 4.142 | 1,58% | 0 | 35 | [`las5cm_16cm_rev`](../../data/processed/reference_sections/markovspodmol/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_011_005/64x64x64/run.json) |
| Validação | Markov Spodmol / MainGallery | `ramo_017_003` | 14,56–21,60 | 64³ | 17.294 | 6,60% | 0 | 0 | [`las5cm_16cm_rev`](../../data/processed/reference_sections/markovspodmol/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_017_003/64x64x64/run.json) |
| Validação | Markov Spodmol / MainGallery | `ramo_017_004` | 21,60–28,64 | 64³ | 14.962 | 5,71% | 0 | 12 | [`las5cm_16cm_rev`](../../data/processed/reference_sections/markovspodmol/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_017_004/64x64x64/run.json) |
| Validação | Markov Spodmol / MainGallery | `ramo_017_005` | 28,64–35,68 | 64³ | 22.094 | 8,43% | 0 | 83 | [`las5cm_16cm_rev`](../../data/processed/reference_sections/markovspodmol/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_017_005/64x64x64/run.json) |
| Validação | Markov Spodmol / MainGallery | `ramo_017_010` | 63,84–70,88 | 64³ | 14.459 | 5,52% | 0 | 0 | [`las5cm_16cm_rev`](../../data/processed/reference_sections/markovspodmol/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_017_010/64x64x64/run.json) |
| Validação | Markov Spodmol / MainGallery | `ramo_017_014` | 92,00–99,04 | 64³ | 16.018 | 6,11% | 0 | 2 | [`las5cm_16cm_rev`](../../data/processed/reference_sections/markovspodmol/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_017_014/64x64x64/run.json) |
| Teste | Indian Tunnel / Full | `ramo_002_001` | 33,12–34,40 | 64³ | 20.433 | 7,79% | 0 | 46 | [`perfis_rotacao_16cm`](../../data/processed/reference_sections/indian_tunnel/Full/holdout_indian_tunnel/perfis_rotacao_16cm/ramo_002_001/64x64x64/run.json) |

† Janelas derivadas a 16 cm, com limites de origem em índices ZYX e fim exclusivo.

- **Archamps / PostEtroiture `ramo_001_005`** usa a janela `[0:64, 0:64, 2:66]` na grade 64×64×68. Preserva 12.455 voxels de ar.
- **Archamps / PreEtroiture `ramo_002_007`** usa a janela `[0:64, 0:64, 3:67]` na grade 64×64×70. Preserva 13.796 voxels de ar.
- **Archamps / PreEtroiture `ramo_001_008`** teve a semente deslocada em 20,1 cm. **Cascade de Môtiers `ramo_035_009`** recebeu 235 pontos medidos da nuvem original, rasterizados em 35 células de parede. Essa recuperação faz parte da superfície do recorte e aparece com zero nas colunas de reparo local e tampa auxiliar.
- **Indian Tunnel `ramo_002_001`** vem do plano `perfis_rotacao_16cm`. O teste representa um trecho de 1,28 m de um tubo de lava. Elaphes, Madeleine e Rupt du Puits estão em auditorias externas separadas. [Histórico de voxelização](../auditoria/gan/historico-voxelizacao.md)

Para documentar evoluções da GAN, registre o identificador do manifesto, a configuração, a semente de treino e o passo de cada checkpoint. Nas visualizações de checkpoints diferentes, mantenha a mesma lista de sementes latentes e o mesmo limiar de ocupação. Assim, a comparação mostra como mudou a geração para cada entrada. [Plano de treino e avaliação](../plano-redes-neurais.md)
