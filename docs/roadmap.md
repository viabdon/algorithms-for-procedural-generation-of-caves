# Roadmap atualizado

## Fase 0 — Esqueleto do repositório

Criar pacote Python, diretórios, configurações, README, arquivos de dependência e convenções de volume.

## Pré-processamento de referências reais

### TODO — Calcular limites espaciais incrementais de nuvens de pontos

**Estado:** os parsers ``.f32`` e ``.ply`` fornecem lotes XYZ ``float32`` de
forma ``(n_no_lote, 3)`` por ``cavegen.io.f32.iter_f32_xyz`` e
``cavegen.io.ply.iter_ply_xyz``, respectivamente. O leitor PLY suporta payload
ASCII por streaming e payload binário por ``numpy.memmap``.

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

**Contrato proposto:** uma função genérica, fora dos parsers de formato, deve
receber um iterável de lotes XYZ e retornar ``(min_xyz, max_xyz)`` como dois
arrays ``float32`` de forma ``(3,)``.

**Validações:** rejeitar iterável sem pontos, lotes fora da forma ``(N, 3)`` e
coordenadas ``NaN`` ou infinitas. Eixos degenerados (``min == max``) devem ser
preservados nesta etapa e tratados explicitamente apenas durante a
normalização.

**Verificação:** testar ao menos dois lotes, com número total de pontos que
não seja múltiplo do tamanho do lote, e conferir os seis extremos esperados.

**Próximo pré-requisito ativo:** inspecionar o cabeçalho de um PLY real do
Elaphes e confirmar que seu layout está dentro das restrições suportadas pelo
parser. Em seguida, implementar esta tarefa de limites de forma independente
do formato de origem.

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
