# Tarefas de Pablo — redes neurais e protocolo compartilhado

Atualizado em 06/11/2026. Pablo inicia GAN, PCGRL e PCGARL em paralelo ao
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
- [ ] Auditar conjuntos de treino da GAN e separação por caverna/grafo, além de
  origem, semântica, licença, resolução, hardware e memória disponível.
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
  parser. A leitura de point clouds deve continuar incremental e em `float32`.
- [ ] Atualizar o texto do TCC para refletir o rollback: documentos externos,
  inclusive os intitulados atualizados, não representam o escopo vigente.

O benchmark/menu da revisão `a7dd1e7` ainda não importam por incompatibilidade
da API do CA; Felipe conduz essa integração, que não bloqueia o desenho neural.
