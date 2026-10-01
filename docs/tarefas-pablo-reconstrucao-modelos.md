# Tarefas do Pablo — malha, semântica e modelos neurais

**Metas indicativas a partir de 30/09/2026.** Esta frente produz a malha
reconstruída, especifica a semântica dos artefatos e prepara a avaliação e os
modelos neurais. Felipe implementa flood fill, SDF/TSDF e o CA condicionado em
paralelo; ver [`tarefas-felipe-sdf-ca.md`](tarefas-felipe-sdf-ca.md).

## Até 02/10 — Contrato e amostra de trabalho

- [ ] Definir com Felipe a região de interesse, transformação XYZ→ZYX,
  origem, espaçamento físico, shapes de teste, convenção `SDF < 0 = VOID`,
  banda `ε` de superfície, truncamento `τ` e máscara de validade/`UNKNOWN`.
- [ ] Identificar no cabeçalho do PLY se há normais aproveitáveis; o leitor
  atual usa apenas XYZ. Planejar leitura de atributos ou estimação/orientação
  de normais, mantendo memória controlada para 94.465.067 pontos.
- [ ] Preparar uma amostra espacial rastreável do Elaphes para prototipar a
  reconstrução. Não usar os 245 voxels `32³` como entrada do Poisson; preservar
  pontos em coordenadas contínuas e registrar origem e critério de amostragem.

## Até 07/10 — Primeira malha candidata

- [ ] Implementar ou prototipar Screened Poisson como rota principal a partir
  de pontos orientados. Registrar amostragem, orientação, profundidade da
  octree, escala, densidade, tempo e memória.
- [ ] Inspecionar extrapolação em regiões pouco observadas, componentes,
  arestas de borda, manifoldness, self intersections, orientação e distância
  ponto–malha. Comparar a malha com o scan, não apenas com a grade `32³`.
- [ ] Localizar entradas reais, gaps e extremidades. Definir fechamento
  controlado e guardar separadamente as faces sintéticas; comunicar a Felipe
  onde o flood fill deverá receber tampas ou máscara `UNKNOWN`.

## Até 13/10 — Decidir a reconstrução e integrar

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

## Até 20/10 — Referências, avaliação e dados para aprendizagem

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
