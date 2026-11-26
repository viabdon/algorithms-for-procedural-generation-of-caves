# Histórico da voxelização de recortes para a GAN

O relatório técnico reúne o fluxo completo, o significado de cada
intervenção e as verificações pendentes.
[Relatório de voxelização](relatorio-voxelizacao.md)

A unidade independente do fold `holdout_indian_tunnel` é a caverna.
Archamps e Cascade de Môtiers entram no treino, Markov Spodmol na
validação e Indian Tunnel no teste. PreEtroiture e PostEtroiture pertencem
a Archamps. As variantes de densidade, estação de corte e escala são
observações relacionadas da mesma caverna.

## Por que a preparação mudou

A [auditoria dos volumes globais](README.md#conclusão-da-auditoria)
encontrou interiores muito pequenos ou fragmentados depois de
normalizar a nuvem inteira para 64³. O trabalho passou a delimitar
trechos pela linha central, preservar a escala física e rasterizar
separadamente a superfície observada, as tampas e o ar inferido. Os
recortes conservam os sistemas de coordenadas, as origens e as
transformações aplicadas a cada fonte.

O [guia da Datastream](../../preparacao-volumes.md) descreve as entradas
do menu e os contratos dos arquivos. O
[plano de reconstrução](../../plano-reconstrucao-secoes.md#evolução-do-piloto-em-archamps)
documenta as primeiras inspeções com evidências de Archamps.

## Do piloto aos lotes

| Rodada | Mudança e evidência | Resultado e limite |
| --- | --- | --- |
| Archamps PostEtroiture a 16 cm | LAS de 2 mm. No início do 001, o agrupamento de pontos da seção separou um aglomerado lateral. Em cortes compartilhados, foram testadas novas estações e ambos os recortes receberam a mesma seção. O percentil 75 define o raio por setor angular. | No plano revisado, o 001 saiu da barreira após mudança documentada da semente. Reparos locais fecharam 001, 002 e 003. O 004 fechou com as tampas de extremidade. |
| Fechamento sintético em Archamps | Depois de falhar o reparo local, o algoritmo testa o fechamento morfológico de menor raio que sela a semente, alcança ambas as extremidades e conserva as sementes internas verificadas. As células acrescentadas ficam em `auxiliary_caps`. | O 005 fechou com 69 voxels sintéticos e o 006 com 46. O flood fill externo reproduziu os seis interiores a 16 cm. A interpretação das aberturas cobertas continua pendente. |
| Primeiros lotes em outras cavernas | Cascade e Markov usaram LAS de 5 cm e grafos fornecidos. Indian Tunnel Full 10x usou grafo estimado. A Full 1x mais densa reutilizou o mesmo grafo. Mantiveram-se 16 cm e os dois contornos de extremidade como condição de entrada no flood fill. | Fecharam inicialmente 12/63 em Cascade, 10/65 em Markov e 1/32 em Indian Tunnel com cada variante Full. Em Indian, a Full 1x fechou o mesmo trecho da 10x. Maior densidade preservou aquele resultado, e 25 recortes seguiram sem contorno completo. |
| Revisão dos planos | Foram testadas estações próximas com contorno conectado e suporte angular. Os planos originais e revistos foram mantidos como versões distintas para auditar a mudança dos limites. | Fecharam 14/63 em Cascade, 11/65 em Markov e 2/32 em Indian Full 10x. As fugas com alerta de passagem próxima continuaram sem fechamento automático. |
| Recentragem no plano existente | Foram usadas as nuvens dos recortes adjacentes, com deslocamento do centro de ajuste no plano e sem mover a estação. O contorno precisou ter suporte em pelo menos 14 setores. | Cascade recuperou 11/19 contornos testados e mais dois volumes de 64³. Markov recuperou 4/18 e mais um volume de 64×74×64. Os 26 contornos de Indian ficaram pendentes. |
| Reextração com busca ampliada | A nuvem original foi consultada até 2,56 m de cada estação pendente, com recentragem de até 0,96 m. A mesma seção foi usada nos dois lados de cada corte e os PLYs afetados foram reextraídos. | Foram obtidos contornos para 19/19 cortes de Cascade, 12/18 de Markov e 2/26 de Indian. Fecharam novas versões de `ramo_027_002` de Cascade e `ramo_017_007` de Markov, já recuperados na etapa anterior. |
| Comparação de escala | Os mesmos PLYs, posições e contornos foram rasterizados diretamente a 28 cm. O raio máximo das tampas auxiliares foi de dois voxels. | A auditoria encontrou 34 volumes nativos de 64³ nas quatro cavernas, distribuídos em 19 de treino, 13 de validação e 2 de teste no fold inicial. Os dois volumes comparáveis de Indian obtiveram IoU física de cerca de 0,91. Algumas comparações em Cascade e Markov ficaram abaixo de 0,65. |
| Auditoria dos recortes para a GAN | A auditoria experimental passou a reler a superfície e as máscaras, repetir o flood fill e conferir o contato com as duas tampas. O manifesto registra os hashes e o loader exige o aceite explícito de ar candidato. | O manifesto de 28 cm permanece com status `gallery_proxy_pending_review`. A cobertura, a fidelidade geométrica e a escala do conjunto final continuam em aberto. |

Os lotes acima ficam detalhados na
[auditoria da GAN](README.md#voxelização-por-recortes-no-fold-inicial),
com contagens, nomes dos planos e observações de cobertura.

## Ramos omitidos no primeiro planejamento

O planejador priorizava os intervalos mais longos quando a quantidade de
recortes era limitada. A opção `passages` permite listar ramos pelos
índices originais do grafo e reservar ao menos um recorte para cada ramo
selecionado. A regra de oito voxels úteis após as margens foi mantida.
O `cobertura.json` dos planos complementares registra os ramos já
planejados, os selecionados e os que ficaram abaixo desse comprimento.

| Levantamento | Ramos planejados nesta rodada | Ramos abaixo do mínimo | Recortes tentados | Volumes fechados |
| --- | ---: | ---: | ---: | ---: |
| Archamps PreEtroiture, LAS de 5 cm | 3 | 2 | 21 | 4 |
| Cascade de Môtiers, LAS de 5 cm | 14 | 16 | 14 | 0 |
| Markov Spodmol, LAS de 5 cm | 15 | 52 | 15 | 0 |
| Indian Tunnel, Full 10x | 2 | 18 | 2 | 0 |

Archamps PreEtroiture usa a mesma partição de PostEtroiture. O primeiro
plano se chama `pre_5cm_16cm`. Os outros três levantamentos usam
`ramos_adicionais_16cm`. Nesse complemento, o planejamento chegou a
33 dos 49 ramos do grafo em Cascade, 30 dos 82 em Markov e 7 dos 25 em
Indian Tunnel. Planejar um ramo indica que ele entrou na extração.
A cobertura de interiores verificados depende do fechamento.

Na revisão `ramos_cortes_16cm`, a busca de estações com contornos
sustentados e a reextração fecharam mais três recortes de PreEtroiture
em 64³, `ramo_001_004`, `ramo_001_007` e `ramo_001_009`. Foram
recuperados contornos para 19 de 23 cortes pendentes no complemento
de Cascade e 4 de 26 em Markov. Foram reextraídos 11 e 3 recortes,
respectivamente. Todos ainda vazaram. Os quatro cortes adicionais de
Indian Tunnel continuaram sem contorno aceito.

Os sete interiores de PreEtroiture passaram na reprodução independente
e alcançam as duas tampas de extremidade. Cinco estão em 64³ e passam
na triagem numérica de volume e largura interna. Os outros dois
mantêm suas grades nativas, 64×75×64 e 64×64×70.

## Revisão de fugas próximas a outras passagens

O ensaio `pontos_medidos_16cm` examinou 61 recortes que o plano revisado
marcou como ambíguos. Para cada bin elegível com pelo menos dois pontos
na fonte dentro dos limites de seleção, a nuvem original foi consultada
para confirmar a atribuição ao mesmo ramo e ao mesmo intervalo do corte.
Em 36 recortes havia pelo menos um bin com apoio na nuvem original.
Depois de conferir a atribuição, restaram células com apoio de pontos
da mesma passagem em 17 casos.

A tentativa de restauração usou somente essas células medidas, com a
mesma busca de reparos e a checagem do componente de ar. Nenhum dos
61 recortes fechou com esse critério. O `restauracao.csv` de cada
levantamento registra as contagens antes e depois do filtro e o motivo
do desfecho. Esse resultado delimita o que se consegue recuperar com
pontos medidos já disponíveis. As aberturas próximas a possíveis
conexões continuam em revisão.

### Superfície corrigida com pontos medidos

O ensaio `paredes_medidas_16cm` manteve a caixa local e os dois
planos de cada recorte. A nuvem original foi consultada de novo sem o
filtro de atribuição ao ramo. Uma célula nova precisava conter pelo
menos dois pontos medidos. Primeiro foram testadas as células junto
à parede já rasterizada. Em seguida foram testadas todas as células
com esse apoio dentro da seleção.

O interior só avançou se tocasse as duas tampas, preservasse as
sementes internas já verificadas e deixasse fora os voxels da linha
central de outros ramos incluídos no domínio. A checagem desconsiderou
as amostras muito próximas do próprio eixo e dos planos de corte, onde
as linhas se encontram. Esse filtro usa o grafo como referência e
a investigação geométrica de possíveis conexões permanece necessária.

| Levantamento | Recortes examinados | Volumes fechados |
| --- | ---: | ---: |
| Archamps PreEtroiture | 13 | 0 |
| Cascade de Môtiers | 49 | 1 |
| Markov Spodmol | 46 | 0 |
| Indian Tunnel Full 10x | 8 | 0 |

Em Cascade, o `ramo_035_009` fechou em 64³ após acrescentar 235
pontos originais, que ocuparam 35 células de superfície. O resultado
reproduziu 14.304 voxels de ar com o flood fill externo. O PLY consolidado
guarda os pontos acrescentados. O `crop.json` registra a fonte, o
relatório anterior, o critério e as contagens. Cada lote tem
`recortes.csv` com o desfecho dos demais casos.

### Sementes, cortes compartilhados e junções

No ensaio `sementes_16cm`, a grade original de cada caso com semente
bloqueada foi classificada a partir do exterior. Uma semente alternativa
precisava ficar no único componente interno que tocasse ambas as tampas,
a até 0,64 m do eixo perto do meio do trecho. Nos 14 casos examinados
em Cascade, Markov e PreEtroiture, faltou o componente entre as duas
tampas. O `revisao.csv` de cada lote guarda o desfecho.

No ensaio `sem_corte_interno_16cm`, foram procurados grupos de dois
a quatro trechos consecutivos do mesmo ramo, com contornos nas
extremidades externas e uma tampa de separação ausente. Os pontos
foram reextraídos para o intervalo combinado. O único grupo que
cumpriu os critérios foi `ramo_065_002_a_003` de Markov e o flood
fill ainda vazou.

O ensaio `juncoes_16cm` delimitou cada junção uma única vez, com uma
tampa transversal por ramo incidente, entre 1,28 e 8 m do nó.
O ponto de partida foi a própria junção. A classificação foi testada
com os pontos atribuídos aos ramos incidentes e com os pontos
medidos dentro da caixa e dos planos. Sete junções em Cascade e
quatro em Markov tinham contornos para todas as saídas. Dessas onze,
dez ainda vazaram e uma teve a semente bloqueada nos dois modos.
As outras junções do inventário tinham pelo menos uma saída sem
contorno. As contagens e as condições de cada junção ficam em
`data/processed/experiments/juncoes_16cm/<caverna>/juncoes.csv`.

## Apoio das malhas e dos arquivos seccionais

Cascade, Markov e Archamps têm malhas oficiais trianguladas de 5 cm.
São produtos derivados do levantamento. O ensaio recortou os triângulos
com a caixa e os planos originais e marcou todas as células de 16 cm
que tocavam o triângulo. A superfície desse ensaio combina essas células
com a parede de pontos. O NPZ de máscaras guarda a contribuição exclusiva
da malha em `malha` e a parede original em `superficie_observada`.
Um fechamento só foi salvo após o flood fill independente, o contato
com as duas tampas e a verificação das sementes internas e linhas centrais
próximas.

A malha PreEtroiture chegou deslocada em X em relação ao LAS. Foi
aplicada uma translação de +100 m nesse eixo após comparar a malha
e os pontos. Na amostra de conferência, a translação ajustada
numericamente ficou a menos de 1 mm por eixo da translação aplicada,
e o percentil 95 da distância da malha ao LAS foi de cerca de 4 cm.
O `alinhamento.json` registra a fonte, o deslocamento aplicado e os
resíduos da comparação.

| Levantamento | Recortes testados com paredes da malha | Volumes fechados |
| --- | ---: | --- |
| Cascade de Môtiers | 58 | `ramo_027_003` e `ramo_035_008`, ambos 64³ |
| Markov Spodmol | 50 | `ramo_010_002`, 64×66×64 |
| Archamps PreEtroiture com malha alinhada | 14 | `ramo_002_001` e `ramo_002_002`, ambos 64³ |

Os resultados estão em `data/processed/experiments/malha_16cm` e
`malha_alinhada_16cm`. Em `sensibilidade.csv`, o limite é a distância
entre o centro da célula trazida pela malha e o centro da célula ocupada
mais próxima na nuvem original de 5 cm. Foram suficientes 16 cm em
Markov e no `ramo_002_001` de PreEtroiture, 32 cm nos dois recortes de
Cascade e 48 cm no `ramo_002_002` de PreEtroiture. O relatório
`malha_na_interface.csv` localiza as células trazidas pela malha que
fazem fronteira com o ar. A proximidade com os pontos e o fechamento
numérico ajudam a priorizar a revisão da superfície inferida.

O ensaio `contornos_malha_16cm` também recuperou tampas ao
intersectar a malha com o plano de corte original. Foi aceito apenas
um único contorno fechado envolvendo o eixo. Foram obtidos 10 de 41
contornos tentados em Cascade, 1 de 44 em Markov e 2 de 8 em
PreEtroiture. Seis recortes passaram a ter as duas tampas. Com a parede
da nuvem, todos ainda vazaram ou falharam antes da publicação.

Na rodada `contornos_e_paredes_malha_16cm`, os mesmos seis recortes
receberam também as células de parede dos triângulos. O
`ramo_017_002` de Cascade fechou em 64³ com 12.766 voxels de ar.
No teste de sensibilidade, limitar a contribuição à vizinhança de
até 96 cm da nuvem reabriu o trecho. Esse candidato depende de regiões
reconstruídas mais distantes dos pontos. As duas tampas e a parede do
ensaio precisam de revisão geométrica. Os seis volumes com apoio de
malha passaram na reprodução independente do flood fill.

O conjunto local de Indian Tunnel oferece nuvens parciais `Section1`
e `Section2` em F32. Nas amostras comparadas, as distâncias medianas
ao vizinho mais próximo de uma amostra da Full 10x foram 1,44 cm e
1,87 cm. Uma busca de coordenadas XYZ idênticas na Full 1x retornou
zero em 4.000 pontos sorteados de cada arquivo. Os recortes do ensaio
`secoes_medidas_16cm` usaram os pontos da Full 10x e dessas duas
seções, mantendo os planos, a caixa e a verificação das linhas
centrais próximas. Os oito recortes testados continuaram vazando.

## Perfis transversais e rotação horizontal no Indian Tunnel

Foram avaliadas 269 estações diagnósticas, espaçadas de 64 cm nos
ramos da linha central estimada. A soma dos ramos do grafo é cerca
de 188 m. Trata-se da extensão acumulada de um grafo, que pode
incluir ramificações e retornos. O plano principal tem 32 recortes.
Na nuvem integral Full 1x, os limites medidos em XYZ têm amplitudes
de 76,46 m, 170,45 m e 15,43 m, respectivamente.

Cada perfil projetou os pontos da Full 10x, com um representante
por célula de 8 cm, em uma grade transversal de 16 cm. Foram
testadas faixas de 16, 32, 48 e 64 cm a cada lado do plano.
A busca exigiu um único interior bidimensional de pelo menos 30
células, largura interna de pelo menos dois voxels na EDT e borda
do interior a até 2,4 m da linha central. Registrou-se se a seção
fechou com os pontos ou após fechamento morfológico de raio de um
ou dois voxels. O registro por estação está
em `data/processed/experiments/secoes_indian_16cm/`.

O ensaio mais estreito encontrou uma seção fechada. Na faixa de
64 cm, três estações consecutivas do ramo 002 sustentaram um recorte
de 33,12 a 34,40 m. O recorte `perfis_16cm/ramo_002_001` foi
reextraído da Full 10x e fechou em 66×64×81, com 20.713 voxels de ar e
39 voxels de tampa sintética.

Os pontos desse mesmo trecho, os planos e a linha central foram
girados horizontalmente em cerca de 21,6 graus e rasterizados de novo.
A escala e o eixo vertical foram preservados. As maiores amplitudes
no quadro girado foram 9,79 m na horizontal e 9,55 m na vertical,
com margem exterior na grade de 64³. A versão
`perfis_rotacao_16cm/ramo_002_001` fechou com 20.433 voxels de ar
e 46 voxels de tampa sintética. O flood fill externo reproduziu o
interior e a checagem do grafo deixou fora as linhas centrais externas
ao trecho. A matriz, a origem e os caminhos antes e depois da
transformação estão no `crop.json`. Em `comparacao_rotacao.json`,
a IoU física estimada por 64 amostras por voxel é cerca de 0,879.

O manifesto experimental em
`data/processed/experiments/gan_piloto_16cm/` inclui essa versão
e outros planos a 16 cm. Auditou 45 volumes e encontrou 35 em 64³
com triagem numérica compatível. No fold inicial são 26 para treino,
8 para validação e 1 para teste. A checagem de hashes e a separação
por caverna foram verificadas nos quatro folds. Um único trecho
de Indian em 64³ ainda oferece cobertura limitada para avaliar a
galeria. O manifesto está marcado como ar candidato, pendente de
revisão geométrica.

## Superfícies integrais dos levantamentos

Foram rasterizadas integralmente a 16 cm as nuvens selecionadas de
PreEtroiture, PostEtroiture, Cascade MainGallery, Markov MainGallery e
Indian Tunnel Full 1x. O NPZ esparso guarda as células observadas em
ZYX e as contagens de pontos. As células ausentes têm ocupação
desconhecida. O `resumo.json` de cada levantamento conserva os
limites, a origem e a escala. Os artefatos ficam em
`data/processed/experiments/superficies_16cm/`.
[Contagens e dimensões das grades](relatorio-voxelizacao.md#7-superfície-completa-e-interiores-candidatos)

## Como localizar o histórico por recorte

Dentro de `data/processed/crop_plans/`, o `plan.json` guarda a fonte
original, a linha central, a escala, as estações e os alertas. O
`crop.json` registra as duas seções, a seleção de pontos, a semente e a
grade. Sempre que um ensaio move estações e reextrai os pontos, ele usa
um identificador de plano distinto.

Dentro de `data/processed/reference_sections/`, o `lote.csv` aponta
para o volume salvo ou para o motivo da falha. O volume conserva a
superfície, o interior e as máscaras ao lado de `relatorio_volume/`.
As tentativas sem volume ficam em `<resolucao>_sem_volume/`.
`checks_replay.csv` registra a reprodução independente do resultado
salvo. Quando há fuga, os relatórios podem incluir `probes.csv`,
`paths.csv` e `bins.csv` com as evidências.

O diagnóstico começa pelo estágio que falhou. Uma tampa de extremidade
ausente exige revisar a estação ou o contorno. Uma semente bloqueada
exige voltar às fatias e confirmar a posição dentro da galeria. Para
um recorte que vaza mesmo com os planos temporários fechando as
extremidades, é preciso investigar a rota na nuvem e delimitar uma
possível abertura lateral antes de preencher a região.

## Automação de sementes e contornos

A rotina de voxelização passou a buscar outra posição quando a
semente cai na barreira. Ela testa posições próximas com o flood fill
a partir do exterior e pode usar uma janela local selada para
obter uma semente provisória para o diagnóstico. Após o reparo,
o componente precisa alcançar as duas tampas e coincidir com a
reclassificação a partir da borda. O relatório guarda a posição
original, a candidata e o desfecho. O ensaio de sementes anterior
continua como referência da condição sem reparo.

A revisão de contornos automatiza a comparação feita em Archamps
entre a faixa da nuvem original, os pontos atribuídos à passagem e os
pontos acima do raio mínimo. A opção de planejamento registra as
contagens por setor no `plan.json` e pode escolher outra estação
para uma tampa compartilhada. Os testes sintéticos cobrem uma abertura
que exige outro corte, um aglomerado separado que alongava o contorno
radial e o uso da mesma seção nos dois vizinhos. Os resultados dos
lotes reais foram preservados como referência para uma nova execução.
[Revisão de contornos](../../planejamento-recortes-voxelizacao.md#revisão-de-contornos-no-planejador) ·
[Busca automática da semente](../../planejamento-recortes-voxelizacao.md#busca-automática-quando-a-semente-cai-na-barreira)
