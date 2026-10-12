# Elaphes: inventário de metadados e posições do scanner

**Verificação em 12/10/2026.** Esta nota registra o alcance da inspeção dos
arquivos disponíveis localmente, do cabeçalho PLY e da
[página oficial do dataset](https://dataset-dl.liris.cnrs.fr/elaphes-cave/).
Ela não pressupõe acesso ao projeto de aquisição original.

| Fonte examinada | Conteúdo relevante | Conclusão para poses |
| --- | --- | --- |
| HD: `DATA/RAW/elaphes_cave.ply` | Único arquivo em `DATA/RAW`; PLY ASCII gerado pelo PDAL, 94.465.067 vértices, XYZ `float64` e atributos escalares LAS | Sem elemento, coluna ou comentário com XYZ do scanner, estação ou trajetória |
| `data/params/elaphes_xyz_bounds.json` | Hash, tamanho, número de pontos e limites XYZ calculados do PLY | Não contém poses; os limites descrevem a nuvem observada |
| Página oficial LIRIS | Oferece LAZ, LAS, PLY e 3D Tiles originais e sanitizados; documenta transformações de posicionamento para 3D Tiles | Não lista arquivo de trajetória, estações ou tabela que associe pontos a poses |

O cabeçalho PLY contém `pointsourceid` como `uint16`, mas esse valor é um
atributo escalar do ponto, **não** uma posição XYZ. Os primeiros 100.000
registros e seis amostras de 2.000 registros distribuídas ao longo do arquivo
(aproximadamente 10%, 25%, 50%, 75%, 90% e 99% dos bytes) apresentaram
`pointsourceid=0`. Essa amostragem não prova que todos os 94 milhões de
registros tenham o mesmo valor. Mesmo que existam outros IDs, faltaria uma
tabela de correspondência com coordenadas das estações para obter poses.
O cabeçalho também não declara normais nem tempo/ordem de aquisição.

A documentação oficial fornece versões **originais** (94.465.067 pontos) e
**sanitizadas** (94.465.064 pontos). Segundo a fonte, a sanitização remove
três pontos isolados que distorcem a caixa da nuvem. Isso coincide em número
com os três pontos Z>8 separados em nosso ensaio, mas a identidade exata
dos registros ainda requer comparação de coordenadas com a versão oficial.
Por ora, a exclusão do ensaio permanece um critério diagnóstico documentado.

**Conclusão operacional:** nos materiais examinados não há poses utilizáveis
para orientar normais. O PLY já está em XYZ local; a unidade física e uma
transformação geográfica aplicável a esse arquivo não foram confirmadas.
Se surgirem arquivos do projeto de aquisição ou poses dos responsáveis,
conferir sistema de coordenadas, unidades e correspondência com o PLY antes
de usá-los. Enquanto isso, avaliar posições interiores candidatas da linha
central em cortes de piso, teto, paredes e bifurcações.
