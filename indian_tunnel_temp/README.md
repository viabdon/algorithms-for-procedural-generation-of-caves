# indian_tunnel_temp — SDF do Indian Tunnel (NASA)

Experimento para levar a nuvem de pontos do Indian Tunnel, um tubo de lava do
NASA Planetary Pits and Caves Analog Dataset, pela mesma pipeline do Elaphes
(voxelização, inundação e SDF) e usar o SDF como peso do CA.

```
data/raw/nasa/indian_tunnel.f32         nuvem de pontos (era IndianTunnel_full_1x.f32)
  -> voxelizacao.py                     limites, giro, grade 64³ da superfície
       data/params/indian_tunnel_xyz_bounds.json
       npz/indian_tunnel_surface_64.npz                 1 = superfície observada
  -> inundacao_sdf.py                   funções do sdf_temp: inundação e SDF
       npz/indian_tunnel_surface_64_inundacao.npz      0 vazio, 1 borda, 2 interno
       npz/indian_tunnel_surface_64_sdf.npz            interno +, externo -
```

## Pastas

| pasta | conteúdo | no git |
|---|---|---|
| `../data/raw/nasa/` | a nuvem `.f32` (3,25 GB) | não |
| `../data/params/indian_tunnel_xyz_bounds.json` | limites da nuvem inteira e o sha256 dela | sim |
| `npz/` | resultado de cada etapa | não (regenerado) |
| `plots/` | figura da inundação e do SDF | não (regenerado) |

## A nuvem

116.205.392 pontos com 7 `float32` cada (x, y, z, NIR, R, G, B), o formato que
o `cavegen.datastream.f32` já lê por memmap. Só o XYZ entra. Extensão em
metros: x 76,5, y 170,4 e z 15,4. O z é a vertical: o túnel é comprido e
baixo.

## Etapas

### 1. Voxelização (`voxelizacao.py`)

- **Limites:** calculados uma vez sobre a nuvem inteira (~5 s) e gravados no
  JSON, no formato do `elaphes_xyz_bounds.json`.
- **Giro (x, y, z) → (x, z, −y):** a normalização manda o 2º eixo para o
  `height`, então o z vertical precisa estar ali para a altura ficar no
  `height` como no Elaphes. Com o sinal no −y é uma rotação de 90° em torno
  do x, sem espelhar a caverna.
- **Normalização:** a mesma do Elaphes (`normalize_xyz_to_zyx_indices`),
  escala única e centralizada. Fica 0,37 voxel por metro, ou seja **cada
  voxel tem ~2,7 m**.
- **Outlier:** fica só a maior componente (vizinhança de 26). Saiu um
  pedaço de 2 voxels (37 pontos) solto na ponta do túnel, o mesmo caso do
  voxel zerado à mão no Elaphes, agora feito pelo script.

Resultado: 1.145 voxels de superfície. O túnel ocupa `depth` 0–55,
`height` 29–34 (6 voxels de altura) e `width` 17–46. Os limites contam o
outlier, como no Elaphes, por isso o `depth` não chega a 63.

### 2. Inundação e SDF (`inundacao_sdf.py`)

Importa as funções do `sdf_temp/inundacao.py` e do `sdf_temp/sdf.py`, então
classificação, distância, sinal e plots seguem iguais aos do Elaphes.

| | Indian Tunnel 64³ | Elaphes 64³ |
|---|---|---|
| borda (1) | 978 | 783 |
| interno (2) | 265 (98 eram buracos fechados) | 292 |
| SDF | −48,02 a +2,00 | −63,16 a +2,00 |

Os 98 buracos fechados são trechos do oco do túnel que a água não alcança:
com 6 voxels de altura, o teto e o chão ficam colados e o oco some em
partes.

- [indian_tunnel_surface_64_inundacao.html](file:///C:/Users/Felipe%20Cruz/Desktop/CESUPA/TCC/code/algorithms-for-procedural-generation-of-caves/indian_tunnel_temp/plots/indian_tunnel_surface_64_inundacao.html)
- [indian_tunnel_surface_64_sdf.html](file:///C:/Users/Felipe%20Cruz/Desktop/CESUPA/TCC/code/algorithms-for-procedural-generation-of-caves/indian_tunnel_temp/plots/indian_tunnel_surface_64_sdf.html)

### 3. Peso do CA

```
uv run python -m cavegen.generators.cellular_automata.pesos indian_tunnel_temp/npz/indian_tunnel_surface_64_sdf.npz
```

Assim entrou o **peso 003**: Indian Tunnel, 64³.

## Como regenerar

Da raiz do projeto, com a nuvem em `data/raw/nasa/indian_tunnel.f32`:

```
uv run python indian_tunnel_temp/voxelizacao.py [lado]
uv run python indian_tunnel_temp/inundacao_sdf.py [lado]
```

Se o JSON de limites já existe, a voxelização usa ele em vez de reler a
nuvem; apague o JSON se a nuvem mudar.
