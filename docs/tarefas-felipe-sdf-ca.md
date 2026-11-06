# Tarefas do Felipe — CA, Random Walk e algoritmo evolutivo

**Responsabilidades atualizadas em 02/11/2026; migração do Random Walk em `216f38d` a `e121f44`.** Felipe continua responsável pelo CA, já iniciou o progresso no Random Walk e, depois da estabilização desses geradores e da interface comum de métricas, implementará o algoritmo evolutivo. Flood fill e SDF real do Elaphes não são dependências do benchmark. Ver o [resumo quinzenal](relatorios/resumo-quinzenal-tcc-2026-10-18.docx), o [roadmap](roadmap.md) e as [tarefas de Pablo](tarefas-pablo-reconstrucao-modelos.md).


> **Atualização em 06/11/2026:** Felipe finaliza os clássicos e assume a coleta
> de métricas e a consolidação da tabela comparativa. Pablo inicia GAN, PCGRL e
> PCGARL; as definições comuns são acordadas pela dupla. As atribuições antigas
> a Pablo de coleta principal e de entrega da interface ficam superadas. O
> código da branch CA foi incorporado à main e à branch neural em `a7dd1e7`;
> a integração do CA ao benchmark continua pendente.

## Coleta e tabela comparativa

- [ ] Corrigir a integração do CA, testar importação e execução de ponta a ponta.
- [ ] Acordar com Pablo métricas estruturais, casos degenerados e a versão do
  esquema, usando `structural-v1` e sem assumir que o protocolo final já existe.
- [ ] Registrar por execução algoritmo, variante, configuração, revisão, seed,
  repetição, hardware/backend, métricas, custos, falhas e caminho do NPZ.
- [ ] Evoluir o CSV com versão de esquema e escrita sequencial; preservar
  resultados anteriores e registrar ausência de leituras como dado ausente.
- [ ] Separar treinamento, ajuste, geração e visualização; calcular sumários e
  dispersão por condição, distinguindo seeds de repetições de tempo.

Os resultados históricos abaixo identificam suas revisões; as tarefas seguem
o estado verificado neste checkout e o [roadmap](roadmap.md).

## Divisão de trabalho deste plano

Felipe finaliza a integração dos clássicos e conduz coleta de métricas e tabela comparativa; o algoritmo evolutivo continua planejado. Pablo conduz a frente neural. Os dois fecham juntos métricas, sementes, orçamento e hardware.

Em 02/11/2026 o gerador de Random Walk do pacote passou a ser o porte do projeto base feito pelo Felipe (ver [Random Walk](random-walk.md)), no lugar do random walk de 6 direções criado na estrutura inicial do projeto (`cab2d1e`, Pablo). Felipe conduz sua integração e experimentos no benchmark.

## Base disponível

- [x] CA básico produz matriz binária e histórico; falta adaptar a saída ao contrato `Volume3D` booleano em ZYX (`True = ar`).
- [x] O benchmark inicial mede tempo de geração, pico de RSS, proporção de vazio, fração da maior componente e estatísticas da transformada de distância.
- [x] Na branch `CA`, a contagem de vizinhos foi vetorizada por convolução 3D; testes comparam o resultado à versão em laço para bordas determinísticas. O modo de borda aleatório não é reproduzível bit a bit.
- [x] Na branch `CA`, há seeds e resultados NPZ, menu de execução/visualização, pesos espaciais opcionais e teste de equivalência do CA sem peso com peso zero. O peso é somado à contagem de vizinhos antes do limiar em cada iteração.
- [x] A branch inclui um amostrador de recursos do processo com tempo, CPU e RSS, além de GPU/VRAM quando disponíveis. A interpretação e a comparabilidade dessas medidas ainda dependem de protocolo.
- [ ] Os resultados comparáveis e a dispersão entre sementes ainda precisam ser coletados no protocolo comum.

## Prioridade imediata — consolidar CA e Random Walk

- [ ] Reparar a integração da branch com o benchmark, em versão própria do Felipe: `run_generation_benchmark.py`, `src/cavegen/menu.py` e os testes vieram da `main` usando `generate_cellular_automata`, `threshold_open_neighbors` e `keep_border_solid`, que o pacote do CA não tem. Até lá, `tests/test_menu.py` e `tests/test_experiment_records.py` falham na importação.
- [ ] Depois da correção, executar um caso pequeno de ponta a ponta e conferir contrato `Volume3D`, formato NPZ, linha CSV e tempo medido antes de iniciar a coleta final.
- [x] Registrar a configuração inicial `baseline_32.yaml`: volume ZYX `32³`, sementes `0` a `4` e parâmetros dos dois geradores clássicos.
- [x] Acordar `64³` em ZYX como grade das medições finais. `baseline_32.yaml` é configuração inicial, não o protocolo final.
- [ ] Fixar com Pablo sementes, repetições de medição, orçamento de ajuste, hardware e versões. A escala física do voxel só será declarada se houver conversão conhecida.
- [ ] Criar a configuração final do CA em `64³` ZYX, separada de `baseline_32.yaml`, com probabilidade inicial, sensibilidade, iterações e regra de borda registradas. Evitar a borda aleatória na comparação que exige reprodução bit a bit, ou controlar explicitamente seus sorteios.
- [ ] Reexecutar o CA básico e, depois do ajuste, o CA com parâmetros escolhidos; conferir arquivos NPZ e linhas CSV, registrar configuração e variação entre sementes.
- [x] Escolher a variante do Random Walk e integrá-la ao contrato público `Volume3D`: a ponderada por waypoints do projeto base. O benchmark e `python -m cavegen` já passam `caverna` e `raio_voxels`, mas só executam depois da integração do CA.
- [ ] Registrar os parâmetros do Random Walk, sua proveniência e as decisões de voxelização; manter o protótipo por waypoints separado do baseline quando houver condicionamento por dados reais. O gerador por waypoints é hoje o único Random Walk do pacote, então essa separação precisa ser revista com o Pablo.
- [ ] Executar casos pequenos dos dois geradores contra a interface comum de métricas.
- [ ] Inspecionar conectividade, componentes e ocupação, inclusive volume sem ar e volume quase todo aberto. Conferir a semântica das bordas no relatório.
- [ ] Registrar que a transformada de distância ao sólido depende da resolução e do espaçamento; seus resumos não são automaticamente a largura de todos os túneis.

## Extensão em protótipo — CA com campo de controle

- [x] Implementar a soma de um peso espacial à contagem de vizinhos do CA. Testes cobrem peso positivo/negativo, shape incompatível e equivalência entre ausência de peso e peso zero.
- [x] Criar um pipeline experimental em `random_walk_temp/`: portar a caminhada ponderada por waypoints de um projeto base, voxelizar os caminhos em tubos e calcular a distância à borda (`101aa24`, `2cf8f8c`, `a58155e`). O raio padrão de 1,5 voxel em `64³` foi escolhido para manter o túnel representável, mas engrossa a geometria em relação ao original. A caminhada e a voxelização foram depois migradas para o pacote (seção [Random Walk](#random-walk-ponderado-do-projeto-base)); o SDF não.
- [x] Adotar como contrato de SDF sintético o sinal positivo no interior do vazio, negativo no exterior sólido, zero na borda e distância euclidiana em voxels, na grade ZYX. O protótipo de SDF do Random Walk seguia esse sinal e unidade.
- [ ] Consolidar um campo de controle independente do scan de teste, com origem, regra de borda e parâmetros registrados, preservando o contrato acima. Os waypoints do Random Walk vêm de cavernas reais do projeto base.
- [ ] Comparar CA básico e condicionado com sementes e orçamento equivalentes, medindo ocupação, conectividade, aderência ao controle permitido, diversidade e custo. Separar o efeito do controle da geração sem condicionamento.

## Random Walk ponderado do projeto base

Detalhes, números medidos e limites em [Random Walk](random-walk.md).

- [x] Exportar os grafos de waypoints da cena Unity do projeto base (3D-Cave-Generation, `7a6c617`) para `configs/random_walk/` (`example`, `knotlow_cavern`, `upper_long_churns`, `odins_mine`) com `exportar_cena.py`. O grafo de cada YAML é idêntico ao da cena nas quatro cavernas; o gerador não depende mais da Unity. Commit `216f38d`.
- [x] Migrar `random_walk_temp/` para `src/cavegen/generators/random_walk/` sem mudança de lógica, com `generate_random_walk(...) -> Volume3D` e `RandomWalkGenerator`, apagando o protótipo e o `random_walk.py` de 6 direções. Evidência: NPZ da seed 1 das quatro cavernas (caminhos, inícios, classificação `64³`) idênticos bit a bit aos do protótipo; `tests/test_random_walk.py` (17) e `tests/test_random_walk_fidelidade.py` (15); suíte com 93 testes em `fe3fd04`, só `test_f32` falhando (`PermissionError` do Windows, anterior). Commits `df9b27b`, `fe3fd04` e `e121f44`.
- [x] Criar o menu de terminal do Random Walk no padrão do CA: gera com caverna, seed, lado, raio e, opcionalmente, `weight`, `k` e `spacer` limitados às faixas do C#, grava `results/result_000.npz` medindo com `track_resources` e plota caminhos ou grade classificada. Evidência: `tests/test_random_walk_menu.py` (6); suíte com 99 testes em `e121f44`, só `test_f32` falhando. Commit `658d397`.
- [ ] Avisar o Pablo de que `src/cavegen/generators/random_walk.py` foi substituído pelo pacote (`caverna`, `weight`, `k`, `spacer`, `raio_voxels` no lugar de `steps` e `brush_radius`) e de que o merge da `main` de 04/11/2026 adaptou o lado do Random Walk no benchmark, em `src/cavegen/menu.py`, nas configurações e nos testes dele, trocando `SystemMonitor` por `ResourceSampler`. O lado do CA ficou como ele escreveu e não importa neste checkout até a integração própria do Felipe. Aceite: Pablo ciente.
- [x] Fazer o benchmark aceitar o Random Walk novo. Feito no merge da `main` de 04/11/2026; o import do CA segue pendente na integração própria do Felipe.
- [ ] Escolher com o Pablo a caverna de waypoints do protocolo (padrão atual `knotlow_cavern`). Aceite: caverna registrada na configuração final e nos metadados, e nenhuma das cavernas reais usadas como waypoints (Knotlow, Upper Long Churns, Odins Mine) usada como referência de avaliação do Random Walk.
- [ ] Se o GA buscar nos parâmetros do Random Walk, decidir com o Pablo se respeita as faixas do C# (`weight` em [0,1; 1], `k` e `spacer` inteiros em [1, 30]); hoje `generate_random_walk` aceita valores contínuos e fora delas. Aceite: limites escritos no espaço de busca.
- [ ] SDF do Random Walk, quando o Felipe decidir retomá-lo: migrar ou reescrever a etapa `sdf_caminhada.py` (histórico em `a58155e`) e regravar a origem do peso 002 do CA, que aponta para `random_walk_temp/npz/knotlow_cavern_seed001_64_sdf.npz`, arquivo que não existe mais. Aceite: SDF gerado pelo pacote igual ao do peso 002 ou diferença explicada.
- [ ] `configs/random_walk/` é encontrado por caminho relativo ao arquivo (`parents[4]`); funciona só rodando do repositório ou de instalação editável. Aceite: decisão registrada de manter assim (e onde o protocolo roda) ou de trocar o mecanismo.

## Etapa seguinte — algoritmo evolutivo para os dois geradores

- [ ] Definir cromossomo e limites dos parâmetros do **CA**: probabilidade inicial, sensibilidade, iterações e tratamento de borda; incluir peso de controle apenas se o experimento condicionado for aprovado.
- [ ] Definir cromossomo e limites dos parâmetros do **Random Walk** conforme a variante escolhida, sem forçar os mesmos parâmetros ou codificação do CA.
- [ ] Construir a função de aptidão sobre a interface comum de métricas e registrar pesos, normalização, penalidades e tratamento de candidatos inválidos.
- [ ] Fixar sementes de ajuste e sementes reservadas de avaliação, número de sementes por candidato, total de avaliações, parada e tratamento de candidatos inválidos. Não selecionar parâmetros usando os resultados reservados.
- [ ] Comparar o algoritmo evolutivo de cada gerador com busca simples de igual orçamento. Registrar número de avaliações e tempo total de busca; medir separadamente o tempo de gerar um volume com a configuração escolhida.

## Orçamento, repetições e hardware a fechar com Pablo

- [ ] Separar sementes diferentes para medir diversidade geométrica de repetições da mesma configuração para estimar variação de tempo. Definir quantidades antes da coleta e registrar cada execução.
- [ ] Usar o rastreador de CPU/RSS e de GPU/VRAM quando disponível, anotando máquina, threads, backend e versões. Verificar o intervalo de amostragem e execuções curtas; célula vazia de GPU significa leitura ausente.
- [ ] Manter o CA otimizado na CPU para o protocolo inicial. Não é necessário portá-lo para GPU porque GAN/PCGRL treinam no Colab. Uma porta para GPU seria experimento separado de aceleração, com teste de equivalência, transferências e sincronização medidos.
- [ ] Entregar a Pablo os resultados de CA e Random Walk, antes e depois do ajuste, e, se houver, variantes condicionadas, sempre com configuração, sementes, métricas e ambiente. Custos de CPU local e GPU do Colab devem ser apresentados por ambiente, sem uma classificação direta de velocidade entre máquinas diferentes.

## Limite da frente real

O PLY do Elaphes observa parede, não o interior. Na branch `CA`, `sdf_temp/` usa flood fill de seis vizinhos e EDT para produzir um campo experimental da grade de **parede** `64³`: 783 voxels de borda, 292 classificados como internos e 26 vazios fechados encontrados. O sinal é positivo no interno e negativo no externo, em voxels. Como entradas e frestas permitem comunicação com o exterior, esse "interno" não valida o ar transitável da caverna. O valor de IoU 0,49 relatado no diário da branch é uma sobreposição diagnóstica com a grade derivada do scan, não IoU volumétrica contra `VOID` real. As malhas avaliadas também não forneceram classificação interior/exterior confiável. Assim, esse campo não deve ser apresentado como SDF real validado nem como referência de avaliação.

Para cada mudança Python com contrato observável, adicionar teste em `tests/`; antes de concluir, executar a suíte e uma importação ou exemplo pertinente.
