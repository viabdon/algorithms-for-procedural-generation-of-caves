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

Não é requisito portar o CA otimizado à GPU apenas porque os modelos neurais treinam no Colab. A comparação estrutural usa saídas `64³` e as mesmas métricas, independentemente do dispositivo. Para custo, identificar máquina e backend em cada linha, separar treino de geração e evitar uma classificação única de velocidade baseada em CPU local versus GPU do Colab. Se a pergunta experimental incluir aceleração por GPU, implementar e medir uma variante do CA como estudo próprio; isso exigiria verificar equivalência de resultados e medir também transferências e sincronização.

Conectividade, componentes e ocupação têm prioridade na avaliação estrutural. A transformada de distância ao sólido descreve o espaço livre; seus valores dependem de resolução, espaçamento e bordas, e não validam a largura de todos os túneis. Ramificação, tortuosidade e diversidade exigem definições e validação próprias. Volumes gerados usam `True = ar`, `False = sólido`, com eixos ZYX.

**Contrato do SDF sintético:** para um volume gerado com vazio conhecido, `SDF > 0` no interior do vazio, `SDF < 0` no exterior sólido e `SDF = 0` nos voxels de borda. A magnitude é a distância euclidiana ao voxel de borda mais próximo, em unidades de voxel, na grade ZYX. O protótipo da branch `CA` usa borda de seis vizinhos de face e coloca o zero no centro do voxel de borda. Registrar sinal, unidade, regra de borda e origem do volume com o campo. Não equiparar esse SDF às estatísticas já existentes de distância do vazio ao sólido: elas são outro descritor, sem sinal.

## 3. Extensões condicionadas e neurais

Na branch `CA`, um peso espacial já é somado à contagem de vizinhos em cada iteração. Testes mostram que peso zero reproduz o CA básico e rejeitam shape incompatível. O porte experimental de Random Walk ponderado por waypoints gera tubos voxelizados e um SDF conforme o contrato de sinal e unidade acima, mas seus waypoints foram posicionados sobre cavernas reais no projeto base; tratá-lo como controle totalmente independente de referência real seria impreciso. Para um experimento de CA guiado, definir guia procedural independente do scan de teste e condicionamento permitido explícito.

Está planejado ajustar geneticamente parâmetros de **CA e Random Walk**. Antes de executar a busca, definir limites e codificação de cada método, aptidão estrutural, orçamento comparável, sementes de ajuste e sementes reservadas de avaliação. Comparar o GA com busca simples de mesmo orçamento. Atribuir o custo da busca à otimização, não ao tempo de uma geração já parametrizada.

GAN e PCGRL ainda são interfaces sem geração funcional. Uma GAN requer volumes de treino semanticamente válidos; volumes sintéticos verificam a infraestrutura, sem comprovar aprendizado de cavernas reais. Para PCGRL, definir o MDP e iniciar com ambiente pequeno, conectividade e ocupação na recompensa, sem IoU contra o scan. Modelos prontos devem obedecer ao contrato de volume e separar treino de inferência.

## 4. Condição para revisitar o SDF real

Uma retomada futura exigiria superfície geometricamente aceita, tratamento documentado de entradas e regiões não observadas, classificação interior/exterior validada e unidade espacial conhecida. Distâncias à parede fornecem magnitude, mas não o sinal de um SDF. Sem isso, não se inferem `VOID/SOLID` reais nem IoU volumétrica da nuvem. Esta frente não bloqueia a comparação atual.

Ver [Orientação](../Orientacao-codex.md), tarefas de [Pablo](tarefas-pablo-reconstrucao-modelos.md) e de [Felipe](tarefas-felipe-sdf-ca.md).
