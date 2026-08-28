# Roadmap atualizado

## Fase 0 — Esqueleto do repositório

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

**Pendente no dataset real:** executar a função sobre o iterador PLY completo
quando o HD do Elaphes estiver montado e preservar os dois limites resultantes
nos metadados da referência. Essa execução é necessária antes de voxelizar os
pontos reais.

### TODO — Normalizar lotes XYZ para uma grade de voxels

**Objetivo:** converter coordenadas contínuas, usando os limites globais já
calculados, para índices inteiros válidos de uma grade com forma
``(depth, height, width)``.

**Contrato proposto:** uma função de normalização deve receber um lote XYZ
``float32``, ``min_xyz``, ``max_xyz`` e a resolução da grade; deve devolver um
array inteiro de forma ``(N, 3)``. O mapeamento de eixos precisa ser explícito:
XYZ representa coordenadas geométricas, enquanto o volume padrão usa a ordem
``(depth, height, width)``.

**Decisão necessária:** preservar a proporção espacial usando a maior extensão
da caixa (recomendado para não deformar a caverna) ou escalar cada eixo de
forma independente para preencher toda a grade. A decisão escolhida deve ser
registrada nos metadados.

**Casos de borda:** coordenadas no máximo global devem resultar no último
índice válido, eixos degenerados requerem uma regra explícita e nenhum índice
pode escapar da grade. A normalização não deve reter todos os pontos na
memória.

**Verificação:** usar uma caixa sintética pequena com extremos conhecidos e
confirmar os índices mapeados, a preservação dos limites da grade e o
tratamento de eixos degenerados.

**Depois da normalização:** ``cavegen.core.voxelization`` poderá marcar cada
índice normalizado em ``surface_voxels``. Essa operação continuará incremental,
mas requer uma segunda varredura do arquivo porque os limites só são conhecidos
após a primeira.

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
