# Ajustes metodológicos da comparação de geradores

## Decisão e alcance

O [resumo quinzenal de 18/10/2026](relatorios/resumo-quinzenal-tcc-2026-10-18.docx) registra o retorno à geração de volumes voxelizados como núcleo do TCC. A reconstrução do Elaphes, um SDF real e a IoU volumétrica contra esse scan deixam de ser pré-requisitos ou métricas do escopo atual. O benchmark deve comparar algoritmos por custo, estrutura, controle e diversidade, sem alegar recuperação do volume interno real do Elaphes.

## 1. Limites da referência real

Os 94.465.067 pontos do PLY amostram parede observada. A voxelização direta `32³` marcou 245 células de superfície entre 32.768. `True` nessa grade tem semântica diferente do `True` dos volumes gerados, que significa ar. Inverter a grade não produz referência de vazio: o complemento mistura ar interno, exterior e partes não observadas.

Os ensaios com Screened Poisson melhoraram a aderência com amostragem mais densa, mas mantiveram bordas, defeitos topológicos ou extrapolação. A linha central exploratória identificou ramos; a orientação por cossenos alterou bordas e componentes sem produzir malha validada. O espessamento da ocupação bruta levou a malhas sem arestas de borda, porém com auto-interseções e falha na checagem de watertightness. A unidade física XYZ ainda não foi confirmada. Esses resultados delimitam as condições examinadas no Elaphes, sem invalidar os métodos em geral. Os registros estão na branch `experiment/elaphes-meshing` e em artefatos locais.

O Elaphes continua útil para inspeção qualitativa e propriedades observáveis. Métricas de superfície com tolerância podem ser estudadas em regiões alinhadas e comparáveis, distinguindo observação de extrapolação. IoU de superfície não entra automaticamente como substituta da volumétrica. Ball Pivoting, Alpha Shapes, winding numbers e fechos controlados são hipóteses futuras, sem comparação concluída demonstrada pelo resumo.

Na branch `CA` (`a58155e`), um flood fill de seis vizinhos e uma EDT calculam um campo experimental da grade de parede `64³`. Encontraram 26 vazios fechados e classificaram 783 voxels como borda e 292 como internos. O campo usa interno positivo, externo negativo e distância em voxels. A classe interna pode conter espessura de parede e buracos fechados; o ar do túnel aberto se conecta ao exterior. Portanto, nem o campo nem a IoU 0,49 relatada para o CA guiado por ele validam uma referência volumétrica de ar do Elaphes. Esse número é apenas diagnóstico de sobreposição com a grade derivada do scan.

## 2. Protocolo do benchmark principal

Comparar Random Walk e CA básico primeiro em `64³`, com eixos ZYX. Fixar sementes, repetições, parâmetros e orçamento de ajuste antes da coleta; registrar código, configuração e hardware e relatar dispersão. A grade não recebe unidade física sem conversão conhecida. As medidas já disponíveis no `main` são tempo de geração, pico de RSS, proporção de vazio, fração de vazio na maior componente e estatísticas da transformada de distância. CPU/GPU/VRAM e descritores adicionais precisam de instrumentação e protocolo. Custos de treinamento, otimização, geração e visualização devem ser separados quando essas etapas existirem.

A branch `CA` acrescenta rastreamento de tempo, CPU e RSS do processo, além de GPU/VRAM quando houver leitura. Há testes do amostrador, mas o protocolo de comparação ainda precisa definir hardware, intervalo de amostragem e tratamento de execuções curtas e leituras ausentes. O benchmark dessa branch não importa por causa da antiga API do CA; seus resultados não devem ser tratados como benchmark integrado antes da correção e de uma execução de ponta a ponta.

**Geradores do benchmark (04/11/2026).** O Random Walk de 6 direções deu lugar ao ponderado por waypoints do projeto base nas configurações, no benchmark e no menu. O lado do CA ficou como veio da `main` e não funciona na branch `CA`: o benchmark importa `generate_cellular_automata` e passa `threshold_open_neighbors`, que o pacote do CA não tem. O Felipe vai escrever essa integração separadamente. O CA antigo contava 26 vizinhos e forçava a borda sólida; o da branch conta 27 células com `sensitivity`, então os parâmetros antigos não valem para ele sem decisão explícita.

Não é requisito portar o CA otimizado à GPU apenas porque os modelos neurais treinam no Colab. A comparação estrutural usa saídas `64³` e as mesmas métricas, independentemente do dispositivo. Para custo, identificar máquina e backend em cada linha, separar treino de geração e evitar uma classificação única de velocidade baseada em CPU local versus GPU do Colab. Se a pergunta experimental incluir aceleração por GPU, implementar e medir uma variante do CA como estudo próprio; isso exigiria verificar equivalência de resultados e medir também transferências e sincronização.

Conectividade, componentes e ocupação têm prioridade na avaliação estrutural. A transformada de distância ao sólido descreve o espaço livre; seus valores dependem de resolução, espaçamento e bordas, e não validam a largura de todos os túneis. Ramificação, tortuosidade e diversidade exigem definições e validação próprias. Volumes gerados usam `True = ar`, `False = sólido`, com eixos ZYX.

O contrato implementado em 02/11/2026 está em
[métricas estruturais](metricas-estruturais.md): conectividade 6 por padrão,
opção explícita de 26, distâncias entre centros com spacing ZYX e exterior
sólido nos volumes mistos. Nos casos totalmente sólido e totalmente aberto,
a EDT é ausente e a degeneração é registrada. Cada execução concluída ocupa
uma linha versionada no CSV central; mudanças de borda, resolução e contrato
impedem a comparação automática com valores históricos. A linha central da
branch experimental é uma base para futuros descritores de ramificação,
dependentes de validação da extração e da preservação de ciclos.

**Contrato do SDF sintético:** para um volume gerado com vazio conhecido, `SDF > 0` no interior do vazio, `SDF < 0` no exterior sólido e `SDF = 0` nos voxels de borda. A magnitude é a distância euclidiana ao voxel de borda mais próximo, em unidades de voxel, na grade ZYX. O protótipo da branch `CA` usa borda de seis vizinhos de face e coloca o zero no centro do voxel de borda. Registrar sinal, unidade, regra de borda e origem do volume com o campo. Não equiparar esse SDF às estatísticas já existentes de distância do vazio ao sólido: elas são outro descritor, sem sinal.

## 3. Extensões condicionadas e neurais

Na branch `CA`, um peso espacial já é somado à contagem de vizinhos em cada iteração. Testes mostram que peso zero reproduz o CA básico e rejeitam shape incompatível. O Random Walk do pacote é, desde 02/11/2026, o porte do random walk ponderado por waypoints do projeto base ([detalhes](random-walk.md)). Seu protótipo também gerava um SDF conforme o contrato de sinal e unidade acima; essa etapa ficou fora do pacote. Os waypoints foram posicionados à mão sobre cavernas reais no projeto base (Knotlow Cavern, Upper Long Churns e Odins Mine), e o random walk só dá a irregularidade do trajeto entre eles. Duas consequências: tratar essa caverna como controle totalmente independente de referência real seria impreciso, e métricas de semelhança do Random Walk medem em boa parte os waypoints, de modo que usar uma dessas cavernas como referência de avaliação seria vazamento. Para um experimento de CA guiado, definir guia procedural independente do scan de teste e condicionamento permitido explícito.

Está planejado ajustar geneticamente parâmetros de **CA e Random Walk**. Antes de executar a busca, definir limites e codificação de cada método, aptidão estrutural, orçamento comparável, sementes de ajuste e sementes reservadas de avaliação. No Random Walk, o C# do projeto base limita `weight` a [0,1; 1] e `k` e `spacer` a inteiros em [1, 30]; o gerador em Python aceita valores contínuos e fora dessas faixas, e uma busca fora delas deixaria de avaliar o algoritmo do projeto base. A decisão está pendente. Comparar o GA com busca simples de mesmo orçamento. Atribuir o custo da busca à otimização, não ao tempo de uma geração já parametrizada.

GAN e PCGRL ainda são interfaces sem geração funcional. Uma GAN requer volumes de treino semanticamente válidos; volumes sintéticos verificam a infraestrutura, sem comprovar aprendizado de cavernas reais. Para PCGRL, definir o MDP e iniciar com ambiente pequeno, conectividade e ocupação na recompensa, sem IoU contra o scan. Modelos prontos devem obedecer ao contrato de volume e separar treino de inferência.

## 4. Condição para revisitar o SDF real

Uma retomada futura exigiria superfície geometricamente aceita, tratamento documentado de entradas e regiões não observadas, classificação interior/exterior validada e unidade espacial conhecida. Distâncias à parede fornecem magnitude, mas não o sinal de um SDF. Sem isso, não se inferem `VOID/SOLID` reais nem IoU volumétrica da nuvem. Esta frente não bloqueia a comparação atual.

## 5. Vetorização da contagem de vizinhos no autômato celular

A contagem de vizinhos do autômato celular deixou de ser um laço tríplice em Python, que visitava célula por célula e somava o cubo 3×3×3 ao redor de cada uma, e passou a ser uma convolução do volume por um kernel 3×3×3 de uns (`scipy.ndimage.convolve`). A justificativa é de validade da comparação, não de conveniência: como o TCC mede desempenho computacional de métodos com e sem IA, e os métodos baseados em IA executam sobre bibliotecas compiladas e aceleradas por GPU, medir o autômato celular em Python interpretado faria os números descreverem a implementação em vez do algoritmo, enviesando a comparação contra o método não-IA. A operação é matematicamente a mesma — a soma da vizinhança de todas as células é, por definição, uma convolução —, com a diferença de que o percurso das vizinhanças passa a ocorrer em código compilado, de uma só vez, em vez de em laços interpretados. O tratamento de borda foi reexpresso como uma moldura de uma célula aplicada ao volume antes da convolução, o que faz os três modos (borda vazia, borda cheia e borda sorteada) percorrerem o mesmo caminho de código, em vez de virarem casos especiais dentro da contagem.

O ganho medido em volumes de 64³ foi de duas ordens de grandeza: de 2,67 s para 0,0064 s por iteração, entre 400 e 580 vezes mais rápido conforme a medição. Na prática isso muda o que é viável experimentalmente. Uma varredura completa das combinações de sensibilidade, tratamento de borda e número de iterações, que exigiria cerca de 12 horas de execução, passa a levar menos de dois minutos, o que dispensa paralelização e permite repetições suficientes para tratamento estatístico. Volumes de 128³, antes inviáveis a aproximadamente 25 s por iteração, passam a custar 0,045 s, ampliando a faixa de resolução que o trabalho pode investigar.

A equivalência entre as duas versões foi verificada e não é aproximada: os resultados são idênticos bit a bit em toda a faixa de sensibilidade (0 a 27), em volumes cúbicos e não cúbicos, e ao longo de múltiplas iterações. Dos 26 volumes já gerados e armazenados antes da mudança, 24 são reproduzidos exatamente pela nova implementação; as duas exceções usam borda sorteada, que nunca foi reproduzível, pois sorteia valores novos a cada execução — limitação que passa a estar documentada e que exclui esse modo de borda de comparações que exijam repetição idêntica. A verificação está fixada como teste automatizado, no qual o laço original é preservado como oráculo. Isso também resolve a medição de complexidade de implementação: ela continua sendo calculada sobre a versão em laço, que é a tradução literal da regra do autômato, de modo simétrico ao que se faz do lado da IA, onde se contabiliza a definição do modelo e não o código interno da biblioteca.

Ver [Orientação](../Orientacao-codex.md), tarefas de [Pablo](tarefas-pablo-reconstrucao-modelos.md) e de [Felipe](tarefas-felipe-sdf-ca.md).
