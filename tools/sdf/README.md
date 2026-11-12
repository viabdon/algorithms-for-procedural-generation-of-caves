# tools/sdf — pipeline do SDF no Elaphes

Calcula o SDF de uma grade de superfície; sem argumento, a do Elaphes. O sinal
vem do flood fill, que é uma ferramenta à parte
([`tools/flood_fill`](../flood_fill/README.md)): o `sdf.py` chama a inundação
direto da grade e grava só o SDF e o plot dele.

```
data/processed/references/elaphes_surface_64.npz   grade 64³ (depth, height, width), 1 = superfície observada
  -> sdf.py
       1. tools/flood_fill: 0 vazio, 1 borda, 2 interno
       2. tira o 2, binariza a borda, mede a distância
       3. devolve o sinal: interno +, externo -
       npz/elaphes_surface_64_sdf.npz
```

Os links `file:///` abrem no navegador (cole na barra de endereço). As figuras
carregam o Plotly pela internet, então precisa estar online.

## Pastas

| pasta | conteúdo | no git |
|---|---|---|
| `../../data/processed/references/` | npz base do Elaphes (entrada) | não (vem do PLY em `data/raw`) |
| `npz/` | o SDF | não (regenerado) |
| `plots/` | figura do SDF | não (regenerado) |
| `articles/` | artigos de base (EDT e FEED) | não (PDFs das editoras) |

## Etapas

### 0. Entrada

O npz de entrada já está sem o outlier: o voxel (13, 60, 31) do plot, o único
da grade sem nenhum dos 26 vizinhos cheios, foi zerado uma vez por um script
avulso. O script saiu do projeto por ser um caso específico e fica no
histórico do git (commit `d20feaf`, `sdf_temp/remover_outlier.py`).

### 1. Inundação (flood fill)

Separa borda e interno pela conectividade com o lado de fora da grade. Fica em
[`tools/flood_fill`](../flood_fill/README.md), com a metodologia, os
resultados, as limitações e a comparação com as abordagens descartadas.

### 2. SDF

`sdf.py` classifica a grade com a inundação e:

1. tira os voxels 2 (interno) e binariza: só a borda (1) fica 1;
2. mede a distância euclidiana de cada voxel até o voxel de borda mais
   próximo (`scipy.ndimage.distance_transform_edt`, exata);
3. volta com o sinal pela máscara do interno guardada no passo 1.

| região | sinal | no Elaphes 64³ |
|---|---|---|
| interno (era 2) | positivo | 292 voxels, até +2,00 |
| borda (era 1) | 0 | 783 voxels |
| externo (água) | negativo | 261.069 voxels, até −63,16 |

A distância está em voxels. Como a superfície é o próprio voxel de borda, o
zero cai no centro dele, sem correção de meio voxel. O interno é fino (a
parede da caverna voxelizada tem poucos voxels de espessura), por isso o
máximo positivo é só 2.

**Sinal:** interno positivo, combinado para este experimento. O
`docs/architecture.md` usa o inverso (`SDF < 0` no `VOID`); para mudar, troque
`SINAL_INTERNO` para `-1`. O npz guarda a convenção usada no campo
`convencao`.

O npz traz `sdf` (`float32`), `borda` e `interno` (máscaras `uint8`),
`convencao` e `metadata`.

**Plot:** paleta Tropic do plotly, do verde-azulado (mais negativo) ao rosa
(mais positivo), esticada de `CORTE_NEGATIVO = -10` até o máximo (+2). O
branco do meio da paleta cai em −4, não no zero da borda: o externo de −1 a
−3 também sai rosado. A opacidade sobe em linha reta do corte (100%
transparente) até o valor mais positivo (opaco). Abaixo do corte o voxel nem
entra no plot: dos 262.144 voxels, ficam 28.321. Cada nível distinto do SDF
vira um trace (o plotly só aceita uma opacidade por trace); no Elaphes são 89
níveis.

- [elaphes_surface_64_sdf.html](file:///C:/Users/Felipe%20Cruz/Desktop/CESUPA/TCC/code/algorithms-for-procedural-generation-of-caves/tools/sdf/plots/elaphes_surface_64_sdf.html)

A EDT do scipy entra por enquanto. A implementação do artigo do Fuseiller
(`articles/`) pode substituir `distancia_ate_borda()`: qualquer EDT exata dá o
mesmo resultado, então o npz do scipy serve de referência para testar.

## Como regenerar

A entrada vem da voxelização do PLY (que fica em `data/`, fora do git), da
raiz do projeto:

```
uv run python -m cavegen.datastream.run_reference_voxelization --ply data/raw/elaphes/elaphes_cave.ply --output data/processed/references/elaphes_surface_64.npz --shape 64 64 64
```

A voxelização devolve o outlier: zere o índice (60, 31, 13) da grade
`surface_voxels` (o (13, 60, 31) do plot) antes de seguir.

Depois, o SDF (a inundação roda dentro dele):

```
uv run python -m tools.sdf.sdf [superficie.npz]
```

O plot da inundação sozinha sai com `uv run python -m tools.flood_fill.inundacao`.
