# Roadmap do TCC

**Atualizado em 06/11/2026.** A `feat/neural-models` incorporou a `main` até
`a7dd1e7`. Felipe se aproxima do fim dos clássicos e passa à coleta de métricas
e consolidação da tabela comparativa; Pablo inicia GAN, PCGRL e PCGARL em
paralelo. As tarefas neurais estão detalhadas no [plano neural](plano-redes-neurais.md).

A decisão de retorno ao pipeline de volumes gerados permanece vigente: não há
interior real validado do Elaphes, logo SDF real e IoU volumétrica contra o
scan estão fora do benchmark. Os documentos externos do projeto de TC,
inclusive os denominados atualizados, antecedem esse rollback. O
[resumo quinzenal](relatorios/resumo-quinzenal-tcc-2026-10-18.docx), a
[arquitetura](architecture.md) e a [metodologia](methodology-adjustments.md)
registram os limites e os experimentos preservados.

## Base integrada e limitações verificadas

- [x] `Volume3D` booleano ZYX (`True = ar`), NPZ e extração de malha para
  visualização; leitores incrementais de PLY/F32 e voxelização diagnóstica da
  superfície. A superfície do scan não representa o ar interior.
- [x] Pacotes de CA com peso espacial e Random Walk ponderado por waypoints,
  testes e ferramentas próprias. A origem dos waypoints condiciona a
  independência do Random Walk; detalhes em [Random Walk](random-walk.md).
- [x] `evaluate_structure`, contrato `structural-v1`, casos degenerados e
  testes de métricas geométricas; ver [métricas estruturais](metricas-estruturais.md).
- [x] Código de registro incremental CSV, configuração inicial `64³` e
  amostragem de recursos; isso não comprova uma coleta final ou integração
  funcional do benchmark. Esquema e protocolo de hardware ainda precisam evoluir.
- [ ] Concluir a integração do CA: em `a7dd1e7`, benchmark e menu importam
  `generate_cellular_automata`, ausente no pacote atual. A suíte local executou
  116 testes com 2 erros de importação e 2 ignorados em 06/11; os módulos de
  testes do menu e dos registros são os afetados. Felipe conduz a correção.
- [ ] Substituir a referência obsoleta do peso 002 do CA ao SDF removido com
  `random_walk_temp/`, se essa extensão voltar ao escopo.
- [ ] Gerar e avaliar GAN, PCGRL e PCGARL: os dois primeiros só têm interfaces
  e rotinas de treino placeholder; o terceiro ainda não foi implementado.

## Frente de Felipe — clássicos, métricas e tabela

- [ ] Finalizar CA e Random Walk, corrigir integração ao benchmark e validar
  importação, teste pequeno de ponta a ponta, NPZ e registro no CSV.
- [ ] Confirmar com Pablo conectividade, spacing, degeneração, métricas comuns,
  resolução `64³`, seeds independentes, repetições, parâmetros e versões antes
  da coleta final. Testes pequenos de desenvolvimento podem usar outras grades.
- [ ] Padronizar tempo, CPU/RSS e GPU/VRAM quando disponíveis; separar geração,
  ajuste, treino, inferência, transferência e visualização. Registrar leituras
  indisponíveis como ausentes, não zero.
- [ ] Consolidar tabela com um registro por execução e arquivos preservados:
  identificação, código/configuração, algoritmo/variante, seed, repetição,
  hardware/backend, tempo por etapa, métricas, falhas e caminho do volume.
  O esquema existente exige cabeçalho fixo e um escritor sequencial; versionar
  eventual extensão e migração sem misturar colunas incompatíveis.
- [ ] Definir sumários e dispersão por condição, distinguindo sementes de
  geometria de repetições de tempo. Não comparar diretamente tempos de máquinas
  distintas como se medissem o mesmo ambiente.
- [ ] Se houver ajuste evolutivo, definir espaços, aptidão, orçamento e sementes
  reservadas; comparar com busca simples e relatar custo de busca separado.

## Frente de Pablo — modelos neurais

- [ ] Definir estado, ações, transições, recompensa, término e orçamento do
  PCGRL; validar ambiente pequeno e política aleatória antes do treinamento.
- [ ] Auditar dados de GAN, origem, independência e divisão por fonte, limites
  de memória, resolução e pós-processamento antes de interpretar resultados.
- [ ] Confirmar o significado de PCGARL e definir gerador, adversário, objetivo,
  avaliação de alcançabilidade e custo antes de implementá-lo.
- [ ] Produzir volumes sob o contrato comum, registrar checkpoints e avaliar
  amostras reservadas com a mesma interface estrutural e condições explícitas.
- [ ] Acordar com Felipe como registrar seeds de treino/geração, dataset,
  checkpoint, backend e métricas, sem preencher metadados desconhecidos com zero.

## Frentes auxiliares

- [ ] Inventariar novas point clouds e verificar existência, término de extração,
  formato, eixos e unidade antes do parsing incremental. Caminhos e estado dos
  dados externos são locais e precisam de confirmação; não presumir que `D:`
  esteja montado ou que as três extrações históricas tenham terminado.
- [ ] Validar guia procedural independente do scan antes de comparar CA guiado;
  o SDF da parede voxelizada não é SDF validado do ar real.
- [ ] Inspecionar volumes e malhas na Unity quando útil. gRPC e ROCm continuam
  posteriores ao núcleo científico.
- [ ] Atualizar a escrita do TCC após análise, registrando protocolo e decisões
  durante o trabalho; não apresentar hipóteses como resultados confirmados.
