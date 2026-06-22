# Roadmap atualizado

## Fase 0 — Esqueleto do repositório

Criar pacote Python, diretórios, configurações, README, arquivos de dependência e convenções de volume.

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
