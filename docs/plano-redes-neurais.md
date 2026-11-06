# Plano de redes neurais: GAN, PCGRL e PCGARL

Atualização de 06/11/2026. Pablo conduz esta frente em paralelo à conclusão
dos clássicos e à coleta de métricas por Felipe. Os itens são propostas de
trabalho, não resultados experimentais. A especificação adversarial e os
limiares numéricos continuam abertos. A comparação final planejada usa 64³;
escalas menores são ensaios de desenvolvimento e não resultados comparáveis.

## Base e dependências

- O contrato comum é `Volume3D` em ZYX, booleano, `True = ar`; salvar NPZ com
  configuração e proveniência. `Volume3D` converte números para booleano:
  probabilidades devem ser limiarizadas explicitamente antes da conversão.
- `cavegen.metrics.evaluate_structure` fornece `structural-v1`: ocupação,
  componentes, fração na maior componente e EDT. Há testes e casos degenerados
  definidos em [métricas estruturais](metricas-estruturais.md). Não confundir
  conectividade por faces (6) com arestas/cantos (26).
- `benchmark/records.py` já cria linhas e acrescenta ao CSV, mas fixa backend
  CPU e repetição zero, exige cabeçalho idêntico e um escritor por vez. Antes
  de receber modelos, combinar evolução versionada do esquema com Felipe;
  não registrar execução GPU como CPU nem sobrescrever dados antigos.
- Benchmark/menu não importam em `a7dd1e7`: o CA não exporta
  `generate_cellular_automata`. Felipe cuidará da integração dos clássicos;
  ela não impede testar métricas e ambiente neural isoladamente.
- `gan_3d.py`, `pcgrl_3d.py` e `training/train_*.py` são placeholders; não há
  checkpoint neural treinado verificado. A IoU contra o Elaphes e seu SDF real
  não são critérios de avaliação, pois a superfície observada não fornece VOID.

## Primeiro ciclo: ambiente PCGRL pequeno

Proposta inicial para discussão, não protocolo final:

1. [ ] Definir MDP versionado: estado = grade de ar/sólido, posição do cursor e
   passos restantes; a observação deve conter toda informação que influencia
   a transição. Definir política de bordas e estado inicial com seed explícita.
2. [ ] Escolher ações discretas (mover em 6 direções, abrir, fechar e terminar)
   e o que acontece em borda, edição redundante e término antecipado. Alternativa:
   varredura automática do cursor; documentar o efeito sobre o espaço de ações.
3. [ ] Implementar ambiente pequeno, por exemplo 8³ ou 16³, com limite de passos;
   `reset(seed=...)` e `step` devem seguir a versão efetiva do Gymnasium,
   distinguindo término por objetivo de truncamento por orçamento.
4. [ ] Testar limites, reprodutibilidade, transições, espaços de observação e
   ação, término/truncamento e integração `Volume3D`/NPZ. Executar um episódio
   aleatório e um conjunto de exemplos geométricos conhecidos antes do PPO.
5. [ ] Medir custo por passo da avaliação estrutural; se for alto, usar medidas
   baratas ou avaliação periódica, validando equivalência. Não presumir que EDT
   completa a cada ação seja viável em 64³.
6. [ ] Treinar uma prova de conceito e comparar com política aleatória, mesmo
   estado inicial, ações, horizonte e conjunto de sementes de avaliação.
   Registrar curva de treino e avaliação em seeds separadas; salvar configuração,
   versão, checkpoint e estados aleatórios necessários para retomar.

### Métricas e recompensa de RL

Métricas de avaliação são descritivas; recompensa é uma escolha de projeto e
não deve ser confundida com qualidade independente. Compartilhar com Felipe
conectividade, unidade e casos degenerados antes de consolidar os resultados.

| Medida | Definição proposta | Uso e ressalvas |
| --- | --- | --- |
| Ocupação `p` | voxels abertos / total | Faixa alvo `[p_min,p_max]` ainda a escolher; registrar proporção, não só penalidade. |
| Maior componente `c` | voxels abertos da maior componente / abertos, conectividade 6 | `0` se sem ar; `1` também pode ocorrer com um único voxel ou tudo aberto. |
| Componentes `n` | número de componentes de ar | Reportar isolamentos e tamanho; não interpretar contagem isolada como qualidade. |
| Degeneração | todo sólido ou todo ar | `structural-v1` marca ambos; proibir que ganhem recompensa por conectividade isolada. |
| EDT | distância ao sólido, conforme `structural-v1` | Descritiva; `None` nos casos degenerados, não é largura validada. |
| Atingibilidade | caminho entre entrada e saída previamente definidas | Proposta opcional; testar por busca em 6 vizinhos, reportando critério e distâncias. |
| Diversidade | distribuição entre volumes e duplicatas, em seeds reservadas | Definir representação e medidas antes de comparar; diferenças por deslocamento também influenciam distâncias. |

Potencial inicial sugerido: `F(s) = w_c*c - w_p*d(p,[p_min,p_max]) -
w_d*I(degenerado)`, onde `d = max(p_min-p, 0, p-p_max)` e `I` é 1 no caso
degenerado. Testar `r_t = F(s_{t+1}) - F(s_t) - custo_acao` e recompensa
terminal explícita caso necessária. Pesos, intervalo, custo, desconto e escala
são hipóteses: fixar após testes de sanidade e registrar; com desconto menor
que 1 essa diferença simples não garante preservação da política ótima.
Verificar exploits: todo sólido, todo ar, um voxel, ilhas, repetição sem efeito,
abrir/fechar em ciclos e parada prematura. Não declarar sucesso apenas por
retorno alto. Na avaliação relatar ocupação, componentes, proporção de volumes
válidos, alcance, diversidade, custo e dispersão, inclusive falhas.

## GAN: limites do problema e dados

- [ ] Inventariar fontes, semântica de ar/sólido, licença, quantidade de volumes
  independentes, resolução, eixos, parâmetros, sementes e procedência. Não usar
  a grade de parede do scan como se fosse vazio. Random Walk por waypoints tem
  dependência das cavernas de origem; tratar essa relação na separação dos dados.
- [ ] Definir unidade de independência (caverna/grafo/volume de origem); separar
  treino, validação e teste **antes** de extrair recortes ou aumentos. Seeds ou
  recortes sobrepostos de um mesmo grafo não são cavernas independentes.
- [ ] Se não houver dados válidos suficientes, executar apenas prova sintética:
  avaliar se a GAN imita a distribuição do gerador clássico, sem alegar que
  aprendeu a distribuição de cavernas reais. Comparar diretamente com o gerador
  que produziu os dados, inclusive custo de criar o dataset.
- [ ] Escolher arquitetura e resolução experimental após medir RAM/VRAM:
  começar pequeno (ex. 16³), lote e representação explícitos; 64³ é objetivo
  experimental e não garantia de viabilidade. Registrar tempo, pico de memória,
  limites de hardware, falhas e critério de interrupção; não inventar orçamento.
- [ ] Especificar entrada latente e domínio de saída do gerador, normalização,
  shape `(N,C,D,H,W)`, distribuição, pós-processamento e limiar fixado em
  validação, sem ajuste no teste. Salvar checkpoint, arquitetura e versão do
  conjunto; suportar `Volume3D` e seed para inferência reproduzível no ambiente.
- [ ] Verificar estabilidade, colapso de modos, duplicatas e memorização com
  vizinhos próximos entre dados e amostras; acompanhar diversidade, ocupação,
  conectividade e casos degenerados. Sem dados independentes, não declarar
  generalização. Reportar geração bruta e qualquer correção pós-processamento.
- [ ] Comparar distribuições em teste reservado, não IoU célula a célula entre
  cavernas não alinhadas. Separar custo de dados, treino, inferência e avaliação.

Uma DCGAN 3D simples é candidata de infraestrutura; World-GAN é alternativa
baseada em um exemplo e arquitetura multiescala, com hipóteses diferentes.
Escolher após auditoria e teste de memória, não assumir equivalência das duas.

## PCGARL: definição a confirmar

O nome PCGARL precisa de referência e objetivo acordados. Uma hipótese é um
**gerador RL** que cria cavernas e um **solucionador** que tenta atravessá-las,
inspirado em ARLPCG; isso não é o mesmo que uma GAN. A adaptação abaixo é
proposta, não reprodução demonstrada do artigo.

- [ ] Definir entrada/saída, movimentos, colisões, limites de passos, observação
  e o que caracteriza navegação válida; usar busca em grafo como oráculo de
  viabilidade para um cenário sem física e comparar com o solver aprendido.
- [ ] Definir como equilibrar desafio e solucionabilidade: por exemplo, retorno
  que favoreça dificuldade apenas em cavernas verificadas alcançáveis. Falha do
  solver não prova impossibilidade; evitá-la como único sinal de dificuldade.
- [ ] Determinar alternância e orçamento de treino de gerador e solver, seeds,
  checkpoints e congelamento de versões para avaliação. Comparar PCGRL simples
  e adversarial com orçamento informado, política aleatória e solver fixo.
- [ ] Avaliar em seeds reservadas, com solver congelado e oráculo: taxa de
  mapas alcançáveis, sucesso do solver, comprimento de caminho, custo, diversidade
  e falhas. Relatar custos de ambos os agentes, inferência e teste separadamente.
- [ ] Só acoplar o adversário depois de o ambiente PCGRL, oráculo e métricas
  passarem nos testes; evoluir contrato e tabela em conjunto com Felipe.

## Integração experimental e sequência recomendada

1. [ ] Confirmar com Felipe o contrato do CSV, a identificação de algoritmo,
   checkpoint, dados/partições, seed de treino, seed de geração, repetição,
   resolução, backend, tempo por etapa e estado/causa de falha; preservar NPZ.
2. [ ] Avaliar volumes artificiais conhecidos usando `evaluate_structure`;
   documentar ocupação e conectividade comuns, sem duplicar métricas em RL.
3. [ ] Fechar o MDP e testes do ambiente pequeno; em paralelo auditar dados e
   limites de memória da GAN. A ordem pode mudar conforme prioridade do projeto.
4. [ ] Fazer provas pequenas, congelar protocolos de validação e depois escalar
   para 64³ somente quando viabilidade e custo estiverem medidos.
5. [ ] Entregar os registros brutos para a tabela de Felipe; documentar hardware,
   versões, número de seeds, seleção, incerteza e experimentos mal sucedidos.

## Referências de partida

- [Khalifa et al., PCGRL (2020)](https://arxiv.org/abs/2001.09212): geração como problema sequencial de RL.
- [Gisslén et al., ARLPCG (2021)](https://arxiv.org/abs/2103.04847): gerador e solucionador adversariais; há cópia na pasta externa de referências.
- [Awiszus et al., World-GAN (2021)](https://arxiv.org/abs/2106.10155): modelo voxel multiescala a partir de um exemplo.

Os artigos motivam alternativas; adaptação para cavernas, recompensa, dados,
escalabilidade e critérios quantitativos ainda exigem pesquisa e validação.
