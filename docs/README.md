# Documentação do TCC

## Tarefas e planejamento

- [Roadmap](tarefas/roadmap.md)
- [Tarefas de Pablo](tarefas/tarefas-pablo-reconstrucao-modelos.md)
- [Tarefas de Felipe](tarefas/tarefas-felipe-sdf-ca.md)

## Resumos teóricos

- [Fundamentos de normais, octrees e Screened Poisson](resumos-teoricos/fundamentos-screened-poisson.md)
- [Linha central de Racine e adaptação no Elaphes](resumos-teoricos/linha-central-racine.md)

## Explicações metodológicas

- [Amostragem, normais e reconstrução do Elaphes](metodologia/amostragem-normais-screened-poisson.md)
- [Arquitetura do pipeline](metodologia/architecture.md)
- [Ajustes de metodologia](metodologia/methodology-adjustments.md)
- [Extração exploratória de linha central no Elaphes](metodologia/linha-central-elaphes-exploracao.md)
- [Orientação experimental das normais por trechos e revisão dos índices incertos](metodologia/orientacao-normais-linha-central.md)
- [Dilatação morfológica da nuvem densa do Elaphes e avaliação para SDF](metodologia/espessamento-morfologico-elaphes.md)
- [Poisson e espessamento leve na extensão completa do Elaphes](metodologia/poisson-elaphes-extensao-completa.md)
- [Inventário de metadados e posições do scanner do Elaphes](metodologia/metadados-elaphes-scanner.md)

O [plano geral](../Orientacao-codex.md) reúne as dependências entre as frentes.
Os resumos explicam conceitos e fontes; os documentos metodológicos descrevem
as decisões e o estado do código deste projeto.

Para regenerar os HTMLs 3D da nuvem, linha central e malhas candidatas, usar
`uv run python plots/plot_elaphes.py line` ou `uv run python plots/plot_elaphes.py mesh`
na raiz do repositório. O comando aceita `--cloud`, `--graph`, `--mesh NOME=OBJ`,
`--output`, `--max-points`, `--seed` e `--show`; ver `--help` em cada subcomando.
`--orientation`, `--highlight-uncertain` e `--show-normals` acrescentam os
índices incertos e as setas da revisão ao HTML.
