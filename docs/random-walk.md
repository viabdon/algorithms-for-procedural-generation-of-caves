# Random Walk ponderado do projeto base

**Estado verificado na branch `CA` em 02/11/2026; migração nos commits `216f38d` a `e121f44`.** O gerador de Random Walk do pacote é o random walk ponderado do TCC que serve de base (Gabriel Freitas, [3D-Cave-Generation](https://github.com/freitasga/3D-Cave-Generation), commit `7a6c617` de 06/12/2024), portado para Python em `src/cavegen/generators/random_walk/`. Ele substitui o random walk "bêbado" de 6 direções (`steps`, `brush_radius`) que existia em `src/cavegen/generators/random_walk.py` desde a estrutura inicial do projeto (`cab2d1e`).

O porte nasceu no protótipo `random_walk_temp/` (`101aa24`, `2cf8f8c`, `a58155e`) e foi migrado para o pacote sem mudança de lógica. Este documento reúne o conteúdo do README do protótipo, com comandos e caminhos atualizados. A pasta foi apagada; o histórico continua no Git.

O projeto base é um projeto **Unity (C#)**, não Python, e **não gera voxels**: ele gera uma malha de tubos em volta dos caminhos. Por isso a caminhada foi portada para Python e a malha foi trocada por uma voxelização direta.

```text
external/3D-Cave-Generation/.../SampleScene.unity    cena com os grafos de waypoints (fora do Git)
  -> exportar_cena.py   exporta uma vez os grafos para configs/random_walk/<caverna>.yaml
  -> cena.py            lê waypoints, ligações e parâmetros do YAML
  -> caminhada.py       random walk ponderado entre os waypoints ligados
       npz/<caverna>_seed001_caminhos.npz
  -> voxelizacao.py     escava um tubo em volta dos caminhos numa grade lado³
       npz/<caverna>_seed001_64_classificacao.npz      0 fora, 1 borda, 2 interno
  -> generator.py       generate_random_walk(...) -> Volume3D (bool ZYX, True = vazio)
       npz/<caverna>_seed001_64_volume.npz
```

`plot.py` desenha os caminhos sobre os waypoints. A etapa de SDF do protótipo (`sdf_caminhada.py`) **não** foi migrada; ver [SDF do Random Walk](#sdf-do-random-walk-adiado).

## Pastas

| pasta | conteúdo | no Git |
|---|---|---|
| `configs/random_walk/` | grafo exportado de cada caverna (`example`, `knotlow_cavern`, `upper_long_churns`, `odins_mine`) | sim |
| `configs/algorithms/random_walk.yaml` | parâmetros padrão do gerador | sim |
| `external/3D-Cave-Generation/` | cópia do projeto base, sem o `.git` dele; só é necessária para refazer a exportação | não (é de outro autor) |
| `src/cavegen/generators/random_walk/npz/` | saída das linhas de comando | não (regenerado) |
| `src/cavegen/generators/random_walk/plots/` | figura de cada etapa e dos resultados do menu | não (regenerado) |
| `src/cavegen/generators/random_walk/results/` | `result_000.npz` gravados pelo menu: grade, classificação, caminhos e parâmetros | não (regenerado) |

## O projeto base

Na cena há quatro objetos com o `CaveGenerator`. Os waypoints foram postos à mão sobre os modelos FBX de cavernas reais (`Assets/Models/`), e cada um tem um `Linker` com a lista dos waypoints ligados a ele:

| caverna | waypoints | ligações | extensão x, y, z (unidades Unity) | radius |
|---|---|---|---|---|
| Example | 19 | 18 | 223 × 8 × 287 | 7,5 |
| Knotlow Cavern | 72 | 71 | 674 × 448 × 1935 | 7 |
| Upper Long Churns | 77 | 78 | 1425 × 101 × 882 | 7 |
| Odins Mine | 140 | 140 | 269 × 446 × 1267 | 7 |

Todas usam `weight = 1`, `k = 30`, `spacer = 5` e `segments = 6`. O Example é um caso plano de demonstração; as outras três seguem cavernas reais.

O random walk não é livre: ele anda **de um waypoint até outro**. A cada passo sorteia um dos 124 movimentos (−1, −0,5, 0, 0,5 e 1 em cada eixo, vezes `spacer`), com probabilidade proporcional a `exp(cos(ângulo até o destino) · weight · k)`. Com `weight · k = 30` o caminho vai quase reto ao destino, com pequenos desvios. Ou seja, a forma da caverna vem dos waypoints, e o random walk só dá a irregularidade do trajeto.

No C#, `weight` é `float` com `[Range(.1f, 1f)]`, e `k` e `spacer` são `int` com `[Range(1, 30)]`.

## Etapas

### 1. Exportação e leitura da cena (`exportar_cena.py`, `cena.py`)

`exportar_cena.py` é um script de uso único. Ele lê o YAML da cena Unity sem depender da Unity e grava um arquivo por caverna em `configs/random_walk/`: waypoints (nome e posição nos eixos da Unity, com y para cima), ligações por índice e parâmetros `weight`, `k`, `spacer`, `radius` e `segments`, além da origem (repositório, commit, cena e ordem na cena). Os objetos `nodes` de todas as cavernas estão na origem, sem rotação e com escala 1, então a posição local dos waypoints já é a do mundo; o script confere isso e para com erro se mudar.

Conferido na migração: o grafo de cada YAML é idêntico ao lido da cena nas quatro cavernas.

`cena.py` lê esses YAMLs. Daqui em diante o gerador não depende da Unity nem do projeto base.

### 2. Caminhada (`caminhada.py`)

Porte direto de `WeightedRandomWalk.cs` e `PathGenerator.cs`, incluindo o corte de laços (repetido duas vezes, como no original). Duas mudanças, as duas por reprodutibilidade:

- o sorteio usa `numpy_rng(seed)`; o original usa o `UnityEngine.Random` sem semente, então nunca gera duas vezes a mesma caverna;
- as contas são em `float64` (a Unity usa `float32`).

Há também uma trava de segurança: a caminhada levanta `RuntimeError` se passar de 100.000 pontos sem chegar ao destino (no original o `while` não tem limite). A trava não muda nenhuma caminhada que termina.

Conferido: mesma seed dá o mesmo caminho, e todo caminho começa no waypoint de origem e termina no de destino. Os passos do meio de cada caminho ficam entre 2,5 e 8,66 unidades (0,5 · 5 e √3 · 5). O **último** passo, que fecha no waypoint de destino, vai de ~0,1 até `spacer` (5) unidades: a caminhada para assim que fica a menos de `spacer` do destino e o original acrescenta o destino como último ponto. Medido nas quatro cavernas, seeds 1 a 3. É comportamento do original, não defeito do porte.

### 3. Voxelização (`voxelizacao.py`)

Em vez da malha de tubos, escava direto na grade uma cápsula de raio `r` em volta de cada trecho. Eixos: `depth = z`, `height = y` e `width = x` da Unity (o y da Unity é para cima). A caverna inteira é encaixada no cubo com a mesma escala nos três eixos, centralizada e com 2 voxels de folga (`MARGEM`). Por isso a grade precisa ser cúbica e com lado maior que 5.

A classificação auxiliar usa os códigos da inundação (0 fora, 1 borda, 2 interno), mas não precisa de flood fill: o tubo já é o vazio da caverna, então borda é o vazio que encosta em rocha por alguma face (fora da grade conta como rocha) e interno é o resto.

**Escala: 64³ com raio 1,5 voxel.** As cavernas reais têm até ~1.900 unidades e o tubo tem raio 7. No cubo 64³, o raio proporcional fica entre 0,2 e 0,3 voxel, abaixo do tamanho do voxel; com o mínimo que não parte o caminho (√3/2 ≈ 0,87) o túnel tem 1 voxel de largura e quase nenhum interno. O raio padrão ficou em 1,5 voxel: mesmo tamanho de grade das seeds e do Elaphes, ordem de grandeza de vazios do Elaphes e um pouco de interno para o SDF positivo. O custo é o túnel ficar ~5x mais grosso, em proporção, que o do original. Medido com a seed 1 (todas as opções deixam a caverna num pedaço só; cada célula é vazios, interno):

| caverna | 64³, r 0,87 | 64³, r 1,5 (padrão) | 64³, r 2 | 128³, r 2 |
|---|---|---|---|---|
| Knotlow Cavern | 245 vazios, 1 interno | 857, 172 | 1.400, 455 | 3.166, 1.030 |
| Odins Mine | 463, 1 | 1.268, 248 | 2.192, 781 | 4.948, 1.685 |
| Upper Long Churns | 288, 0 | 733, 122 | 1.321, 449 | 2.959, 992 |

Para comparar: o Elaphes em 64³ tem 1.075 voxels de casca (783 borda, 292 interno). Para o túnel ter a proporção do original sem forçar o raio, a grade precisaria de ~256³ (raio proporcional 0,9 a 1,4).

O raio muda pelo terceiro argumento da linha de comando, em voxels ou `proporcional` (o `radius` da cena convertido pela escala, com mínimo de √3/2).

### 4. Gerador (`generator.py`)

```python
generate_random_walk(shape=(64, 64, 64), seed=None, caverna="knotlow_cavern",
                     weight=None, k=None, spacer=None, raio_voxels=1.5) -> Volume3D
```

Devolve o `Volume3D` booleano ZYX com `True = vazio`, igual a `classificacao > 0`. `None` em `weight`, `k` ou `spacer` usa o valor da cena; `raio_voxels=None` usa o raio proporcional. `caverna` aceita o nome ou o apelido de um arquivo de `configs/random_walk/`. Os metadados gravam seed, caverna, parâmetros efetivos, raio em voxels, raio proporcional, escala, deslocamento, número de caminhos e de pontos. `RandomWalkGenerator` embrulha a mesma função com `generate(shape, seed)`.

Erros verificados: grade não cúbica e grade com lado ≤ 5 levantam `ValueError`.

## Validação da migração

- Os `.npz` da seed 1 das quatro cavernas (caminhos, inícios e classificação 64³) gerados pelo pacote são idênticos bit a bit aos do protótipo `random_walk_temp/`. O `Volume3D` é igual a `classificacao > 0`.
- `tests/test_random_walk.py` (17 testes) cobre a exportação dos grafos (idênticos à cena), os 124 movimentos, reprodutibilidade, origem e destino de cada caminho, tamanho dos passos, corte de laços, contrato do `Volume3D`, metadados no NPZ, encaixe e classificação. `tests/test_random_walk_fidelidade.py` (15 testes) usa traduções literais do C# como oráculo do sorteio e do corte de laços, e cobre a entrada do destino, a trava de passos, a troca de eixos, as trocas de parâmetro, o gerador global intocado, seed `np.int64` e grade pequena demais.
- A revisão confirmou a fidelidade ao protótipo e ao C#. Dois defeitos do código novo, ausentes no protótipo e sem efeito em 64³, foram corrigidos antes de fechar a migração: grade com lado ≤ 5 gerava escala zero ou negativa sem erro (agora `ValueError`), e seed `np.int64` quebrava o JSON dos metadados (agora é convertida para `int`).
- `tests/test_random_walk_menu.py` (6 testes) confere que o resultado gravado pelo menu é o mesmo volume de `generate_random_walk`, que as faixas do C# barram valores fora delas, que os dois plots são gerados e que lado menor que 6 é recusado.
- Suíte completa em `e121f44`: 99 testes; só falha `test_f32`, por `PermissionError` do Windows, falha anterior e sem relação com o Random Walk.

## SDF do Random Walk (adiado)

O protótipo tinha uma quarta etapa, `sdf_caminhada.py`, que importava as funções do `sdf_temp/sdf.py` (binarização da borda, EDT exata do scipy e sinal) e seguia o contrato de SDF sintético: interno positivo, externo negativo, borda 0, em voxels. Por decisão do Felipe, essa etapa **não** foi migrada e fica para depois; o script continua no histórico do Git (`a58155e`).

Diferença de significado registrada no protótipo: no Elaphes a malha é aberta nas entradas, a água da inundação entra nos túneis e o interno é quase só a espessura da parede. Aqui o interno é o miolo do túnel, o vazio de verdade da caverna.

O **peso 002** do CA foi gerado por essa etapa, antes da migração: Knotlow Cavern, seed 1, 64³, raio 1,5 (857 vazios, 172 internos, SDF de −48,76 a +1,41), importado pelo `pesos.py` do CA a partir de `random_walk_temp/npz/knotlow_cavern_seed001_64_sdf.npz`. A origem gravada no peso aponta para esse caminho, que não existe mais.

### Teste rápido do CA com o peso 002

Mesma configuração do Dia 8 do [diário](diario-naufrago.md) com o Elaphes (seed 1 do CA, borda zeros, 3 iterações), rodado em memória, sem gravar resultado. IoU contra os 857 vazios da Knotlow:

| s | vazios | IoU | cobre da Knotlow | vazios fora dela |
|---|---|---|---|---|
| 9 | 10.301 | 0,08 | 100% | 9.444 |
| 11 | 4.391 | 0,19 | 99% | 3.546 |
| 12 | 2.409 | 0,31 | 90% | 1.637 |
| 13 | 1.072 | 0,41 | 66% | 509 |
| 14 | 292 | 0,24 | 26% | 66 |
| 15 | 22 | 0,03 | 3% | 0 |

O peso guia o CA do mesmo jeito que o do Elaphes: a sensibilidade controla a espessura em volta do guia, e o melhor IoU também cai em s = 13 (0,41, contra 0,49 com o Elaphes). Limite: o IoU é medido contra a própria caverna do Random Walk que gerou o peso; ele mostra quanto o CA acompanha o guia, não semelhança com uma caverna real.

## Limites e pendências

- **Faixa dos parâmetros.** `generate_random_walk` aceita `weight`, `k` e `spacer` contínuos e fora das faixas do C# (`weight` em [0,1; 1], `k` e `spacer` inteiros em [1, 30]). Se o ajuste genético buscar nesses parâmetros, precisa respeitar essas faixas para o gerador continuar sendo o do projeto base. Decisão pendente com o Pablo.
- **Forma vem dos waypoints.** Os waypoints foram postos à mão sobre cavernas reais (Knotlow, Upper Long Churns, Odins Mine). Métricas de semelhança do Random Walk medem em boa parte os waypoints, e usar alguma dessas cavernas como referência de avaliação seria vazamento. Ver [ajustes metodológicos](methodology-adjustments.md#3-extensões-condicionadas-e-neurais).
- **Caverna do protocolo.** O padrão é `knotlow_cavern`; a caverna usada no benchmark precisa ser combinada com o Pablo.
- **Benchmark incompatível.** `src/cavegen/benchmark/run_generation_benchmark.py` não foi alterado e não importa (falta `generate_cellular_automata`, problema anterior à migração). `configs/experiments/baseline_32.yaml` ainda passa `steps` e `brush_radius`, que o gerador novo não aceita. Fica para a refatoração do benchmark planejada pelo Felipe. `configs/algorithms/random_walk.yaml` já traz os parâmetros novos.
- **Caminho dos grafos.** `configs/random_walk/` é encontrado por caminho relativo ao arquivo (`Path(__file__).parents[4]`): funciona rodando do repositório ou de instalação editável, não de um pacote instalado fora dele.
- **Escala.** O raio padrão de 1,5 voxel em 64³ deixa o túnel ~5x mais grosso, em proporção, que o original (ver a etapa 3).

## Menu

Como o do CA: gera uma caverna escolhendo caverna, seed, lado, raio e, opcionalmente, `weight`, `k` e `spacer` (limitados às faixas do Inspector no C#: `weight` 0,1 a 1, `k` e `spacer` 1 a 30), grava `results/result_000.npz` medindo com o `track_resources` e plota os caminhos ou a grade classificada.

```bash
uv run python -m cavegen.generators.random_walk.menu
uv run python -m cavegen.generators.random_walk.plot <resultado> [caminhos|classificacao]
```

## Como regenerar

Da raiz do projeto. As etapas da linha de comando rodam as quatro cavernas; `voxelizacao` lê os caminhos gravados por `caminhada`.

```bash
uv run python -m cavegen.generators.random_walk.caminhada [seed]
uv run python -m cavegen.generators.random_walk.voxelizacao [seed] [lado] [raio|proporcional]
uv run python -m cavegen.generators.random_walk.generator [seed] [lado] [raio|proporcional]
```

`generator` não depende das etapas anteriores: grava o `Volume3D` de cada caverna com `save_volume_npz`.

Para refazer a exportação dos grafos, com o projeto base em `external/3D-Cave-Generation`:

```bash
git clone --depth 1 https://github.com/freitasga/3D-Cave-Generation external/3D-Cave-Generation
rm -rf external/3D-Cave-Generation/.git
uv run python -m cavegen.generators.random_walk.exportar_cena
```

Ver [arquitetura](architecture.md), [roadmap](roadmap.md) e tarefas de [Felipe](tarefas-felipe-sdf-ca.md) e [Pablo](tarefas-pablo-reconstrucao-modelos.md).
