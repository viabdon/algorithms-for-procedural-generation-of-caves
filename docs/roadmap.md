# Roadmap do TCC

**Replanejamento de 18/10/2026; responsabilidades atualizadas em 02/11/2026; migração do Random Walk em `216f38d` a `e121f44`.** O [resumo quinzenal](relatorios/resumo-quinzenal-tcc-2026-10-18.docx) retira a reconstrução do Elaphes, o SDF real e a IoU volumétrica do caminho crítico. Pablo prioriza métricas, redes neurais e parsing de novas cavernas; Felipe continua CA e Random Walk e depois implementa a otimização evolutiva. Este roadmap separa o que está no checkout `main` dos avanços ainda isolados nas branches `CA` e `experiment/elaphes-meshing`.

## Base disponível

- [x] Leitura incremental de PLY/F32, limites XYZ, normalização XYZ→ZYX e voxelização diagnóstica de superfície. O PLY do Elaphes declara 94.465.067 pontos; em `32³`, 245 de 32.768 células foram marcadas como parede observada. Essa grade não representa vazio.
- [x] `Volume3D` booleano, Random Walk e CA básico, com `True = ar` e `False = sólido`.
- [x] Persistência NPZ, exportação de malha de volumes gerados por Marching Cubes e benchmark inicial em Python.
- [x] Métricas iniciais de tempo, pico de RSS, proporção de vazio, fração na maior componente e estatísticas da transformada de distância.
- [x] Ensaios exploratórios de Poisson, linha central, orientação de normais e espessamento registrados na branch experimental e em artefatos locais. Nenhum produziu uma referência volumétrica validada.

### Avanços na branch `CA` ainda não integrados ao `main`

- [x] CA com contagem 3D vetorizada, bordas configuráveis, sementes/resultados NPZ, menu e peso espacial opcional. Testes verificam equivalência com o laço para bordas determinísticas e CA sem peso igual ao de peso zero.
- [x] Amostrador de tempo, CPU e RSS do processo, com GPU/VRAM quando disponíveis. A branch contém testes do rastreador, sem protocolo final de hardware.
- [x] Protótipos `sdf_temp/` de flood fill e EDT da **parede** voxelizada do Elaphes e `random_walk_temp/` de caminhada ponderada por waypoints, voxelização tubular e campo de distância. São experimentos, não a referência real validada nem geradores integrados ao benchmark. `random_walk_temp/` foi depois migrado para o pacote e apagado (item abaixo).
- [x] Fixar o contrato do SDF sintético: positivo no interior do vazio, negativo no exterior sólido, zero na borda e distância euclidiana em voxels, na mesma grade ZYX. O protótipo de SDF do Random Walk seguia sinal e unidade; ficou só no histórico (`a58155e`) e a API pública de SDF ainda não está integrada.
- [x] Migrar o random walk ponderado por waypoints do projeto base para `src/cavegen/generators/random_walk/`, sem mudança de lógica, substituindo o random walk de 6 direções (`steps`, `brush_radius`). Grafos exportados para `configs/random_walk/`; NPZ da seed 1 das quatro cavernas idênticos bit a bit aos do protótipo; 38 testes novos, contando os 6 do menu de terminal. Commits `216f38d` a `e121f44`. Ver [Random Walk](random-walk.md).
- [ ] Integrar o CA ao benchmark refatorado da `main`: ele importa `generate_cellular_automata`, ausente no pacote do CA, e passa `threshold_open_neighbors`. O Felipe vai escrever essa integração separadamente; até lá o benchmark, `python -m cavegen`, `tests/test_menu.py` e `tests/test_experiment_records.py` não importam.
- [ ] SDF do Random Walk, quando o Felipe decidir retomá-lo: a etapa não foi migrada, e o peso 002 do CA aponta para um arquivo do protótipo que não existe mais.

## Prioridade 1 — Implementar e padronizar métricas

- [x] Inventariar as métricas estruturais existentes e registrar contratos, unidades, casos degenerados e colunas em [métricas estruturais](metricas-estruturais.md).
- [x] Implementar `evaluate_structure(Volume3D)` e funções individuais para `bool[D,H,W]` validado, com resultados imutáveis e registro plano `structural-v1`.
- [x] Validar conectividade, componentes, ocupação e estatísticas da EDT por testes geométricos independentes.
- [ ] Definir ramificação, tortuosidade e diversidade; considerar o reaproveitamento do grafo de linha central, validando extração, junções e ciclos.
- [ ] Padronizar a medição de tempo e recursos, distinguindo tempo de geração, otimização, treino, inferência, transferências e visualização. Leituras ausentes de GPU/VRAM não equivalem a zero.
- [x] Definir tratamento de volumes vazios, totalmente abertos, desconectados e com shapes inválidos; cobrir contratos observáveis com testes.
- [x] Acrescentar resultados estruturais e contexto inicial por execução ao CSV central, preservando arquivos NPZ. O inventário completo de hardware e as repetições permanecem pendentes.
- [ ] Fixar esquema de saída e metadados de resolução, eixos, sementes, repetições, hardware, backend e versões. Não atribuir escala física aos voxels sem conversão conhecida.
- [ ] Disponibilizar a interface ao CA, Random Walk, algoritmo evolutivo e modelos neurais antes da coleta final.

## Prioridade 2 — Implementar os geradores neurais

- [ ] Auditar volume, independência e semântica dos dados de treino antes de escolher uma GAN. Dados sintéticos servem a testes de infraestrutura, não à alegação de aprendizagem de cavernas reais.
- [ ] Especificar um MDP pequeno para PCGRL, com recompensa inicial de conectividade e ocupação, sem IoU com o scan.
- [ ] Implementar geração funcional e comparar com os baselines sob o mesmo contrato `Volume3D`; reportar treino e geração separadamente. As interfaces atuais lançam `NotImplementedError`.
- [ ] Reutilizar a interface de métricas da prioridade 1 para avaliação e, no PCGRL, somente para recompensas que tenham definição e custo compatíveis com o ambiente.

## Prioridade 3 — Inventariar e parsear novas cavernas

- [ ] Usar o volume externo `D:` como origem preferencial das point clouds, evitando duplicação de arquivos grandes no repositório.
- [ ] Aguardar o término da descompactação das três cavernas em andamento antes de validar tamanho, hash, formato ou conteúdo.
- [ ] Inventariar as cavernas disponíveis, incluindo quais pertencem ao conjunto de 16 associado à fonte do KarstConduitCatalogue, sem presumir que todas tenham o mesmo formato ou semântica.
- [ ] Para cada formato novo, documentar cabeçalho, tipo de registro, eixos, unidade quando conhecida e representação; reutilizar `iter_ply_xyz` ou `iter_f32_xyz` quando o contrato for compatível.
- [ ] Implementar parsing incremental com validações, `float32`, limites de memória e testes sintéticos pequenos. Não carregar a point cloud completa por padrão.
- [ ] Manter a distinção entre superfície observada e vazio; qualquer voxelização ou uso como treino exige decisão metodológica própria.

## Trabalho de Felipe — geradores clássicos e algoritmo evolutivo

- [ ] Integrar a API do CA da branch ao benchmark e testar importação e uma execução pequena. Versão personalizada do Felipe, separada do que veio da `main`.
- [x] Adaptar o benchmark e `python -m cavegen` ao Random Walk por waypoints (`caverna`, `raio_voxels`), medindo pelo `ResourceSampler`. Só executa depois da integração do CA. Feito no merge da `main` de 04/11/2026.
- [ ] Escolher a caverna de waypoints do Random Walk usada no protocolo (padrão atual `knotlow_cavern`), sem usar essa mesma caverna como referência de avaliação.
- [ ] Criar configurações finais `64³` distintas de `baseline_32.yaml` e fornecer saídas rastreáveis para a interface comum de métricas.
- [ ] Definir e implementar o algoritmo evolutivo para os parâmetros de CA e Random Walk após a estabilização das métricas, com espaços de busca próprios e aptidão comum quando metodologicamente aplicável. No Random Walk, decidir se a busca respeita as faixas do C# do projeto base (`weight` em [0,1; 1], `k` e `spacer` inteiros em [1, 30]).
- [ ] Reservar sementes de avaliação, comparar com busca simples de igual orçamento e separar custo de otimização do custo de geração.

## Extensões condicionais

- [x] Prototipar peso espacial no CA e verificar peso zero equivalente ao CA básico na branch `CA`.
- [ ] Validar um guia procedural independente do scan de teste sob o contrato de SDF já fixado, registrando regra de borda e origem, e comparar CA condicionado com o básico sob protocolo comum. A extensão não bloqueia o benchmark clássico.
- [ ] Usar Unity para inspeção dos volumes e malhas exportados. gRPC e AMD/ROCm ficam para depois do pipeline científico.

## Fechamento do experimento

- [ ] Reexecutar os geradores sob o protocolo final, registrar resultados e dispersão por semente e conferir NPZ, CSV e casos degenerados antes da interpretação.
- [ ] Somente após a coleta e a análise, padronizar de forma ampla a documentação, atualizar o texto do TCC e consolidar tabelas, limitações e conclusões. Durante o experimento, registrar apenas o necessário para reprodutibilidade e decisões de contrato.

## Reconstrução real fora do escopo atual

Os ensaios com Poisson, linha central e dilatação melhoraram diagnósticos, mas as malhas avaliadas não satisfizeram conjuntamente fechamento, ausência de auto-interseções, conectividade e aderência. O flood fill e a EDT da branch `CA` calculam um campo da grade de **parede** e não resolvem entradas, regiões não observadas ou o ar interno real. A IoU diagnóstica relatada para o CA guiado pelo Elaphes não é uma métrica volumétrica válida contra `VOID` real. Ball Pivoting, Alpha Shapes, winding numbers e fechos controlados foram discutidos, sem comparação concluída. Uma retomada exigiria validação geométrica, classificação interior/exterior e unidade espacial. Preservar códigos e registros; o rollback é metodológico.

Ver [arquitetura](architecture.md), [metodologia](methodology-adjustments.md) e [tarefas por responsável](../Orientacao-codex.md).
