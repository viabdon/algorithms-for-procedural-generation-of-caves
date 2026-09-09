# Roadmap atualizado

## Fase 0 — Esqueleto do repositório (concluída)

Criar pacote Python, diretórios, configurações, README, arquivos de dependência e convenções de volume.

## Pré-processamento de referências reais

### Concluído — Implementar limites espaciais incrementais de nuvens de pontos

**Estado:** ``calculate_xyz_bounds`` foi implementada em
``cavegen.datastream.bounds`` e testada em ``tests/test_bounds.py``. Os parsers
``.f32`` e ``.ply`` fornecem os lotes XYZ ``float32`` de forma
``(n_no_lote, 3)`` que ela consome. O leitor PLY suporta payload ASCII por
streaming e payload binário por ``numpy.memmap``.

**Objetivo:** calcular a caixa delimitadora alinhada aos eixos da nuvem sem
carregar todos os pontos na memória:

```text
min_xyz = [menor_x, menor_y, menor_z]
max_xyz = [maior_x, maior_y, maior_z]
```

**Estratégia:** para cada lote, calcular mínimo e máximo locais por coluna e
combiná-los com acumuladores globais por ``numpy.minimum`` e
``numpy.maximum``. A implementação deve manter memória adicional constante,
além do lote atual.

**Cobertura dos dados:** para produzir limites usados na normalização e na
voxelização, a função deve consumir todos os vértices do iterador. Uma amostra
não garante conter os extremos reais e pode reduzir indevidamente a caixa,
causando distorção ou recorte de pontos. Amostras servem apenas para
visualização, estimativas exploratórias ou escolha preliminar de parâmetros;
nunca como limites definitivos da referência.

**Contrato proposto:** uma função genérica, fora dos parsers de formato, deve
receber um iterável de lotes XYZ e retornar ``(min_xyz, max_xyz)`` como dois
arrays ``float32`` de forma ``(3,)``.

**Validações:** rejeitar iterável sem pontos, lotes fora da forma ``(N, 3)`` e
coordenadas ``NaN`` ou infinitas. Eixos degenerados (``min == max``) devem ser
preservados nesta etapa e tratados explicitamente apenas durante a
normalização.

**Verificação:** testar ao menos dois lotes, com número total de pontos que
não seja múltiplo do tamanho do lote, e conferir os seis extremos esperados.

**Inspeção concluída — Elaphes:** o arquivo externo
``/run/media/midnavi/Pablo/TCC/DATA/RAW/elaphes_cave.ply`` é PLY ASCII 1.0,
declara ``94_465_067`` vértices, traz ``vertex`` como primeiro elemento e
inclui as propriedades ``float64 x``, ``float64 y`` e ``float64 z``. As 16
propriedades adicionais são escalares e podem ser ignoradas pelo leitor XYZ.
Um lote real de 2.048 pontos foi lido como ``float32`` com coordenadas finitas.

**Concluído no dataset real:** em 2026-08-30, a função foi executada sobre os
``94_465_067`` vértices do PLY ASCII completo, em lotes de ``65_536`` pontos.
Os limites definitivos ``float32`` são:

```text
min_xyz = [-9.9391, -3.23727, -6.96334]
max_xyz = [73.7245, 12.9577, 69.7809]
```

Os metadados reproduzíveis, incluindo hash SHA-256 da fonte, estão em
``data/params/elaphes_xyz_bounds.json``. Esses limites devem ser usados na
normalização e não alteram a semântica dos pontos como superfície.

### Concluído — Normalizar e voxelizar uma referência PLY em lotes

**Estado:** ``normalize_xyz_to_zyx_indices`` em
``cavegen.core.normalization`` converte lotes ``float32`` de coordenadas XYZ
para índices ZYX válidos, com uma escala compartilhada, padding simétrico e
tratamento explícito de eixos degenerados. ``voxelize_surface_zyx`` em
``cavegen.core.voxelization`` marca os índices em uma grade booleana de
superfície. Ambos possuem testes unitários.

**Integração concluída:** ``cavegen.datastream.reference_preprocessing`` lê os
limites persistidos, transmite os lotes de ``iter_ply_xyz`` pela normalização e
os entrega diretamente ao voxelizador por ``voxelize_ply_surface``. O fluxo não
armazena a nuvem inteira: mantém somente o lote corrente, seus índices e a
grade final. Um teste de integração com PLY ASCII sintético verifica o fluxo.

**Decisão adotada:** uma única escala preserva as proporções espaciais; o espaço
remanescente é dividido como padding ao redor da nuvem. A conversão de XYZ para
ZYX torna o resultado compatível com volumes na forma ``(depth, height, width)``.

**Semântica:** ``True`` na grade retornada significa superfície observada, e não
espaço aberto de caverna. Portanto, essa grade ainda não deve ser usada como um
``Volume3D`` dos geradores nem comparada diretamente por IoU a eles.

**Persistência concluída:** ``cavegen.datastream.surface_io`` salva e carrega
grades de superfície em NPZ comprimido, sem usar ``Volume3D``. O arquivo inclui
metadados de fonte, limites XYZ, resolução e convenção de normalização. O
comando de voxelização exige o caminho de saída para não perder a inspeção.

**Verificação concluída — Elaphes em ``32³``:** o processamento completo dos
``94_465_067`` vértices gerou ``elaphes_surface_32.npz`` com grade booleana
``(32, 32, 32)``. Foram marcados 245 dos 32.768 voxels (0,75%). A estrutura do
arquivo e seus metadados de limites, origem e normalização foram validados após
a escrita.

**Próxima verificação:** inspecionar esse resultado e só então repetir em
``64³`` e ``128³``. Depois, definir uma conversão metodologicamente justificável
para ``void_voxels``.

## Fase 1 — Baselines clássicos

Implementar Random Walk 3D e Cellular Automata 3D. Esses algoritmos validam a representação volumétrica, o controle de seeds, a exportação e o cálculo de métricas antes de introduzir o custo dos modelos de IA.

## Fase 2 — Métricas e exportação

Implementar IoU, conectividade, volume ocupado, número de componentes, estatísticas morfológicas simples, exportação `.npz` e exportação `.obj` por Marching Cubes.

## Fase 3 — Visualização offline na Unity

Criar um visualizador simples por importação de arquivos. A Unity não calcula a tabela principal do TCC nessa fase.

## Fase 4 — IA no Colab

Treinar modelos de IA em Colab, começando pequeno:

- GAN 3D simplificada em `32³` ou `64³`.
- PCGRL 3D com ambiente reduzido e recompensas simples.

## Fase 5 — Benchmark principal

Rodar todos os algoritmos com mesmas seeds, dimensões e métricas. Separar treinamento e inferência para modelos de IA.

## Fase 6 — Integração gRPC

Adicionar Python como servidor gRPC e Unity como cliente somente após o pipeline científico estar funcional.

## Fase 7 — Portabilidade AMD/ROCm

Executar amostra menor no ambiente AMD/ROCm, se houver tempo, tratando-a como contribuição técnica complementar.
