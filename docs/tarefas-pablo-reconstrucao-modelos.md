# Tarefas de Pablo — redes neurais e protocolo compartilhado

Atualizado em 17/11/2026. Pablo conduz GAN, PCGRL e PCGARL em paralelo ao
trabalho de Felipe nos clássicos, coleta e tabela. O
[plano neural](plano-redes-neurais.md) detalha contratos, testes, recompensa,
limites, referências e critérios de aceitação. Ver também
[tarefas de Felipe](tarefas-felipe-sdf-ca.md) e [roadmap](roadmap.md).

## Entregas iniciais

- [ ] Ler `metrics/structural.py` e [métricas estruturais](metricas-estruturais.md);
  combinar com Felipe conectividade, ocupação, degeneração, unidade e schema.
- [ ] Especificar e testar MDP pequeno: observações, ações, transições, seed,
  orçamento e distinção entre término e truncamento; validar episódio aleatório.
- [ ] Definir e verificar a recompensa de conectividade e ocupação contra casos
  conhecidos e soluções degeneradas. Separar retorno de métricas independentes.
- [x] Auditar os nove NPZ disponíveis, origem, semântica, licenças e resolução;
  definir folds por caverna. Os quatro interiores não passaram a triagem.
- [x] Preparar a GAN de ocupação/SDF e notebook Colab, com testes em máscaras
  artificiais, checkpoints e avaliação por seeds. Sem treino nas referências.
- [x] Implementar o [piloto de recortes](planejamento-recortes-voxelizacao.md)
  com seleção em lotes, precisão local, seções, tampas, busca por janelas e
  máscara de reparo.
- [ ] Revisar a geometria do 003 reparado e do controle 004 em resoluções
  comparáveis e repetir o diagnóstico em outras galerias. [Resultados do piloto](plano-reconstrucao-secoes.md#evolucao-do-piloto-em-archamps)
- [ ] Acordar o que PCGARL significa no projeto e a referência adversarial; testar
  alcançabilidade e custos do solucionador antes de acoplar os agentes.
- [ ] Implementar provas pequenas e só então treinar, versionar checkpoints,
  produzir `Volume3D` e entregar registros rastreáveis para a tabela de Felipe.
- [ ] Registrar sementes de treino e de avaliação distintas, dados, checkpoints,
  backend, etapas e custos; `64³` é alvo final, não validação já concluída.

## Protocolo e dados

- [ ] Fixar com Felipe critérios, repetições, orçamento e hardware; relatar
  dispersão e falhas. Repetições de tempo não são diversidade geométrica.
- [ ] Não usar superfície do Elaphes como vazio real, IoU volumétrica ou dado
  de treino de ar sem reconstrução e validação adequadas.
- [ ] Inventariar fontes externas e estado das extrações antes de qualquer novo
  parser. Manter leitura incremental; no novo preparo de recortes LAS, remover
  a origem com precisão suficiente antes de converter coordenadas para float32.
- [ ] Separar dados por caverna antes dos recortes, guardar limites/transformações
  e revisar os contornos. Bounds menores no CLI atual não filtram a nuvem.
- [ ] Conferir tampas dentro da grade, contexto dos cortes, resolução física e
  incerteza antes de produzir novas referências ou liberar um ensaio de treino.
- [ ] Atualizar o texto do TCC para refletir o rollback: documentos externos,
  inclusive os intitulados atualizados, não representam o escopo vigente.

O benchmark/menu da revisão `a7dd1e7` ainda não importam por incompatibilidade
da API do CA; Felipe conduz essa integração, que não bloqueia o desenho neural.
