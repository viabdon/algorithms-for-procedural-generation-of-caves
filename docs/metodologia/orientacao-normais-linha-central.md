# Orientação experimental de normais com a linha central

**Estado em 15/10/2026.** Há código e artefatos diagnósticos para o recorte
X `[12,45]` do Elaphes. Ainda **não há posições interiores validadas em
cortes**. Por isso, o primeiro processamento marcou os **20.274 pontos como
incertos**. A linha central visualmente plausível não fornece, sozinha, o
interior, o sinal do SDF ou uma malha aceita. A comparação posterior de
limiares de cosseno também não demonstrou uma reconstrução utilizável. A
decisão de escopo está registrada ao final deste documento.

## O que esta etapa tenta resolver

A estimação com 30 vizinhos calcula a direção perpendicular à superfície,
mas cada normal pode apontar para um de dois lados. A orientação por plano
tangente do Open3D busca coerência entre vizinhos; ela não conhece o lado
navegável da caverna. A antiga `interior_seed_xyz` decide apenas se **todas**
as normais serão invertidas. Em túneis curvos e bifurcações, uma única posição
pode não representar todos os trechos. O novo experimento usa **várias
posições interiores conferidas** e admite deixar o sentido de pontos
específicos sem decisão.

## Da linha aos candidatos de cada ponto

1. Ler a amostra XYZ na ordem salva em `points_xyz` e a árvore da linha
   central em `nodes_xyz` e `edges`. A função `split_branches` separa a árvore
   em caminhos entre pontas e bifurcações. Ela não poda ramos curtos: o ramo
   real de X≈30 deve continuar representado.
2. Para cada ponto, projetá-lo nas arestas de cada ramo. Comparar a distância
   à projeção dividida por uma estimativa local do raio da passagem, obtida
   das distâncias entre nós e pontos amostrados próximos. Isso equilibra
   trechos com escalas distintas, mas **não é distância geodésica** nem prova
   que não há uma parede entre ponto e ramo.
3. Guardar o ramo de menor custo. Guardar também o segundo quando os custos
   relativos diferem em até `0,15` ou o ponto está perto de uma bifurcação,
   desde que ambos passem pelo custo máximo. Um ponto pode ficar sem ramo
   plausível. Em vez de fundir vetores de ramos distintos, o código conserva
   as duas hipóteses e testa seus votos separadamente.

Os limites `0,15`, raio de bifurcação e custo máximo são **heurísticas
provisórias**. Precisam ser comparados com cortes do scan, sobretudo em
passagens estreitas, superfícies próximas e na bifurcação X≈42.

## De referências verificadas ao sentido da normal

O arquivo de referências contém índices de nós do grafo e um campo
`validated_interior`. Um nó com valor `false` não participa da decisão. O
JSON registra o hash do grafo para impedir o uso de referências escolhidas
em outra versão da linha. Após inspecionar cada candidato em cortes de piso,
teto e paredes, o pesquisador pode marcá-lo como interior verificado.

Para cada ramo candidato de um ponto, o programa escolhe o nó **validado**
mais próximo ao longo do comprimento desse ramo. O vetor desse nó ao ponto
aponta aproximadamente para a parede. O produto escalar com a normal
estimada indica `+` se ela acompanha esse sentido ou `−` se aponta para o
lado oposto. Um voto é descartado quando a referência está distante ao longo
do ramo ou o vetor é quase tangente à normal. Dois ramos com votos opostos
marcam conflito; eles não são promediados.

Depois, pontos vizinhos formam trechos locais de superfície quando são
próximos, têm normais base coerentes, deslocamento aproximadamente tangente
e compartilham ao menos um ramo candidato. Esse agrupamento busca evitar que
o consenso atravesse uma passagem estreita e una paredes diferentes. Um
trecho recebe sinal apenas com votos suficientes (`≥3`) e concordância
ponderada (`≥0,8`). Uma análise PCA dos 30 vizinhos identifica normais
locais instáveis; elas não votam no consenso. Pontos sem consenso, com
referências discordantes, conflito com o trecho ou perto de bifurcação sem
voto local continuam incertos. **Mesmo num trecho com consenso, um ponto sem
voto local válido permanece incerto**: uma referência numa ponta do túnel
não pode decidir o sentido de toda uma parede distante. O sinal decidido
pelo trecho inverte ou mantém a normal **por trecho**, nunca por média dos
vetores de dois ramos.

Esses filtros são conservadores, mas ainda podem errar. A segmentação usa
distância euclidiana e vizinhança da amostra, não topologia comprovada da
superfície. Uma malha Poisson posterior **não** transforma referências
provisórias em verdades de campo.

## Arquivos para inspecionar e corrigir

`normal_orientation prepare` salva três arquivos com o mesmo prefixo:

- `.npz`: coordenadas e normais na ordem da amostra, `uncertain_mask`, a lista
  exata `uncertain_indices`, ramos candidatos, custos, trecho, referências
  usadas, votos, qualidade local e pontos corrigidos manualmente.
- `.json`: hash da amostra e do grafo, parâmetros, versão do Open3D, contagens
  e proveniência. Não há sorteio nesta etapa (`random_seed: null`).
- `.uncertain.csv`: **uma linha para cada índice incerto**, coordenadas,
  normal atual, ramos candidatos e motivos. A coluna `action` aceita `keep`
  ou `flip`; vazia significa que o ponto continua incerto. O hash na primeira
  linha vincula a planilha às setas exatas da revisão. Não altere índices,
  coordenadas, normais ou essa primeira linha.

O comando gera também `.references.template.json`, com um nó **não
validado** como exemplo. O índice do nó aparece no hover da linha vermelha;
o índice do ponto aparece no hover do marcador rosa. São identificadores
diferentes. A identidade da amostra é um hash dos XYZ **ordenados**; plotar
uma nuvem em outra ordem causa erro, mesmo que contenha os mesmos pontos.

### Reproduzir o diagnóstico atual

Na raiz do projeto, com o ambiente `.venv`:

```bash
.venv/bin/python -m cavegen.meshing.normal_orientation prepare \
  --sample data/processed/elaphes_gallery_roi_x12_45.npz \
  --graph data/processed/elaphes_centreline_roi_x12_45_pruned_exploratory.npz \
  --output data/processed/elaphes_centreline_normals_review.npz

.venv/bin/python plots/plot_elaphes.py line \
  --cloud data/processed/elaphes_gallery_roi_x12_45.npz \
  --graph data/processed/elaphes_centreline_roi_x12_45_pruned_exploratory.npz \
  --orientation data/processed/elaphes_centreline_normals_review.npz \
  --highlight-uncertain --show-normals --max-normal-arrows 120 \
  --output results/figures/04_orientacao_normais/elaphes_centreline_normals_review.html
```

O fundo da nuvem é colorido por Z. Pontos rosa são incertos; pontos verdes
são decisões manuais já aplicadas. O hover mostra o índice **exato da
amostra**, a normal atual, ramos candidatos e motivos. As setas exibem uma
seleção determinística limitada por `--max-normal-arrows`; **todos** os
índices incertos permanecem no CSV e nos marcadores, mesmo quando o fundo
da nuvem usa `--max-points`. A legenda permite ocultar camadas para examinar
a geometria. O HTML é diagnóstico em Python; a visualização final de malhas
continua prevista para Unity.

Após conferir e aprovar alguns nós em cortes, criar uma cópia do template,
marcar `validated_interior: true` apenas para eles e executar `prepare` com
`--references caminho.json` e **outro** `--output`. Conferir o novo CSV/HTML.
Para uma correção pontual, preencher `action` na linha do índice visto no
HTML e aplicar:

```bash
.venv/bin/python -m cavegen.meshing.normal_orientation apply \
  --input data/processed/elaphes_centreline_normals_review.npz \
  --corrections data/processed/elaphes_centreline_normals_review.uncertain.csv \
  --output data/processed/elaphes_centreline_normals_corrected.npz
```

`keep` confirma a seta exibida; `flip` a inverte. O comando exige um novo
arquivo, rejeita decisões para índices já resolvidos e confere o hash e os
XYZ/normais da linha. A saída mantém a lista dos índices **ainda** incertos
para outra rodada de revisão. Uma decisão manual de sentido não corrige a
posição do ponto, a normal geométrica mal estimada nem uma associação errada
à superfície.

## Uso diagnóstico e requisitos para eventual retomada

O Poisson pode ler um NPZ de revisão por `--oriented-sample` para produzir
uma malha OBJ **diagnóstica** com as normais salvas. `--require-resolved`
impede a execução se ainda houver qualquer sentido incerto. Sem essa opção,
os sentidos não resolvidos mantêm a orientação base do Open3D; é apenas uma
comparação experimental. A saída registra hashes, contagens de incerteza e
métricas topológicas.

```bash
.venv/bin/python -m cavegen.meshing.poisson \
  --oriented-sample data/processed/elaphes_centreline_normals_corrected.npz \
  --output results/meshes/elaphes_normals_corrected_diagnostic.obj \
  --depth 8 --threads 1 --require-resolved
```

O comando acima só poderá passar por `--require-resolved` quando **todos** os
índices da amostra usada estiverem decididos. Ainda não é o caso do Elaphes.

Se uma pesquisa futura retomar esta abordagem, antes de promover o resultado
a uma candidata séria para SDF será necessário:

- Conferir nós interiores em cortes locais de piso, teto e paredes, incluindo
  extremidades e bifurcações; anotar evidência para cada nó escolhido.
- Comparar ramos/custos, normais e patches contra regiões conhecidas, medindo
  quantos pontos ficam sem ramo, ambíguos, discordantes ou incertos. Revisar
  casos de paredes próximas e ligações que atravessam paredes.
- Testar sensibilidade aos 30 vizinhos, margem de ambiguidade e limites do
  consenso; repetir com diferentes densidades e confrontar com um baseline
  Poisson de **mesma amostra e mesmos parâmetros**.
- Comparar suporte da malha à nuvem, bordas, componentes, não manifold,
  extrapolação, teto, entradas e tampas. Nenhuma dessas comparações já
  aprovou a malha do Elaphes ou o sinal de interior/exterior.

Esse módulo implementa uma **adaptação metodológica do projeto** posterior
à extração da linha. A extração LBC+MST foi inspirada em Racine et al.; a
associação de pontos, os votos de referências, a revisão de sentidos e o
CSV não são apresentados aqui como procedimentos publicados por eles.

## Experimento de cossenos com a linha central (15/10/2026)

### Por que e como foi feito

A revisão visual individual de 20.274 normais não é viável. Testamos se a
direção local linha central → ponto da parede pode propor automaticamente o
sentido de parte delas. Para cada ponto da amostra, projetamos sobre a aresta
mais próxima de cada ramo candidato e calculamos
`c = dot(normal_base, ponto - projeção) / |ponto - projeção|`. Portanto,
`c ≥ limiar` propõe `keep` e `c ≤ -limiar` propõe `flip`. Entre os dois
limites, a normal continua incerta. Comparamos `|c| ≥ 0,50`, `0,75` e `0,94`
(desvios máximos aproximados de 60°, 41,4° e 20°). **Essas são propostas
geométricas, não referências interiores validadas.**

A associação já existente limita a distância à linha a `2,5` raios locais e
retém um segundo ramo quando os custos são próximos ou há bifurcação. Se
existirem dois candidatos, ambos precisam ultrapassar o limiar com o mesmo
sinal. Pontos perto de bifurcações, com normal local instável, sem ramo
plausível ou com vetor radial nulo permanecem incertos. Os valores dos dois
cossenos, projeções, arestas, ramos, qualidade local e motivos são gravados
por índice da amostra nos NPZ; o CSV contém todos os índices ainda incertos.
O `automatic_sign` vale `+1` (`keep`), `-1` (`flip`) ou `0` (incerto). O
`review_sha256` protege também esses diagnósticos. A revisão manual e a
plotagem existentes aceitam esses arquivos.

O comando curto é:

```bash
.venv/bin/python menu_malhas.py cossenos \
  --orientacao data/processed/elaphes_centreline_normals_review.npz \
  --grafo data/processed/elaphes_centreline_roi_x12_45_pruned_exploratory.npz \
  --prefixo data/processed/elaphes_centreline_cosine_experiment_01
```

O prefixo deve ser novo: o comando não sobrescreve resultados. Ele produz
`_cos050.npz`, `_cos075.npz`, `_cos094.npz`, seus JSON/CSV e `_summary.json`.
O mesmo comando está na opção 8 do menu. `inspecionar ARQUIVO --indice N`
mostra o cosseno e a aresta para um ponto; `plotar --orientacao ARQUIVO`
gera o HTML correspondente. Para malhas, `malha --permitir-incertos` permite
uma comparação diagnóstica e conserva as normais base nos pontos incertos.
Um HTML do limiar `0,50` foi gerado em
`results/figures/04_orientacao_normais/elaphes_centreline_cosine_experiment_01_cos050.html`.

### O que foi observado no recorte Elaphes

Foram usados a amostra fixa de **20.274 pontos** (hash XYZ ordenado
`9b269cea…ec193`), o grafo podado de **120 nós e 119 arestas** (hash
`26e6c57f…c76da`) e as normais base do diagnóstico anterior. Não houve nova
amostragem nem sorteio. Os três arquivos preservam a mesma ordem dos pontos;
as normais base diferem do arquivo original no máximo por `2,22 × 10⁻¹⁶`
devido à renormalização. As decisões do limiar mais alto são subconjuntos
das decisões dos limiares menores.

| Cosseno mínimo em módulo | `keep` propostos | `flip` propostos | Incertos | Fração proposta |
| ---: | ---: | ---: | ---: | ---: |
| 0,50 | 3.786 | 8.149 | 8.339 | 58,9% |
| 0,75 | 2.469 | 6.222 | 11.583 | 42,9% |
| 0,94 | 709 | 2.238 | 17.327 | 14,5% |

Em **todos** os limiares, 4.758 pontos ficaram sem ramo plausível, 3.083
tinham custos de ramos próximos, 12 estavam perto de bifurcação e 2.285
tinham qualidade local de normal baixa. As contagens **se sobrepõem**. O
filtro de cosseno foi insuficiente em 2.583, 6.226 e 12.406 pontos,
respectivamente. Não apareceu conflito de sinais fortes entre dois ramos
nos candidatos desta amostra; o caso foi coberto em teste sintético, mas
esse zero não confirma a associação nas bifurcações reais. A diferença grande
entre 3.786 `keep` e 8.149 `flip` no limiar 0,50 sugere que a orientação
global inicial do Open3D diverge da direção radial proposta em muitas áreas;
sem cortes interiores, não sabemos se a proposta está certa.

### Malhas comparáveis, ainda diagnósticas

Reconstruímos o baseline e as três propostas com os mesmos 20.274 pontos,
Screened Poisson do Open3D, profundidade 8 e uma thread. Nos índices incertos,
as propostas usam a normal base. O baseline usa as normais base do arquivo
`_cos050.npz`; elas são numericamente equivalentes às do diagnóstico inicial.
As saídas estão em `results/meshes/elaphes_cosine_experiment_01_*.obj` com
JSON de métricas associado.

| Normais | Vértices | Faces | Arestas de borda | Arestas não manifold | Componentes | Distância vértice→amostra, P95 / P99 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Base | 49.303 | 98.617 | 207 | 29 | 14 | 1,122 / 9,795 |
| 0,50 | 50.216 | 100.608 | 128 | 57 | 22 | 0,911 / 6,572 |
| 0,75 | 54.117 | 108.416 | 200 | 82 | 35 | 1,108 / 13,245 |
| 0,94 | 55.512 | 111.400 | 202 | 105 | 19 | 0,955 / 8,591 |

A distância foi medida da posição de cada vértice da malha ao ponto mais
próximo da amostra fixa, nas unidades XYZ do scanner; não mede cobertura da
nuvem pela superfície nem compara topologia correta. Nenhuma malha foi
watertight. `0,50` reduziu bordas e P99, mas aumentou arestas não manifold e
componentes; portanto **nenhum limiar demonstrou melhora global ou uma
malha adequada ao SDF**. O limiar `0,75` teve P99 maior que o baseline.

Para aceitar um resultado em eventual retomada, seria necessário verificar
referências interiores em cortes locais, conferir as associações de paredes e
ramos nas bifurcações e revisar visualmente entradas, teto, extrapolação e
suporte da malha. A aparência da linha dentro da nuvem continua insuficiente
para determinar o sinal interior/exterior. Esta orientação por cossenos é uma
adaptação experimental nossa, não parte do método de Racine et al.

## Decisão de escopo e pesquisas futuras (15/10/2026)

**Resultado do ensaio:** a linha central permitiu registrar associações,
incertezas e propostas reproduzíveis de orientação, mas não validou o sentido
físico das normais nem produziu uma malha adequada à classificação
interior/exterior. As três reconstruções por cosseno tiveram resultados
mistos frente ao baseline; nenhuma ficou watertight. Isso não demonstra que
a abordagem seja impossível em geral, apenas que ela não resolveu a
reconstrução do Elaphes nas condições testadas.

**Decisão para o TCC atual:** em razão do tempo, do recorte e do foco da
pesquisa, não prosseguir com a reconstrução da malha por orientação baseada
na linha central. Os arquivos e comandos acima permanecem como registro
reproduzível do experimento, não como etapas pendentes da pipeline atual.
Esta decisão não equivale a aceitar outra malha do Elaphes como referência.

**Questões abertas para trabalhos futuros:** conferir nós interiores em
cortes locais, testar se cada ponto está associado à parede e ao ramo
corretos nas bifurcações, avaliar a orientação com referências verificadas
e medir seu efeito em malhas reconstruídas sob a mesma amostra e os mesmos
parâmetros. Qualquer conclusão sobre interior/exterior ainda dependeria de
validação geométrica e topológica independente.
