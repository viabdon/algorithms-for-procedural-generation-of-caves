# sdf_temp — pipeline do SDF no Elaphes

Experimento para calcular o SDF da referência do Elaphes a partir da grade de
superfície. Cada etapa é um script que lê o npz da etapa anterior e grava o
seu npz e o seu plot.

```
entrada/elaphes_surface_64.npz          grade 64³ (depth, height, width), 1 = superfície observada
  -> remover_outlier.py                 zera voxels soltos (no próprio npz de entrada)
  -> inundacao.py                       flood fill: 0 vazio, 1 borda, 2 interno
       npz/elaphes_surface_64_inundacao.npz
  -> sdf.py                             tira o 2, binariza a borda, mede a distância
       npz/elaphes_surface_64_sdf.npz   e devolve o sinal: interno +, externo -
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

### 2. SDF

`sdf.py` lê a classificação da inundação e:

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

A EDT do scipy entra por enquanto. A implementação do artigo do Fuseiller
(`articles/`) pode substituir `distancia_ate_borda()`: qualquer EDT exata dá o
mesmo resultado, então o npz do scipy serve de referência para testar.

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
uv run python sdf_temp/sdf.py
```
