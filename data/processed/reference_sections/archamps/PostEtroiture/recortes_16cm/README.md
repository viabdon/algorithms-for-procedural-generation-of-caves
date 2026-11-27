# Archamps PostEtroiture a 16 cm

Seis recortes de referência para adaptar e comparar os algoritmos de Random
Walk e Cellular Automata. As grades mantêm a escala de **0,16 m por voxel**
e a ordem **ZYX**. Cada recorte tem sua própria pasta e resolução nativa.

| Recorte | Grade ZYX | Voxels de ar candidato | Reparo local | Tampa auxiliar |
| --- | --- | ---: | ---: | ---: |
| `ramo_001_001` | 64×78×64 | 6.659 | 3 | 0 |
| `ramo_001_002` | 64×64×64 | 9.893 | 2 | 0 |
| `ramo_001_003` | 64×64×64 | 7.490 | 2 | 0 |
| `ramo_001_004` | 64×64×64 | 8.139 | 0 | 0 |
| `ramo_001_005` | 64×64×68 | 12.455 | 0 | 69 |
| `ramo_001_006` | 64×64×64 | 8.022 | 0 | 46 |

- `interior.npz` guarda o ar candidato. Use
  `cavegen.datastream.voxel_io.load_volume_npz` para obter um
  `Volume3D` com `True` onde há ar inferido.
- `surface.npz` guarda a parede observada. Use
  `cavegen.datastream.surface_io.load_surface_npz`.
- `masks.npz` guarda `caps` com as duas tampas de extremidade,
  `repair` com o reparo local e `auxiliary_caps` com os fechamentos
  sintéticos. As três chaves estão disponíveis em todos os recortes.
- `relatorio_volume/checks_replay.csv` registra a reclassificação
  independente e o que acontece ao retirar cada tampa ou reparo.

As grades e as máscaras foram reproduzidas pelo flood fill a partir do
exterior, com contato do ar com as duas tampas. Os metadados dos NPZs
preservam a origem e a semente de cada grade. Para comparar resultados
entre algoritmos, use o mesmo recorte, escala e convenção de ocupação,
e registre a influência das tampas sintéticas. A validação geométrica
do ar inferido continua pendente.

## Como o piloto foi obtido

1. A nuvem PostEtroiture de 2 mm foi dividida em seis intervalos
   ao longo da linha central. Na tampa inicial do 001, a estimativa
   por componentes conectados separou a galeria de um aglomerado
   lateral, com o plano mantido na estação de 0,16 m.
2. A consulta à nuvem original recuperou a cobertura angular em
   outra estação nos limites 001/002 e 005/006. Os cortes passaram,
   respectivamente, de 8,76 m para 9,24 m e de 42,34 m para 43,62 m.
   Os dois recortes de cada par receberam o mesmo corte e foram
   reextraídos.
3. A semente do 001 saiu da parede após o reposicionamento para
   `[35.0406, 27.8859, -6.191]` no sistema local XYZ da nuvem do
   recorte. O flood fill exigiu três voxels de reparo local no 001,
   dois no 002 e dois no 003. O 004 fechou com as tampas de
   extremidade.
4. As fugas do 005 e do 006 exigiram fechamentos auxiliares. A busca
   encontrou 69 células com raio de dois voxels no 005 e 46 com
   raio de quatro no 006. A retirada da máscara sintética reabriu
   cada um desses recortes.

Os documentos do repositório registram as estações exatas, o
diagnóstico das fugas, a diferença entre tampas e reparos e o cálculo
da grade de 68 células em X no 005.
[Registro do piloto](../../../../../../docs/plano-reconstrucao-secoes.md#evolução-do-piloto-em-archamps) ·
[Planejamento dos recortes](../../../../../../docs/planejamento-recortes-voxelizacao.md#como-a-grade-cresce-ao-mover-um-corte) ·
[Relatório de voxelização](../../../../../../docs/auditoria/gan/relatorio-voxelizacao.md#5-archamps-do-primeiro-erro-ao-fechamento-do-piloto)

## Origem e licença

Fonte original de superfície. Racine, T., Trunz, C., Straubhaar, J. A.,
& Renard, P. (2025). *Archamps* (Version 1.0) [Data set]. UNINE data
service. [DOI 10.60544/gxkd-1r73](https://doi.org/10.60544/gxkd-1r73).

A preparação do TCC usou o LAS PostEtroiture de 2 mm, delimitou seis
trechos com a linha central do levantamento e rasterizou as paredes a
16 cm. As tampas, os reparos e a máscara de ar foram criados no TCC.
Os caminhos do computador foram retirados dos metadados desta cópia.

Os metadados do depósito SWISSUbase (projeto 21005, dataset 3065)
registram CC BY-SA 4.0. As contribuições desta adaptação são
distribuídas sob essa licença. O README da embalagem local registra
CC BY-NC 4.0. Esta entrega é para uso acadêmico e preserva o registro
da divergência. [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) ·
[CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/) ·
[Auditoria da origem](../../../../../../docs/auditoria/README.md#fontes-e-pontos-a-esclarecer)
