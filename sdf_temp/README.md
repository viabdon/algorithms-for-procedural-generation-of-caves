# sdf_temp — pipeline do SDF no Elaphes

Experimento para calcular o SDF da referência do Elaphes a partir da grade de
superfície. Cada etapa é um script que lê o npz da etapa anterior e grava o
seu npz e o seu plot.

```
entrada/elaphes_surface_64.npz          grade 64³ (depth, height, width), 1 = superfície observada
  -> remover_outlier.py                 zera voxels soltos (no próprio npz de entrada)
  -> inundacao.py                       flood fill: 0 vazio, 1 borda, 2 interno
       npz/elaphes_surface_64_inundacao.npz
```

Os links `file:///` abrem no navegador (cole na barra de endereço). As figuras
carregam o Plotly pela internet, então precisa estar online.

## Pastas

| pasta | conteúdo | no git |
|---|---|---|
| `entrada/` | npz base do Elaphes | não (vem do PLY em `data/`) |
| `npz/` | resultado de cada etapa | não (regenerado) |
| `plots/` | figura de cada etapa | não (regenerado) |
| `articles/` | artigos de base (EDT e FEED) | não (PDFs das editoras) |

## Etapas

### 0. Entrada e outlier

`remover_outlier.py` zera o voxel (13, 60, 31) do plot, o único da grade sem
nenhum dos 26 vizinhos cheios. Sobrescreve o npz de entrada e é idempotente.

- [elaphes_surface_64.html](file:///C:/Users/Felipe%20Cruz/Desktop/CESUPA/TCC/code/algorithms-for-procedural-generation-of-caves/sdf_temp/plots/elaphes_surface_64.html)

### 1. Inundação (flood fill)

Separa borda e interno pela conectividade com o lado de fora da grade.
Metodologia, resultados, limitações e a comparação com as abordagens
descartadas estão em [inundacao.md](inundacao.md).

- [elaphes_surface_64_inundacao.html](file:///C:/Users/Felipe%20Cruz/Desktop/CESUPA/TCC/code/algorithms-for-procedural-generation-of-caves/sdf_temp/plots/elaphes_surface_64_inundacao.html)

## Como regenerar

A entrada vem da voxelização do PLY (que fica em `data/`, fora do git), da
raiz do projeto:

```
uv run python -m cavegen.datastream.run_reference_voxelization --ply data/raw/elaphes/elaphes_cave.ply --output sdf_temp/entrada/elaphes_surface_64.npz --shape 64 64 64
```

Depois, as etapas na ordem:

```
uv run python sdf_temp/remover_outlier.py
uv run python sdf_temp/inundacao.py
```
