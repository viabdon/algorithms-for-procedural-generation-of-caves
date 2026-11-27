# Planos de recortes e reprodução

O acervo guarda 42 conjuntos de planos nas pastas em que foram usados.
São 36 em `crop_plans/` e seis em `experiments/`, com as versões de
Elaphes, Madeleine, Rupt du Puits e Vallorbe. Os JSONs históricos foram
preservados com seus parâmetros, polígonos, grades e diagnósticos de
planejamento. [Fluxo da Datastream](../../../docs/preparacao-volumes.md#propor-e-extrair-recortes-pela-linha-central)

| Arquivo | Conteúdo |
| --- | --- |
| `entrada.json` ou `plan.json` | Entrada do planejador ou manifesto da execução com fonte, grafo, parâmetros e estações escolhidas. |
| `crop.json` e variantes `crop_*.json` | Origem local, limites, grade ZYX, semente, planos transversais, polígonos das tampas e ajustes de cada versão. |
| `cobertura.json` | Ramos considerados e omitidos no planejamento complementar. |
| `centreline.npz` | Grafo de entrada para os planos de Indian Tunnel. A linha central exploratória do Elaphes está em `experiments/experiment_elaphes-meshing/`. |
| `docs/auditoria/gan/splits.json` dentro do experimento | Inventário local requerido para voxelizar recortes das cavernas fora dos folds históricos. |

Os PLYs extraídos, HTMLs, máscaras e volumes voxelizados são saídas
regeneráveis. Os três NPZ de linha central arquivados são entradas do
planejamento. Os planos que usam grafos oficiais esperam o par de arquivos
`*_nodes_from_LBC.txt` e `*_links_from_LBC.txt` no mesmo diretório.
Obtenha o LAS, F32 ou PLY da versão indicada e seus metadados. Para
Madeleine, Rupt du Puits e Vallorbe, use os nomes e DOI de versão
registrados no histórico. [Origem das nuvens](../../../docs/auditoria/README.md) ·
[Histórico de voxelização](../../../docs/auditoria/gan/historico-voxelizacao.md)

## Refazer um plano

1. Use o `entrada.json` associado. Quando só houver `plan.json`, copie o
   objeto `parameters` para um novo JSON de entrada. O `plan.json` completo
   é o resultado do planejamento.
2. Na cópia, aponte `source` e `centreline` para a nuvem e o grafo da sua
   máquina. Os caminhos absolutos nos arquivos preservam a procedência da
   execução antiga. Caminhos relativos são resolvidos a partir da pasta do
   JSON que os usa. Nas referências do Indian Tunnel, `IndianTunnel_cave`
   aparece em caminhos antigos que hoje podem corresponder a
   `IndianTunnel/Full` na organização do HD.
3. Na Datastream, use a opção **5** com uma pasta nova para reextrair os
   PLYs. Confira as estações e os contornos em relação ao `plan.json`
   arquivado. Para voxelizar uma versão arquivada, use seu `crop*.json`,
   com `source` apontando para o PLY correspondente e os caminhos de
   `leak_diagnostics` ajustados quando presentes. A opção **3** aceita uma
   configuração individual ou um diretório de recortes com `crop.json`.

A conferência deste acervo reextraiu os sete recortes de Rupt du Puits
com o LAS de 5 cm. O planejador reproduziu o manifesto, as seções e os
hashes SHA-256 dos sete PLYs.

Os seis planos experimentais gravaram resultados em um diretório de
execução próprio. A voxelização dessas versões usa esse diretório como
`repository` em `prepare_crop`, para ler o inventário local de partições.
No exemplo abaixo, substitua `EXECUCAO` pelo diretório com `entrada.json`
e informe o `crop.json` cujo PLY já foi extraído.

```python
from pathlib import Path
from cavegen.datastream.gallery_crop import prepare_crop, process_crop

crop = prepare_crop(Path('CAMINHO_DO_CROP_JSON'), repository=Path('EXECUCAO'))
process_crop(crop)
```

## Versões que dependem de preparo adicional

Alguns ensaios partem de uma amostra da nuvem, de um recorte anterior ou
de pontos acrescentados à parede. Nesses casos, refaça o preparo indicado
no histórico antes da voxelização. O plano arquiva a geometria escolhida.
Para reproduzir os resultados voxel a voxel, use a mesma variante da nuvem,
do grafo e dos insumos derivados. Exemplos são a cópia binária em float32
do PLY do Elaphes, a rotação de Indian Tunnel em `perfis_rotacao_16cm` e a
restauração de pontos de Cascade em `paredes_medidas_16cm`.
[Histórico dos ensaios e das transformações](../../../docs/auditoria/gan/historico-voxelizacao.md)

No fold cárstico, os recortes de Cascade no plano `contornos_16cm` usam
os `crop_contorno.json` da pasta `las5cm_16cm_rev`. O recorte
`ramo_001_008` de Archamps PreEtroiture usa a configuração de semente
arquivada em `experiments/planejamento_auto_16cm/config_sementes_originais/`
e o PLY do plano `ramos_cortes_16cm`. [Inventário do fold](../../../docs/relatorios/inventario-gan-holdout-carste.md)
