# Inventário do fold holdout_carste para a GAN piloto

O fold ativo tem **52 recortes de seis cavernas cársticas**, em voxels de **16 cm**. O treino e a validação conservam os mesmos 37 recortes do piloto anterior. O teste reúne 15 recortes de três cavernas reservadas. O manifesto é `ce425f62ff3f`, com status `gallery_proxy_pending_review`. [Manifesto](../auditoria/gan/holdout_carste/splits.json) · [Auditoria](../auditoria/gan/holdout_carste/reference_audit.json)

| Partição | Caverna | Levantamento | Recortes |
| --- | --- | --- | ---: |
| Treino | Archamps | PostEtroiture | 5 |
| Treino | Archamps | PreEtroiture | 7 |
| Treino | Cascade de Môtiers | MainGallery | 17 |
| Validação | Markov Spodmol | MainGallery | 8 |
| Teste | Madeleine | Filleul | 4 |
| Teste | Rupt du Puits | Cascades | 3 |
| Teste | Vallorbe | GalerieSemiActive | 8 |
| **Total** | | | **52** |

Quando duas densidades da mesma galeria passaram para o mesmo recorte, foi escolhida a versão com menos células de tampa auxiliar. As versões concorrentes ficam identificadas no registro de seleção. Os três conjuntos de teste estão sujeitos à revisão geométrica, especialmente os trechos com maior intervenção. [Seleção das versões](../auditoria/gan/holdout_carste/selecao_teste.json) · [Histórico das voxelizações](../auditoria/gan/historico-voxelizacao.md)

## Recorte por recorte

As estações são distâncias ao longo do ramo no plano informado. A fração de ar usa as 262.144 células da máscara de entrada da GAN. As colunas de intervenção contam células extras às duas tampas de extremidade. Os links por plano abrem os recibos quando os artefatos da voxelização estão disponíveis no checkout local.

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
| Teste | Madeleine / Filleul | `ramo_001_002` | 7,13–14,10 | 64³ | 6.316 | 2,41% | 0 | 106 | [`las2mm_16cm`](../../data/processed/experiments/madeleine_rupt_16cm/madeleine/las2mm_16cm/data/processed/reference_sections/madeleine/Filleul/teste_externo/las2mm_16cm/ramo_001_002/64x64x64/run.json) |
| Teste | Madeleine / Filleul | `ramo_001_006` | 35,01–42,15 | 64³ | 3.791 | 1,45% | 0 | 1.059 | [`las5cm_16cm`](../../data/processed/experiments/madeleine_rupt_16cm/madeleine/las5cm_16cm/data/processed/reference_sections/madeleine/Filleul/teste_externo/las5cm_16cm/ramo_001_006/64x64x64/run.json) |
| Teste | Madeleine / Filleul | `ramo_002_001` | 1,36–5,83 | 64³ | 7.302 | 2,79% | 0 | 270 | [`las2mm_16cm`](../../data/processed/experiments/madeleine_rupt_16cm/madeleine/las2mm_16cm/data/processed/reference_sections/madeleine/Filleul/teste_externo/las2mm_16cm/ramo_002_001/64x64x64/run.json) |
| Teste | Madeleine / Filleul | `ramo_002_003` | 10,54–17,17 | 64³ | 14.528 | 5,54% | 0 | 415 | [`las5cm_16cm`](../../data/processed/experiments/madeleine_rupt_16cm/madeleine/las5cm_16cm/data/processed/reference_sections/madeleine/Filleul/teste_externo/las5cm_16cm/ramo_002_003/64x64x64/run.json) |
| Teste | Rupt du Puits / Cascades | `ramo_001_001` | 0,16–6,64 | 64³ | 25.987 | 9,91% | 0 | 6 | [`las5cm_16cm`](../../data/processed/experiments/madeleine_rupt_16cm/rupt_du_puits/las5cm_16cm/data/processed/reference_sections/rupt_du_puits/Cascades/teste_externo/las5cm_16cm/ramo_001_001/64x64x64/run.json) |
| Teste | Rupt du Puits / Cascades | `ramo_001_002` | 6,64–12,95 | 64³ | 24.758 | 9,44% | 0 | 25 | [`las2mm_16cm`](../../data/processed/experiments/madeleine_rupt_16cm/rupt_du_puits/las2mm_16cm/data/processed/reference_sections/rupt_du_puits/Cascades/teste_externo/las2mm_16cm/ramo_001_002/64x64x64/run.json) |
| Teste | Rupt du Puits / Cascades | `ramo_001_003` | 12,95–19,59 | 64³ | 27.305 | 10,42% | 0 | 316 | [`las2mm_16cm`](../../data/processed/experiments/madeleine_rupt_16cm/rupt_du_puits/las2mm_16cm/data/processed/reference_sections/rupt_du_puits/Cascades/teste_externo/las2mm_16cm/ramo_001_003/64x64x64/run.json) |
| Teste | Vallorbe / GalerieSemiActive | `ramo_001_003` | 13,60–20,15 | 64³ | 28.927 | 11,03% | 0 | 35 | [`las5cm_16cm`](../../data/processed/experiments/vallorbe_16cm/vallorbe/las5cm_16cm/data/processed/reference_sections/vallorbe/GalerieSemiActive/teste_externo/las5cm_16cm/ramo_001_003/64x64x64/run.json) |
| Teste | Vallorbe / GalerieSemiActive | `ramo_001_004` | 20,15–26,71 | 64³ | 36.248 | 13,83% | 0 | 11 | [`las5cm_16cm`](../../data/processed/experiments/vallorbe_16cm/vallorbe/las5cm_16cm/data/processed/reference_sections/vallorbe/GalerieSemiActive/teste_externo/las5cm_16cm/ramo_001_004/64x64x64/run.json) |
| Teste | Vallorbe / GalerieSemiActive | `ramo_001_005` | 26,71–33,27 | 64³ | 39.293 | 14,99% | 0 | 55 | [`las5cm_16cm`](../../data/processed/experiments/vallorbe_16cm/vallorbe/las5cm_16cm/data/processed/reference_sections/vallorbe/GalerieSemiActive/teste_externo/las5cm_16cm/ramo_001_005/64x64x64/run.json) |
| Teste | Vallorbe / GalerieSemiActive | `ramo_001_006` | 33,27–39,83 | 64×66×64 † | 45.883 | 17,50% | 0 | 30 | [`las5cm_16cm`](../../data/processed/experiments/vallorbe_16cm/vallorbe/las5cm_16cm/data/processed/reference_sections/vallorbe/GalerieSemiActive/teste_externo/las5cm_16cm/ramo_001_006/64x66x64/run.json) |
| Teste | Vallorbe / GalerieSemiActive | `ramo_002_004` | 19,93–26,42 | 64³ | 37.167 | 14,18% | 0 | 4 | [`las5cm_16cm`](../../data/processed/experiments/vallorbe_16cm/vallorbe/las5cm_16cm/data/processed/reference_sections/vallorbe/GalerieSemiActive/teste_externo/las5cm_16cm/ramo_002_004/64x64x64/run.json) |
| Teste | Vallorbe / GalerieSemiActive | `ramo_002_007` | 39,39–45,87 | 64×68×66 † | 25.984 | 9,91% | 0 | 20 | [`las5cm_16cm`](../../data/processed/experiments/vallorbe_16cm/vallorbe/las5cm_16cm/data/processed/reference_sections/vallorbe/GalerieSemiActive/teste_externo/las5cm_16cm/ramo_002_007/64x68x66/run.json) |
| Teste | Vallorbe / GalerieSemiActive | `ramo_004_003` | 13,71–20,32 | 64³ | 36.316 | 13,85% | 0 | 8 | [`las5cm_16cm`](../../data/processed/experiments/vallorbe_16cm/vallorbe/las5cm_16cm/data/processed/reference_sections/vallorbe/GalerieSemiActive/teste_externo/las5cm_16cm/ramo_004_003/64x64x64/run.json) |
| Teste | Vallorbe / GalerieSemiActive | `ramo_004_004` | 20,32–26,93 | 64³ | 32.256 | 12,30% | 0 | 0 | [`las5cm_16cm`](../../data/processed/experiments/vallorbe_16cm/vallorbe/las5cm_16cm/data/processed/reference_sections/vallorbe/GalerieSemiActive/teste_externo/las5cm_16cm/ramo_004_004/64x64x64/run.json) |

† Janelas de 64³ derivadas da máscara de ar. Os limites finais são exclusivos.

- **Archamps / PostEtroiture `ramo_001_005`** usa a janela ZYX `[0:64, 0:64, 2:66]` e conserva 12.455 voxels de ar.
- **Archamps / PreEtroiture `ramo_002_007`** usa a janela ZYX `[0:64, 0:64, 3:67]` e conserva 13.796 voxels de ar.
- **Vallorbe / GalerieSemiActive `ramo_001_006`** usa a janela ZYX `[0:64, 1:65, 0:64]` e conserva 45.883 voxels de ar.
- **Vallorbe / GalerieSemiActive `ramo_002_007`** usa a janela ZYX `[0:64, 1:65, 0:64]` e conserva 25.984 voxels de ar.

## Avaliação externa do Indian Tunnel

O `ramo_002_001` de Indian Tunnel, com 20.433 voxels de ar, ficou reservado para avaliar o comportamento da GAN em um tubo de lava, em outro domínio geológico. Comparações com esse volume devem ser relatadas à parte. O inventário externo identifica o arquivo e seus hashes. O manifesto anterior mantém a composição usada antes da troca. [Inventário externo do Indian Tunnel](../auditoria/gan/holdout_carste/avaliacao_externa_indian_tunnel.json) · [Fold anterior](inventario-gan-holdout-indian-tunnel.md)

## Verificação antes do piloto

A partir da raiz do repositório, com PyTorch instalado no ambiente da GAN, o comando abaixo verifica as partições e carrega as máscaras de ocupação para o fold novo.

```bash
PYTHONPATH=src python -m cavegen.training.train_gan \
  --root data/processed \
  --splits docs/auditoria/gan/holdout_carste/splits.json \
  --fold holdout_carste
```

Para comparar checkpoints, fixe as sementes latentes e o limiar de ocupação. Registre o manifesto, a configuração e o passo do checkpoint. [Protocolo neural](../plano-redes-neurais.md)
