# Elaphes: amostragem espacial, normais e Screened Poisson

**Estado em 01/10/2026:** esta é a implementação experimental de
[`cavegen.meshing.poisson`](../../src/cavegen/meshing/poisson.py). As malhas
produzidas até agora são **candidatas não aceitas** para classificação
interior/exterior ou SDF. O [resumo teórico](../resumos-teoricos/fundamentos-screened-poisson.md)
explica o método independentemente do código.

## 1. Entrada e ordem das etapas

```text
PLY XYZ do Elaphes (94.465.067 pontos; sem normais)
  → leitura em batches e amostragem em bins XYZ regulares
  → pontos amostrados ainda em coordenadas XYZ do scan
  → estimação e orientação de normais com Open3D
  → Screened Poisson com octree adaptativa interna
  → malha OBJ candidata, densidades e diagnósticos
  → inspeção/validação antes de definir grade ZYX e flood fill
```

O [leitor PLY](../../src/cavegen/datastream/ply.py) já existente valida o
cabeçalho e transmite vértices XYZ em batches. O JSON
[`elaphes_xyz_bounds.json`](../../data/params/elaphes_xyz_bounds.json) fornece
limites XYZ, contagem, tamanho e hash registrado da fonte. O código confere
contagem e tamanho com o PLY, mas **não recalcula o SHA-256** em cada execução.
O PLY possui coordenadas e outros atributos, mas não propriedades de normal.
A unidade física dessas coordenadas ainda precisa ser confirmada; neste texto,
"unidade XYZ" significa a unidade original do arquivo.

O Poisson **não** consome a grade diagnóstica `32³` de `surface_voxels`, nem
converte XYZ para ZYX. A grade ZYX, com origem e espaçamento, será definida
depois que uma malha for aceita para a classificação e o SDF.

## 2. Batches e bins: duas divisões distintas

Um **batch** é um bloco temporário de leitura, por padrão com até 65.536
vértices. Seu tamanho afeta memória transitória e velocidade de leitura. O
último batch pode ser menor. Ele não define resolução espacial.

Um **bin** é uma célula de uma grade regular fixa em XYZ. O código usa os
limites globais do scan e escolhe uma quantidade `(Nx, Ny, Nz)` de células
cujo produto não excede `--max-points`. A busca usa uma largura física comum
aproximada nos três eixos, sem esticar cada eixo independentemente. Para cada
coordenada `p`, calcula um índice por eixo proporcional a `(p − min)/(max − min)`,
aplica `floor` e limita o índice ao último bin na borda máxima. Um eixo sem
extensão recebe um único bin. O identificador linear do bin permite acumular
dados de sucessivos batches.

Com `--max-points 100000`, o Elaphes gerou **`82 × 16 × 76 = 99.712` bins**,
de lado próximo a 1 unidade XYZ. Apenas **1.864 bins** receberam pontos; logo
o limite é para bins possíveis, não uma promessa de 100.000 pontos amostrados.
A grade é fixa durante a passagem e **não é uma octree**. A octree será
construída separadamente pelo Poisson após a amostragem.

### Regras de representação de um bin ocupado

| Regra | Ponto entregue ao Poisson | Dados adicionais | Risco principal |
| --- | --- | --- | --- |
| `first` (padrão) | Primeiro ponto do PLY que caiu no bin | Nenhuma dispersão calculada | Depende da ordem dos registros; não representa necessariamente o centro da superfície local |
| `centroid` | Média XYZ de todos os pontos no bin | Contagem, desvio padrão e variância por eixo | Pode cair entre paredes ou folhas de superfície distintas no mesmo bin |

Para `centroid`, o leitor acumula por bin `n`, `Σp` e `Σp²` em todos os batches.
Após a leitura, calcula `μ = Σp/n`, `v = max(Σp²/n − μ², 0)` e `σ = √v`, por
eixo. O `max` evita variância negativa por arredondamento numérico. A variância
e o desvio são **diagnósticos**; não orientam nem subdividem bins no código
atual. O centróide é ponderado pela quantidade de pontos observados, portanto
pela densidade do scan dentro do bin. Nenhuma regra usa sorteio: a seed
aleatória é `null` no JSON. A `first` depende da ordem do PLY; a `centroid`
depende dos pontos e dos limites. Ambas mantêm memória proporcional ao número
de bins, não aos 94 milhões de registros.

Uma dispersão alta pode indicar ruído, curvatura, variação ao longo de uma
parede ou duas superfícies próximas. Ela **não prova**, sozinha, que houve
mistura de paredes. Também não garante que a média melhore uma malha. No
Elaphes, o p95 do módulo do desvio XYZ por bin foi 0,490 unidade e o máximo
0,640. Esse módulo é `√(σx² + σy² + σz²)`; são valores a investigar em
relação ao bin de aproximadamente 1 unidade. A contagem máxima foi 746.314
pontos em um único bin.

## 3. Estimação local das normais

[`reconstruct_poisson`](../../src/cavegen/meshing/poisson.py) cria um
`open3d.geometry.PointCloud` com os pontos amostrados, já convertidos para
`float64` em memória. Em seguida chama:

```python
pcd.estimate_normals(
    o3d.geometry.KDTreeSearchParamKNN(knn=normal_neighbors)
)
```

Com `normal_neighbors=30`, o Open3D encontra os vizinhos mais próximos de
cada ponto, ajusta um plano local pela covariância das posições e escolhe o
autovetor da menor variação como linha normal. Por exemplo, pontos espalhados
quase só em X e Y definem uma normal aproximadamente paralela a Z. A chamada
usa o padrão `fast_normal_computation=True` do Open3D 0.20.0; essa opção é
mais rápida e pode ser menos estável numericamente que o caminho iterativo.
[API de `PointCloud.estimate_normals`](https://www.open3d.org/docs/latest/python_api/open3d.geometry.PointCloud.html).

`normal_neighbors` controla a escala do plano ajustado **na nuvem
amostrada**, não nos 94 milhões de pontos brutos. Um valor pequeno pode seguir
ruído; um valor grande pode atravessar a largura de um túnel, misturar paredes
opostas e suavizar detalhes. O mesmo `30` não corresponde a uma distância
física constante quando a densidade da amostra muda.

## 4. Orientação dos sentidos

Um plano local permite duas normais igualmente perpendiculares: `n` e `−n`.
Para tornar as escolhas coerentes entre vizinhos, o código chama
`pcd.orient_normals_consistent_tangent_plane(orientation_neighbors)`, com
`orientation_neighbors=30` por padrão. O Open3D propaga os sentidos usando
conexões entre planos locais por uma árvore geradora mínima; esta etapa procura
**consistência relativa** e não sabe onde fica o VOID da caverna.
[Tutorial de reconstrução do Open3D](https://www.open3d.org/docs/latest/tutorial/geometry/surface_reconstruction.html).

Opcionalmente, `--interior-seed-xyz X Y Z` informa uma coordenada sabidamente
no interior navegável. Para cada ponto `p` e normal `n`, o protótipo calcula
`n · (p − seed)`. Se a **mediana** desses produtos for negativa, inverte
**todas** as normais. Trata-se de uma heurística para escolher o sentido
dominante, não de uma correção individual por parede. Uma caverna longa,
curvada, não estrelada em relação à seed ou com componentes separados pode
violar essa hipótese. A seed é uma **posição geométrica**, não uma seed de
aleatoriedade. Nos dois ensaios do Elaphes ela foi `null`; a orientação
semântica ainda não foi validada.

## 5. Octree adaptativa e chamada do Screened Poisson

Depois das normais, o código executa
`open3d.geometry.TriangleMesh.create_from_point_cloud_poisson(pcd, depth=depth,
n_threads=threads)`. A função requer uma nuvem **orientada** e devolve
`(mesh, densities)`. A octree do reconstrutor divide recursivamente o cubo de
trabalho em oito filhos por nó, adaptando-se à distribuição das amostras. Com
`depth=7`, o limite teórico é `2^7 = 128` células por eixo do cubo, mas o
algoritmo pode parar antes em regiões pouco amostradas. Portanto, `depth` não
é o shape dos bins anteriores nem a resolução da futura grade SDF.
[API do Open3D 0.20](https://www.open3d.org/docs/latest/python_api/open3d.geometry.TriangleMesh.html),
[artigo de Kazhdan e Hoppe](https://www.cs.jhu.edu/~misha/MyPapers/ToG13.pdf).

| Parâmetro | Valor atual | Influência e cuidado |
| --- | --- | --- |
| `--depth` | 8 por padrão; 7 nos ensaios relatados | Teto de refinamento da octree; valores maiores podem preservar detalhe se houver amostras e normais suficientes, com maior custo de memória/tempo. Não preenchem observações ausentes. |
| `--threads` | 1 | Threads de CPU passadas ao Poisson; manter fixo ajuda a comparar execuções. Não solicita GPU. |
| `scale` do Open3D | 1,1, **não exposto no CLI** | Razão entre o cubo usado na reconstrução e o cubo que envolve as amostras. Afeta o domínio do solucionador; não é o padding da futura grade ZYX. |
| `width` do Open3D | 0, **não exposto** | Largura alvo da menor célula; a API a ignora quando `depth` é fornecido, como neste código. |
| `linear_fit` do Open3D | `False`, **não exposto** | Escolha de interpolação das posições dos vértices da isosuperfície. |
| `full_depth` do Open3D | 5, **não exposto** | Nível de profundidade completa antes do refinamento adaptativo; manter como padrão enquanto isolamos as variáveis principais. |
| `samples_per_node` do Open3D | 1,5, **não exposto** | Controla a adaptação à quantidade de amostras por nó; valores maiores tendem a produzir reconstrução mais suave em dados ruidosos. |
| `point_weight` do Open3D | 2,0, **não exposto** | Peso das restrições de interpolação dos pontos na formulação *screened*; alterar muda o equilíbrio entre aderência aos pontos e regularização. |

Os valores e significados de `scale`, `width`, `linear_fit`, `full_depth`,
`samples_per_node` e `point_weight` acima vêm da **API do Open3D 0.20.0** e,
para os dois últimos, também do [README do PoissonRecon original](https://github.com/mkazhdan/PoissonRecon/blob/master/README.md).
Como o protótipo não os passa explicitamente, mudar a versão da biblioteca
pode mudar esses padrões; a versão usada é registrada no JSON da execução.

## 6. O que salvamos e como julgamos uma candidata

`--sample-only` escreve um `.npz` com pontos XYZ, shape dos bins, limites,
contagem total, regra e hash **copiado do JSON da fonte**. Na regra `centroid`,
inclui contagem, desvio e variância por bin. O cache é verificado contra a
regra solicitada antes de uma reconstrução. O comando de malha grava `.obj`
para inspeção e eventual importação na Unity, além de `.obj.json` com versão
do Open3D, parâmetros, seed interior, tempos, limites XYZ, quantidade de
vértices/triângulos, componentes, arestas de borda e não manifold,
`is_watertight()` e mínimo/máximo das densidades devolvidas pelo Poisson.
O código **não salva as densidades por vértice** nem remove automaticamente
regiões de baixa densidade.

Uma malha aproximadamente fechada exige avaliação geométrica e semântica.
Menos arestas de borda ou menor distância aos pontos não provam que o volume
interior esteja correto. O Poisson pode extrapolar onde não houve observação;
um corte por densidade pode retirar superfícies reais pouco escaneadas ou abrir
novas bordas. Entradas reais da caverna e tampas artificiais precisam ser
identificadas antes do flood fill. [Open3D: densidade e extrapolação](https://www.open3d.org/docs/latest/tutorial/geometry/surface_reconstruction.html).

### Dois ensaios comparáveis do Elaphes

Ambos usaram os mesmos `82×16×76` bins, 1.864 representantes, `depth=7`,
`normal_neighbors=30`, `orientation_neighbors=30`, uma thread, Open3D 0.20.0
e nenhuma `interior_seed_xyz`. A única diferença planejada foi a regra de
representação por bin.

| Medida | `first` | `centroid` |
| --- | ---: | ---: |
| Tempo da passagem completa pelo PLY | 529 s | 881 s |
| Vértices / triângulos da malha | 6.173 / 12.212 | 6.467 / 12.783 |
| Arestas de borda | 186 | 215 |
| Arestas não manifold | 13 | 3 |
| Componentes de triângulos | 3 | 4 |
| `is_watertight()` | `False` | `False` |
| Menor Y da malha | −30,93 | −40,87 |

O menor Y observado no scan é −3,24. Ambas as malhas extrapolam muito nesse
eixo; a média dos bins não resolveu o problema. Numa comparação exploratória,
a distância p95 **dos 3.728 pontos da união das duas amostras até a malha**
foi 0,712 para `first` e 0,678 para `centroid`, em unidades XYZ. É uma medida
unilateral sobre representantes da nuvem, não Hausdorff95 do scan completo.
Ela não certifica fechamento nem forma navegável. A regra `centroid` reduziu
arestas não manifold, mas aumentou bordas abertas e extrapolação. Não há base
para aceitá-la como melhor por enquanto.

## 7. Parâmetros a estudar, em ordem

1. Confirmar unidade e orientação dos eixos XYZ e localizar uma posição
   interior confiável; inspecionar normais estimadas em regiões conhecidas.
2. Verificar a dispersão e a ocupação dos bins perto de paredes próximas,
   entradas e extremidades. Experimentar bins menores/maior `--max-points`
   mantendo o restante fixo. Dispersão alta pode orientar refinamento local
   futuro, ainda não implementado.
3. Variar `--normal-neighbors` e `--orientation-neighbors` separadamente;
   conferir se vizinhos cruzam paredes opostas e se a orientação propaga entre
   componentes corretos.
4. Só então comparar `--depth` e, se justificável, expor `scale`,
   `samples_per_node` ou `point_weight` em uma mudança registrada do código.
   Não atribuir melhora a um parâmetro quando vários foram alterados juntos.
5. Comparar cada malha com pontos observados, suporte/densidade, limites,
   bordas, componentes e entradas da caverna. Aprovar uma candidata antes de
   derivar o domínio ZYX e entregá-la ao flood fill.

## Referências

- [Open3D 0.20: `PointCloud.estimate_normals` e orientação](https://www.open3d.org/docs/latest/python_api/open3d.geometry.PointCloud.html).
- [Open3D 0.20: `TriangleMesh.create_from_point_cloud_poisson`](https://www.open3d.org/docs/latest/python_api/open3d.geometry.TriangleMesh.html).
- [Open3D: tutorial de reconstrução de superfície](https://www.open3d.org/docs/latest/tutorial/geometry/surface_reconstruction.html).
- [Kazhdan e Hoppe, *Screened Poisson Surface Reconstruction*](https://www.cs.jhu.edu/~misha/MyPapers/ToG13.pdf).
- [PoissonRecon: parâmetros originais](https://github.com/mkazhdan/PoissonRecon/blob/master/README.md).
