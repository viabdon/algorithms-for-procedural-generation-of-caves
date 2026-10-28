# Roadmap do TCC

**Replanejamento de 18/10/2026; branch `CA` verificada em 28/10/2026 (`a58155e`).** O [resumo quinzenal](relatorios/resumo-quinzenal-tcc-2026-10-18.docx) retira a reconstrução do Elaphes, o SDF real e a IoU volumétrica do caminho crítico. Este roadmap separa o que está no checkout `main` dos avanços ainda isolados nas branches `CA` e `experiment/elaphes-meshing`.

## Base disponível

- [x] Leitura incremental de PLY/F32, limites XYZ, normalização XYZ→ZYX e voxelização diagnóstica de superfície. O PLY do Elaphes declara 94.465.067 pontos; em `32³`, 245 de 32.768 células foram marcadas como parede observada. Essa grade não representa vazio.
- [x] `Volume3D` booleano, Random Walk e CA básico, com `True = ar` e `False = sólido`.
- [x] Persistência NPZ, exportação de malha de volumes gerados por Marching Cubes e benchmark inicial em Python.
- [x] Métricas iniciais de tempo, pico de RSS, proporção de vazio, fração na maior componente e estatísticas da transformada de distância.
- [x] Ensaios exploratórios de Poisson, linha central, orientação de normais e espessamento registrados na branch experimental e em artefatos locais. Nenhum produziu uma referência volumétrica validada.

### Avanços na branch `CA` ainda não integrados ao `main`

- [x] CA com contagem 3D vetorizada, bordas configuráveis, sementes/resultados NPZ, menu e peso espacial opcional. Testes verificam equivalência com o laço para bordas determinísticas e CA sem peso igual ao de peso zero.
- [x] Amostrador de tempo, CPU e RSS do processo, com GPU/VRAM quando disponíveis. A branch contém testes do rastreador, sem protocolo final de hardware.
- [x] Protótipos `sdf_temp/` de flood fill e EDT da **parede** voxelizada do Elaphes e `random_walk_temp/` de caminhada ponderada por waypoints, voxelização tubular e campo de distância. São experimentos, não a referência real validada nem geradores integrados ao benchmark.
- [x] Fixar o contrato do SDF sintético: positivo no interior do vazio, negativo no exterior sólido, zero na borda e distância euclidiana em voxels, na mesma grade ZYX. O protótipo de Random Walk segue sinal e unidade; a API pública ainda não está integrada.
- [ ] Corrigir a integração: o benchmark da branch importa `generate_cellular_automata`, que não é exportado pelo pacote reorganizado. A suíte da branch passou com 53 testes, mas a checagem de importação do benchmark falhou.

## Prioridade 1 — Fechar o benchmark clássico

- [x] Registrar a configuração inicial `baseline_32.yaml`: volume ZYX `32³`, sementes `0` a `4` e parâmetros de Random Walk e CA básico.
- [x] Fixar `64³` em ZYX como grade das medições finais. A configuração `baseline_32.yaml` permanece como teste inicial e precisa de uma configuração final distinta.
- [ ] Fixar sementes e repetições de medição; documentar hardware, versões e orçamento de ajuste. Não atribuir escala física aos voxels sem conversão conhecida.
- [ ] Integrar a API do CA da branch ao benchmark e testar importação e uma execução pequena antes de coletar resultados.
- [ ] Reexecutar ambos, registrar resultados e dispersão por semente. Conferir NPZ, CSV e casos degenerados antes de interpretar diferenças.
- [ ] Interpretar tempo, pico de RAM, proporção de vazio e fração da maior componente. Completar a contagem de componentes quando necessária ao relatório.
- [ ] Documentar resolução e unidade da transformada de distância. Não chamar seus resumos de largura validada de todos os túneis.

## Prioridade 2 — Avaliação estrutural e relato

- [ ] Definir e validar conectividade, componentes e ocupação como medidas estruturais centrais. Especificar ramificação, tortuosidade e diversidade antes de usá-las.
- [ ] Integrar e validar a instrumentação de CPU/RSS e GPU/VRAM da branch `CA` no protocolo comum; GPU/VRAM podem ficar ausentes quando não houver leitura. Definir como amostragem e execuções curtas entram no relato.
- [ ] Definir a apresentação de custos por ambiente: CA e Random Walk podem permanecer na CPU; modelos neurais podem usar GPU no Colab. Separar treino, inferência/geração e transferências. Portar CA para GPU somente se surgir uma pergunta experimental específica sobre esse backend.
- [ ] Separar custo de geração, treino, otimização e visualização; identificar cada ambiente de execução.
- [ ] Atualizar o texto do TCC para explicitar a retirada da IoU volumétrica e a impossibilidade atual de afirmar recuperação do volume interno real do Elaphes.

## Prioridade 3 — Frente neural

- [ ] Auditar volume, independência e semântica dos dados de treino antes de escolher uma GAN. Dados sintéticos servem a testes de infraestrutura, não à alegação de aprendizagem de cavernas reais.
- [ ] Especificar um MDP pequeno para PCGRL, com recompensa inicial de conectividade e ocupação, sem IoU com o scan.
- [ ] Implementar geração funcional e comparar com os baselines sob o mesmo contrato `Volume3D`; reportar treino e geração separadamente. As interfaces atuais lançam `NotImplementedError`.

## Extensões condicionais

- [x] Prototipar peso espacial no CA e verificar peso zero equivalente ao CA básico na branch `CA`.
- [ ] Validar um guia procedural independente do scan de teste sob o contrato de SDF já fixado, registrando regra de borda e origem, e comparar CA condicionado com o básico sob protocolo comum. A extensão não bloqueia o benchmark clássico.
- [ ] Aplicar otimização genética aos parâmetros de CA e Random Walk, depois de definir espaços de busca, função de aptidão e orçamento comparável. Reservar sementes de avaliação e comparar com busca simples de igual orçamento. Distinguir custo de otimização do custo de geração.
- [ ] Usar Unity para inspeção dos volumes e malhas exportados. gRPC e AMD/ROCm ficam para depois do pipeline científico.

## Reconstrução real fora do escopo atual

Os ensaios com Poisson, linha central e dilatação melhoraram diagnósticos, mas as malhas avaliadas não satisfizeram conjuntamente fechamento, ausência de auto-interseções, conectividade e aderência. O flood fill e a EDT da branch `CA` calculam um campo da grade de **parede** e não resolvem entradas, regiões não observadas ou o ar interno real. A IoU diagnóstica relatada para o CA guiado pelo Elaphes não é uma métrica volumétrica válida contra `VOID` real. Ball Pivoting, Alpha Shapes, winding numbers e fechos controlados foram discutidos, sem comparação concluída. Uma retomada exigiria validação geométrica, classificação interior/exterior e unidade espacial. Preservar códigos e registros; o rollback é metodológico.

Ver [arquitetura](architecture.md), [metodologia](methodology-adjustments.md) e [tarefas por responsável](../Orientacao-codex.md).
