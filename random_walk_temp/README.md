# random_walk_temp — cavernas do random walk do projeto base

Experimento para gerar cavernas com o random walk ponderado do TCC que serve
de base (Gabriel Freitas, [3D-Cave-Generation](https://github.com/freitasga/3D-Cave-Generation),
commit `7a6c617` de 06/12/2024), voxelizar e calcular o SDF delas, para usar
como peso do CA além do Elaphes.

O projeto base é um projeto **Unity (C#)**, não Python, e **não gera voxels**:
ele gera uma malha de tubos em volta dos caminhos. Por isso a caminhada foi
portada para Python e a malha foi trocada por uma voxelização direta.

```
external/3D-Cave-Generation/.../SampleScene.unity   cena com os grafos de waypoints
  -> cena.py              lê os waypoints, as ligações e os parâmetros de cada caverna
  -> caminhada.py         random walk ponderado entre os waypoints ligados
       npz/<caverna>_seed001_caminhos.npz
  -> voxelizacao.py       escava um tubo em volta dos caminhos numa grade lado³
       npz/<caverna>_seed001_64_classificacao.npz      0 fora, 1 borda, 2 interno
  -> sdf_caminhada.py     mesmas funções do sdf_temp: EDT exata e sinal
       npz/<caverna>_seed001_64_sdf.npz
```

## Pastas

| pasta | conteúdo | no git |
|---|---|---|
| `../external/3D-Cave-Generation/` | cópia do projeto base, sem o `.git` dele | não (é de outro autor) |
| `npz/` | resultado de cada etapa | não (regenerado) |
| `plots/` | figura de cada etapa | não (regenerado) |

## O projeto base

Na cena há quatro objetos com o `CaveGenerator`. Os waypoints foram postos à
mão sobre os modelos FBX de cavernas reais (`Assets/Models/`), e cada um tem
um `Linker` com a lista dos waypoints ligados a ele:

| caverna | waypoints | ligações | extensão x, y, z (unidades Unity) | radius |
|---|---|---|---|---|
| Example | 19 | 18 | 223 × 8 × 287 | 7,5 |
| Knotlow Cavern | 72 | 71 | 674 × 448 × 1935 | 7 |
| Upper Long Churns | 77 | 78 | 1425 × 101 × 882 | 7 |
| Odins Mine | 140 | 140 | 269 × 446 × 1267 | 7 |

Todas usam `weight = 1`, `k = 30`, `spacer = 5` e `segments = 6`. O Example é
um caso plano de demonstração; as outras três seguem cavernas reais.

O random walk não é livre: ele anda **de um waypoint até outro**. A cada
passo sorteia um dos 124 movimentos (−1, −0,5, 0, 0,5 e 1 em cada eixo, vezes
`spacer`), com probabilidade proporcional a `exp(cos(ângulo até o destino) ·
weight · k)`. Com `weight · k = 30` o caminho vai quase reto ao destino, com
pequenos desvios. Ou seja, a forma da caverna vem dos waypoints, e o random
walk só dá a irregularidade do trajeto.

## Etapas

### 1. Cena (`cena.py`)

Lê o YAML da cena Unity sem depender da Unity. Os objetos `nodes` de todas as
cavernas estão na origem, sem rotação e com escala 1, então a posição local
dos waypoints já é a do mundo; o script confere isso e para com erro se mudar.

### 2. Caminhada (`caminhada.py`)

Porte direto de `WeightedRandomWalk.cs` e `PathGenerator.cs`, incluindo o
corte de laços (repetido duas vezes, como no original). Duas mudanças, as
duas por reprodutibilidade:

- o sorteio usa `numpy_rng(seed)`; o original usa o `UnityEngine.Random` sem
  semente, então nunca gera duas vezes a mesma caverna;
- as contas são em `float64` (a Unity usa `float32`).

Conferido: mesma seed dá o mesmo caminho, todo caminho começa no waypoint de
origem e termina no de destino, e os passos ficam entre 2,5 e 8,66 unidades
(0,5 · 5 e √3 · 5).

### 3. Voxelização (`voxelizacao.py`)

Em vez da malha de tubos, escava direto na grade uma cápsula de raio `r` em
volta de cada trecho. Eixos: `depth = z`, `height = y` e `width = x` da Unity
(o y da Unity é para cima). A caverna inteira é encaixada no cubo com a mesma
escala nos três eixos, centralizada e com 2 voxels de folga.

A classificação usa os códigos da inundação (0 fora, 1 borda, 2 interno), mas
não precisa de flood fill: o tubo já é o vazio da caverna, então borda é o
vazio que encosta em rocha e interno é o resto.

**Escala: 64³ com raio 1,5 voxel.** As cavernas reais têm até ~1.900
unidades e o tubo tem raio 7. No cubo 64³, o raio proporcional fica entre
0,2 e 0,3 voxel, abaixo do tamanho do voxel; com o mínimo que não parte o
caminho (√3/2 ≈ 0,87) o túnel tem 1 voxel de largura e quase nenhum interno.
O raio padrão ficou em 1,5 voxel: mesmo tamanho de grade das seeds e do
Elaphes, ordem de grandeza de vazios do Elaphes e um pouco de interno para o
SDF positivo. O custo é o túnel ficar ~5x mais grosso, em proporção, que o
do original. Medido com a seed 1 (todas as opções deixam a caverna num
pedaço só; cada célula é vazios, interno):

| caverna | 64³, r 0,87 | 64³, r 1,5 (padrão) | 64³, r 2 | 128³, r 2 |
|---|---|---|---|---|
| Knotlow Cavern | 245 vazios, 1 interno | 857, 172 | 1.400, 455 | 3.166, 1.030 |
| Odins Mine | 463, 1 | 1.268, 248 | 2.192, 781 | 4.948, 1.685 |
| Upper Long Churns | 288, 0 | 733, 122 | 1.321, 449 | 2.959, 992 |

Para comparar: o Elaphes em 64³ tem 1.075 voxels de casca (783 borda, 292
interno). Para o túnel ter a proporção do original sem forçar o raio, a grade
precisaria de ~256³ (raio proporcional 0,9 a 1,4).

O raio muda pelo terceiro argumento, em voxels ou `proporcional`:
`uv run python random_walk_temp/voxelizacao.py 1 64 2`.

### 4. SDF (`sdf_caminhada.py`)

Importa as funções do `sdf_temp/sdf.py` (binarização da borda, EDT exata do
scipy e sinal), então o resultado segue a mesma convenção: interno positivo,
externo negativo, borda 0, em voxels. O plot é o mesmo do SDF do Elaphes.

Diferença de significado: no Elaphes a malha é aberta nas entradas, a água da
inundação entra nos túneis e o interno é quase só a espessura da parede. Aqui
o interno é o miolo do túnel, o vazio de verdade da caverna.

O npz sai no formato que o `pesos.py` do CA importa:

```
uv run python -m cavegen.generators.cellular_automata.pesos random_walk_temp/npz/knotlow_cavern_seed001_64_sdf.npz
```

Assim entrou o **peso 002**: Knotlow Cavern, seed 1, 64³, raio 1,5 (857
vazios, 172 internos, SDF de −48,76 a +1,41).

### 5. Teste rápido do CA com o peso 002

Mesma configuração do Dia 8 com o Elaphes (seed 1 do CA, borda zeros, 3
iterações), rodado em memória, sem gravar resultado. IoU contra os 857
vazios da Knotlow:

| s | vazios | IoU | cobre da Knotlow | vazios fora dela |
|---|---|---|---|---|
| 9 | 10.301 | 0,08 | 100% | 9.444 |
| 11 | 4.391 | 0,19 | 99% | 3.546 |
| 12 | 2.409 | 0,31 | 90% | 1.637 |
| 13 | 1.072 | 0,41 | 66% | 509 |
| 14 | 292 | 0,24 | 26% | 66 |
| 15 | 22 | 0,03 | 3% | 0 |

O peso guia o CA do mesmo jeito que o do Elaphes: a sensibilidade controla a
espessura em volta do guia, e o melhor IoU também cai em s = 13 (0,41, contra
0,49 com o Elaphes).

## Como regenerar

Da raiz do projeto, com o projeto base em `external/3D-Cave-Generation`:

```
uv run python random_walk_temp/cena.py              # só confere a leitura
uv run python random_walk_temp/caminhada.py [seed]
uv run python random_walk_temp/voxelizacao.py [seed] [lado] [raio_em_voxels]
uv run python random_walk_temp/sdf_caminhada.py [seed] [lado]
```

Para baixar o projeto base de novo:

```
git clone --depth 1 https://github.com/freitasga/3D-Cave-Generation external/3D-Cave-Generation
rm -rf external/3D-Cave-Generation/.git
```
