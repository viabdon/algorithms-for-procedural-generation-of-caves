# Tarefas do Felipe — CA e extensões de controle

**Estado verificado na branch `CA` em 28/10/2026 (`a58155e`).** O CA básico e o benchmark clássico continuam prioritários. A branch avançou no CA com pesos, instrumentação e protótipos de SDF, ainda sem integração validada ao benchmark principal. Flood fill e SDF real do Elaphes não são dependências do benchmark. Ver o [resumo quinzenal](relatorios/resumo-quinzenal-tcc-2026-10-18.docx), o [roadmap](roadmap.md) e as [tarefas de Pablo](tarefas-pablo-reconstrucao-modelos.md).

## Divisão de trabalho deste plano

Felipe conduz a **integração e os experimentos do CA**, seu peso espacial, a instrumentação da branch `CA` e o ajuste genético dos parâmetros do CA. Pablo conduz o **Random Walk** no benchmark, o ajuste de seus parâmetros, as métricas, a análise e a frente neural. Os dois fecham juntos sementes, orçamento e hardware para que os resultados tenham o mesmo critério de leitura. Isso define entregas pendentes, não resultados já obtidos.

## Base disponível

- [x] CA básico gera `Volume3D` booleano em ZYX, com `True = ar` e `False = sólido`.
- [x] O benchmark inicial mede tempo de geração, pico de RSS, proporção de vazio, fração da maior componente e estatísticas da transformada de distância.
- [x] Na branch `CA`, a contagem de vizinhos foi vetorizada por convolução 3D; testes comparam o resultado à versão em laço para bordas determinísticas. O modo de borda aleatório não é reproduzível bit a bit.
- [x] Na branch `CA`, há seeds e resultados NPZ, menu de execução/visualização, pesos espaciais opcionais e teste de equivalência do CA sem peso com peso zero. O peso é somado à contagem de vizinhos antes do limiar em cada iteração.
- [x] A branch inclui um amostrador de recursos do processo com tempo, CPU e RSS, além de GPU/VRAM quando disponíveis. A interpretação e a comparabilidade dessas medidas ainda dependem de protocolo.
- [ ] Os resultados comparáveis e a dispersão entre sementes ainda precisam ser coletados no protocolo comum.

## Prioridade imediata — reproduzir o CA

- [ ] Reparar a integração da branch com o benchmark: `run_generation_benchmark.py` importa `generate_cellular_automata`, ausente no pacote reorganizado. O import falha em `a58155e`, embora os 53 testes da branch passem.
- [ ] Depois da correção, executar um caso pequeno de ponta a ponta e conferir contrato `Volume3D`, formato NPZ, linha CSV e tempo medido antes de iniciar a coleta final.
- [x] Registrar a configuração inicial `baseline_32.yaml`: volume ZYX `32³`, sementes `0` a `4` e parâmetros dos dois geradores clássicos.
- [x] Acordar `64³` em ZYX como grade das medições finais. `baseline_32.yaml` é configuração inicial, não o protocolo final.
- [ ] Fixar com Pablo sementes, repetições de medição, orçamento de ajuste, hardware e versões. A escala física do voxel só será declarada se houver conversão conhecida.
- [ ] Criar a configuração final do CA em `64³` ZYX, separada de `baseline_32.yaml`, com probabilidade inicial, sensibilidade, iterações e regra de borda registradas. Evitar a borda aleatória na comparação que exige reprodução bit a bit, ou controlar explicitamente seus sorteios.
- [ ] Reexecutar o CA básico e, depois do ajuste, o CA com parâmetros escolhidos; conferir arquivos NPZ e linhas CSV, registrar configuração e variação entre sementes.
- [ ] Inspecionar conectividade, componentes e ocupação, inclusive volume sem ar e volume quase todo aberto. Conferir a semântica das bordas no relatório.
- [ ] Registrar que a transformada de distância ao sólido depende da resolução e do espaçamento; seus resumos não são automaticamente a largura de todos os túneis.

## Extensão em protótipo — CA com campo de controle

- [x] Implementar a soma de um peso espacial à contagem de vizinhos do CA. Testes cobrem peso positivo/negativo, shape incompatível e equivalência entre ausência de peso e peso zero.
- [x] Criar um pipeline experimental em `random_walk_temp/`: portar a caminhada ponderada por waypoints de um projeto base, voxelizar os caminhos em tubos e calcular a distância à borda. O raio padrão de 1,5 voxel em `64³` foi escolhido para manter o túnel representável, mas engrossa a geometria em relação ao original; o código ainda não integra o gerador público nem o benchmark.
- [x] Adotar como contrato de SDF sintético o sinal positivo no interior do vazio, negativo no exterior sólido, zero na borda e distância euclidiana em voxels, na grade ZYX. O protótipo de Random Walk segue esse sinal e unidade.
- [ ] Consolidar um campo de controle independente do scan de teste, com origem, regra de borda e parâmetros registrados, preservando o contrato acima. Os waypoints do protótipo atual vêm de cavernas reais do projeto base.
- [ ] Comparar CA básico e condicionado com sementes e orçamento equivalentes, medindo ocupação, conectividade, aderência ao controle permitido, diversidade e custo. Separar o efeito do controle da geração sem condicionamento.

## Ajuste planejado — otimização genética

- [ ] Definir cromossomo e limites dos parâmetros do **CA**: probabilidade inicial, sensibilidade, iterações e tratamento de borda; incluir peso de controle apenas se o experimento condicionado for aprovado. Combinar com Pablo a mesma função de aptidão estrutural usada no Random Walk, com parâmetros próprios para cada gerador.
- [ ] Fixar sementes de ajuste e sementes reservadas de avaliação, número de sementes por candidato, total de avaliações, parada e tratamento de candidatos inválidos. Não selecionar parâmetros usando os resultados reservados.
- [ ] Comparar o GA do CA com busca simples de igual orçamento. Registrar número de avaliações e tempo total de busca; medir separadamente o tempo de gerar um volume com a configuração escolhida. Pablo faz a avaliação correspondente do Random Walk.

## Orçamento, repetições e hardware a fechar com Pablo

- [ ] Separar sementes diferentes para medir diversidade geométrica de repetições da mesma configuração para estimar variação de tempo. Definir quantidades antes da coleta e registrar cada execução.
- [ ] Usar o rastreador de CPU/RSS e de GPU/VRAM quando disponível, anotando máquina, threads, backend e versões. Verificar o intervalo de amostragem e execuções curtas; célula vazia de GPU significa leitura ausente.
- [ ] Manter o CA otimizado na CPU para o protocolo inicial. Não é necessário portá-lo para GPU porque GAN/PCGRL treinam no Colab. Uma porta para GPU seria experimento separado de aceleração, com teste de equivalência, transferências e sincronização medidos.
- [ ] Entregar a Pablo os resultados de CA básico, CA ajustado e, se houver, CA condicionado com configuração, sementes, métricas e ambiente. Custos de CPU local e GPU do Colab devem ser apresentados por ambiente, sem uma classificação direta de velocidade entre máquinas diferentes.

## Limite da frente real

O PLY do Elaphes observa parede, não o interior. Na branch `CA`, `sdf_temp/` usa flood fill de seis vizinhos e EDT para produzir um campo experimental da grade de **parede** `64³`: 783 voxels de borda, 292 classificados como internos e 26 vazios fechados encontrados. O sinal é positivo no interno e negativo no externo, em voxels. Como entradas e frestas permitem comunicação com o exterior, esse "interno" não valida o ar transitável da caverna. O valor de IoU 0,49 relatado no diário da branch é uma sobreposição diagnóstica com a grade derivada do scan, não IoU volumétrica contra `VOID` real. As malhas avaliadas também não forneceram classificação interior/exterior confiável. Assim, esse campo não deve ser apresentado como SDF real validado nem como referência de avaliação.

Para cada mudança Python com contrato observável, adicionar teste em `tests/`; antes de concluir, executar a suíte e uma importação ou exemplo pertinente, conforme `AGENTS.md`.
