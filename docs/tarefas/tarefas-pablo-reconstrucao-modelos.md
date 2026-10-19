# Tarefas do Pablo — malha, semântica e modelos neurais

**Metas indicativas revistas em 12/10/2026.** Esta frente produz a malha
reconstruída, especifica a semântica dos artefatos e prepara a avaliação e os
modelos neurais. Felipe implementa flood fill, SDF/TSDF e o CA condicionado em
paralelo; ver [`tarefas-felipe-sdf-ca.md`](tarefas-felipe-sdf-ca.md).
O estado da reconstrução e os parâmetros testados estão em
[`amostragem-normais-screened-poisson.md`](../metodologia/amostragem-normais-screened-poisson.md).

## Até 13/10 — Contrato e amostra de trabalho

- [ ] Definir com Felipe a região de interesse, transformação XYZ→ZYX,
  origem, espaçamento físico, shapes de teste, convenção `SDF < 0 = VOID`,
  banda `ε` de superfície, truncamento `τ` e máscara de validade/`UNKNOWN`.
- [x] Identificar no cabeçalho do PLY se há normais aproveitáveis: o Elaphes
  não as contém. O protótipo estima e orienta normais após amostragem espacial;
  a orientação global ainda precisa de revisão com uma semente interior.
- [x] Inventariar os arquivos brutos e metadados locais e conferir a
  [fonte oficial](https://dataset-dl.liris.cnrs.fr/elaphes-cave/) em busca de
  poses, estações e trajetórias. O HD contém apenas o PLY; os arquivos
  publicados não listam poses. Ver
  [inventário e limites da inspeção](../metodologia/metadados-elaphes-scanner.md).
- [x] Revisar cabeçalho e atributos do PLY, inclusive `pointsourceid`.
  Não há campos de posição do scanner; nas amostras verificadas o ID é `0`.
  Mesmo outros IDs não seriam coordenadas sem tabela de correspondência.
- [x] Registrar os arquivos e metadados examinados e concluir que **não há
  poses utilizáveis nos materiais disponíveis**. A unidade física e a
  transformação geográfica do PLY ainda não foram confirmadas; testar poses
  em piso/teto/paredes só será possível se surgir fonte adicional.
- [x] Inspecionar no navegador a última plotagem 3D da linha central podada:
  Pablo confirmou que todos os nós aparentam estar dentro do volume da nuvem
  e que as ramificações estão representadas corretamente. Essa é uma
  validação visual do grafo, registrada em
  [extração exploratória](../metodologia/linha-central-elaphes-exploracao.md).
- [x] Prototipar a associação de cada ponto a até dois ramos da linha central,
  com margem para custos próximos e região de bifurcação. Orientar por votos
  de nós interiores **explicitamente verificados**, sem fundir vetores de
  ramos discordantes. Ver [método e limites](../metodologia/orientacao-normais-linha-central.md).
- [x] Registrar **quais** pontos têm sentido incerto no NPZ/CSV e destacá-los
  no HTML com índice, normal e motivo. Implementar revisão pontual `keep`/`flip`
  com hash da amostra ordenada e um novo artefato; permitir que Poisson consuma
  diretamente as normais revisadas.
- [x] Executar uma primeira amostragem espacial rastreável do Elaphes com o novo comando
  `cavegen.meshing.poisson --sample-only`, revisando a densidade nas regiões
  finas. Os 245 voxels `32³` não entram no Poisson; o arquivo guarda XYZ do scan.
  Primeira passagem: 1.864 pontos retidos em bins `82×16×76`.

## Primeiras candidatas (09/10) e revisão pendente até 16/10

- [x] Implementar ou prototipar Screened Poisson como rota principal a partir
  de pontos orientados. Registrar amostragem, orientação, profundidade da
  octree, escala, densidade, tempo e memória.
- [ ] Refinar a amostra e a orientação das normais. A primeira candidata
  (`depth=7`, 1.864 pontos) ainda possui 186 arestas de borda, 13 arestas não
  manifold e extrapolação no eixo Y; não aceitá-la para flood fill.
- [x] Reamostrar o PLY com maior resolução e sem deixar os pontos altos
  definirem os bins: três pontos em Z≈69,78 foram separados para diagnóstico,
  e 22.368 representantes entraram no Poisson. Remover só o representante
  anômalo da amostra antiga não eliminou a extrapolação.
- [ ] Inspecionar a origem dos três pontos altos no PLY bruto antes de fixar
  uma regra de exclusão definitiva; guardar o critério e as contagens. A
  fonte oficial oferece versão sanitizada com três pontos isolados removidos;
  comparar coordenadas antes de afirmar que são os mesmos três registros.
- [ ] Comparar a nova malha global com o recorte denso X `[12,35]`, que tem
  bom suporte geométrico mas termina aberto no limite artificial X≈36,15 e
  ainda possui arestas não manifold. Não promover a malha do recorte a
  referência para SDF.
- [x] Comparar `first` e `centroid` nos mesmos bins do primeiro ensaio. A média
  reduziu arestas não manifold (13→3), mas aumentou bordas abertas (186→215)
  e a extrapolação em Y; nenhum resultado é watertight.
- [ ] Inspecionar bins de alta dispersão, testar resolução maior e orientação
  de normais com uma posição interior validada. Comparar suporte à nuvem e
  topologia antes de qualquer fechamento artificial.
- [ ] Inspecionar extrapolação em regiões pouco observadas, componentes,
  arestas de borda, manifoldness, self intersections, orientação e distância
  ponto–malha. Comparar a malha com o scan, não apenas com a grade `32³`.
- [ ] Localizar entradas reais, gaps e extremidades. Definir fechamento
  controlado e guardar separadamente as faces sintéticas; comunicar a Felipe
  onde o flood fill deverá receber tampas ou máscara `UNKNOWN`.
- [x] Repetir a linha central num recorte até X=45: a ramificação em X≈33 do
  corte curto não persistiu; a de X≈29,4 ficou como ponta terminal de uma
  aresta de 0,38 unidade. Registrar esses resultados sem inferir passagens.
- [x] Inspecionar o grafo ampliado em 3D: a linha aparece dentro do volume
  observado; Pablo confirmou a pequena ramificação real para cima em X≈30
  e a grande bifurcação em X≈42. Registrar essas observações como validação
  visual, distinta da futura classificação interior/exterior para SDF.
- [x] Medir pontas terminais e produzir poda exploratória em X≈42,
  preservando explicitamente o ramo real de X≈30 apesar de medir só 0,382
  unidade. A versão de inspeção tem 120 nós e cinco folhas.

**Decisão de escopo em 15/10/2026:** a orientação pela linha central foi
comparada com o baseline em três limiares de cosseno, mantendo amostra e
parâmetros do Poisson. Os resultados foram mistos e nenhuma malha ficou
fechada. A reconstrução por esse método não prosseguirá no TCC atual.
Conferir referências interiores em cortes, revisar a poda em X≈42 e validar
associações de parede, ramo e normal ficam como [pesquisa
futura](../metodologia/orientacao-normais-linha-central.md), fora das tarefas
com prazo desta frente.

**Hipótese de pesquisa futura, sem prazo neste TCC:** dividir a nuvem em
trechos sobrepostos, buscar parâmetros locais do Poisson e unir as malhas.
Uma bifurcação deve caber inteira em um trecho; a avaliação deve ocorrer
também após a união, sem confundir tampas artificiais dos recortes com uma
superfície real watertight. A candidata global densa ainda extrapola ao
limite cúbico e tem 175 arestas abertas e 27 não manifold; não há evidência
experimental de que a abordagem por trechos resolva esses defeitos.

## Até 20/10 — Decidir a reconstrução e integrar

- [ ] Testar sensibilidade do Poisson a normais, amostragem e profundidade.
  Caso falhe nos critérios, estudar Ball Pivoting e Alpha Shapes como fallbacks
  de **malha**, registrando por que cada candidato foi aceito ou rejeitado.
- [ ] Entregar malha candidata e metadados para o pipeline de classificação de
  Felipe. Conferir juntos em geometrias sintéticas e em região conhecida do
  Elaphes se o sinal do SDF corresponde ao vazio da caverna.
- [ ] Decidir com evidência quais células são `VOID`, `SURFACE`,
  `SOLID/EXTERIOR` e `UNKNOWN`, inclusive perto de tampas sintéticas.
  Formalizar que faces inventadas para fechamento não contam automaticamente
  como superfície observada nas métricas.

## Até 27/10 — Referências, avaliação e dados para aprendizagem

- [ ] Integrar e validar a referência completa: malha e SDF/TSDF produzidos
  por Felipe, rótulos categóricos, máscaras válidas e de tampas, dados de
  origem, parâmetros e transformação espacial.
- [ ] Fixar métricas de volume (IoU/Dice só em `VOID` válido), superfície
  (ASSD/HD95/Surface Dice com tolerância e máscara) e estrutura
  (conectividade, ocupação e largura), junto com casos de borda e unidades.
- [ ] Definir treino/validação/teste por caverna ou região separada com zona
  de exclusão entre patches vizinhos. Registrar quando os poucos scans só
  permitem estudo exploratório, sem alegação de generalização.

## Após validar a referência — redes neurais

- [ ] Auditar quantidade e diversidade de exemplos antes de escolher
  autoencoder, GAN ou outra arquitetura. Decidir se a rede prevê
  `VOID` binário, SDF/TSDF ou ambos, com a mesma convenção espacial.
- [ ] Preparar `Dataset`/`DataLoader` `(B, 1, D, H, W)`, metadados e uma
  conversão testada das saídas para as métricas; começar com treino pequeno
  reprodutível, sem confundir reconstrução com geração nova.
- [ ] Definir o MDP do PCGRL antes de PPO: estado, ação, transição, recompensa,
  término e custo da representação 3D. Extrair metas somente do treino; manter
  o scan de teste e sua IoU fora da recompensa.
- [ ] Comparar modelos neurais com Random Walk, CA básico e versões CA+SDF e
  CA+SDF+algoritmo genético, separando tempo de preparação da referência,
  otimização/treino e geração.

## Entrega para Felipe

A interface inicial suficiente é uma grade ZYX documentada, um sinal de SDF
acordado e exemplos sintéticos com interior conhecido. Assim ele pode validar
o SDF e condicionar o CA antes de existir malha real. Para integração com o
Elaphes, entregar uma malha candidata, transformações e indicação explícita
de entradas, tampas e regiões incertas.

Os HTMLs de inspeção podem ser regenerados com `uv run python
plots/plot_elaphes.py line` e `uv run python plots/plot_elaphes.py mesh`;
`--help` mostra entradas personalizadas e `--show` abre o navegador. A
visualização colorida por Z segue a convenção dos plots de CA de Felipe.
