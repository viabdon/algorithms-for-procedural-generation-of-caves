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

### Resultado das 58 tentativas com as nuvens originais

A rodada usou os levantamentos originais a 16 cm e retomou os sete
planos que tinham ficado bloqueados pela ausência do HD. A revisão
de contornos buscou estações a até oito voxels (1,28 m) em cada
direção, quando havia espaço suficiente entre cortes. A busca de
sementes usou raio de quatro voxels (64 cm). A tabela usa o recorte
como unidade e conta uma vez cada caso do inventário pendente.

| Bloqueio inicial | Tentativas | Volumes reproduzidos pelo exterior | Sem volume |
| --- | ---: | ---: | ---: |
| Contorno de extremidade ausente | 44 | 0 | 44 |
| Semente na barreira | 14 | 1 | 13 |
| **Total** | **58** | **1** | **57** |

Nos 44 recortes sem contorno válido, 41 ficaram sem os dois
polígonos e três ficaram sem um deles. Ao reunir as extremidades
compartilhadas, são **67 cortes distintos**. A preparação interrompeu
esses recortes na validação do polígono, antes de rasterizar as
tampas ou iniciar o flood fill. As falhas se distribuem em dois
recortes de Cascade de Môtiers, 18 de Markov Spodmol e 24 do Indian
Tunnel.

#### O que limitou os 67 cortes

Para cada corte, foram conferidos os diagnósticos `section_reviews`
do plano novo. Um setor conta como sustentado quando tem pelo menos
dois pontos na etapa considerada. A tabela usa o melhor número de
setores obtido nas estações testadas em cada etapa. Cada corte
entrou uma vez, na primeira condição aplicável.

| Evidência nos diagnósticos | Cortes |
| --- | ---: |
| A faixa da nuvem original ficou abaixo de 14 setores sustentados mesmo antes de aplicar o raio mínimo. | 55 |
| A faixa original atingiu 14 setores, mas a seleção por ramo e estação ficou abaixo desse limite após o filtro de raio. | 6 |
| O conjunto filtrado atingiu 14 setores, mas o ajuste por um componente conectado da amostra ficou abaixo desse limite. | 3 |
| O ajuste conectado atingiu 14 setores, porém nenhuma estação passou na regra de contorno completo. | 2 |
| Houve contorno completo em uma estação que violava a distância mínima entre cortes. | 1 |

O raio mínimo, isoladamente, ficou sem caso nesta classificação.
Nos três casos abaixo do limite no ajuste conectado, os diagnósticos
registram a cobertura obtida, que depende do agrupamento e da
amostragem. Nos dois com 14 setores e ajuste rejeitado, o registro
por estação guarda a cobertura e a aprovação, com informação
insuficiente para separar lacunas consecutivas de componentes
concorrentes. Nos 55 cortes com cobertura angular insuficiente já
na fonte, a medição se refere às faixas e estações testadas. A
interpretação física depende da relação entre a nuvem e a linha
central e da inspeção da abertura.

Em Cascade, no início do `ramo_012_001`, a estação de 0,48 m
registrou suporte em 16 setores na fonte e 11 nos pontos filtrados.
No Indian Tunnel, o início do `ramo_006_001` teve contorno completo
a 1,44 m, mas a estação deixaria menos de 1,28 m até o corte vizinho.
[Regras de geração e espaçamento](../../planejamento-recortes-voxelizacao.md#revisão-de-contornos-no-planejador)

#### O que ocorreu depois da busca de semente

Cinco casos ficaram sem um voxel elegível no raio testado. Em oito,
o algoritmo encontrou uma semente provisória, mas o flood fill
continuou alcançando o exterior mesmo com as duas extremidades
cobertas por planos temporários. Os oito tinham alerta
`outra_passagem_ou_retorno_proximo`, que bloqueia o reparo local e
as tampas auxiliares. A origem física dessas fugas continua em
aberto.

O `ramo_001_008` de Archamps PreEtroiture fechou com deslocamento
de semente de 20,1 cm e 19 células de tampa auxiliar. O flood fill
externo reproduziu 7.499 voxels de ar e contato com ambas as
extremidades. Remover a tampa auxiliar reabriu a fuga.

Os arquivos locais `voxelizacao_44_contornos.json` e
`busca_sementes_originais.json`, em
`data/processed/experiments/planejamento_auto_16cm/`, identificam
cada recorte, sua configuração e o diagnóstico aplicável. O arquivo
`comparacao_fontes_originais.json` conserva os resultados dos sete
planos e as mudanças fora do inventário de 58 recortes.

### Busca conjunta de tampas perto de bifurcações

A rotina auxiliar usa o grafo para filtrar os recortes sem volume
antes de ler a nuvem. Ela ajusta seções pela tangente de cada ramo,
descarta conflitos entre polígonos e máscaras e testa um conjunto
limitado de combinações. Os volumes de junção são armazenados
separadamente dos recortes que acionaram o ensaio.
[Método e parâmetros da busca conjunta](../../planejamento-recortes-voxelizacao.md#busca-conjunta-de-tampas-em-bifurcações)

O inventário da rodada a 16 cm reuniu os 44 recortes sem contorno,
os 13 casos de semente ainda sem volume, os 93 com aviso de
passagem ambígua e os 17 que já tinham passado pela tentativa de
fechamento anterior. O inventário e o resultado por recorte e
junção ficam em `data/processed/experiments/juncoes_auto/`.

Dos **167 recortes** de entrada, **39** ficaram fora da busca
custosa pela distância ao nó mais próximo. Os demais apontaram
para **61 nós distintos**. Foram 62 avaliações por fonte e nó,
pois uma junção do Indian Tunnel entrou com as variantes Full
10x e Full 1x.

| Levantamento | Avaliações | Ramo sem tampa válida | Combinações sem fechamento | Fechou |
| --- | ---: | ---: | ---: | ---: |
| Cascade de Môtiers | 24 | 18 | 5 | 1 |
| Markov Spodmol | 28 | 24 | 4 | 0 |
| Archamps PreEtroiture | 2 | 2 | 0 | 0 |
| Indian Tunnel Full 10x | 7 | 7 | 0 | 0 |
| Indian Tunnel Full 1x | 1 | 1 | 0 | 0 |

Nas 68 combinações avaliadas em 3D, 39 foram descartadas porque
a barreira tocava a borda da grade, 28 vazaram e uma fechou.
Três recortes de entrada levaram à mesma junção salva. Os desfechos
originais desses recortes foram preservados. A checagem da
junção foi reproduzida pelos NPZs, com a máscara de cada tampa
rasterizada novamente a partir do polígono salvo.

A `juncao_023` de Cascade de Môtiers, com os ramos 14, 15 e 16,
havia vazado no ensaio anterior. As tampas estavam a
aproximadamente 5,33 m, 1,28 m e 1,28 m do nó. Na busca conjunta,
as distâncias escolhidas foram 1,28 m, 1,92 m e 1,92 m. Os
polígonos e os voxels das três tampas ficaram disjuntos. Na
grade ZYX de 43×46×52, o flood fill pelo exterior reproduziu
6.421 voxels de ar no mesmo componente, em contato com as
três tampas. A verificação foi numérica. A geometria inferida
permanece como referência candidata.

#### Pendências após a busca conjunta

O inventário contém **218 recortes**, incluindo os ramos adicionais e
contando cada recorte uma vez entre revisões. **51 têm alguma versão
fechada e 167 permanecem sem um volume do trecho original**. A junção
023 foi salva como um volume próprio. Os três recortes que acionaram
essa busca continuam na contagem das pendências.

| Bloqueio atual | Recortes | O que já foi tentado | Resultado da triagem de junções |
| --- | ---: | --- | --- |
| Falta contorno em uma ou ambas as extremidades | 44 | Comparação com a nuvem original, busca de estações, recentragem e ajuste de contorno por componente conectado. Ao fim, 41 ficaram sem as duas tampas e três sem uma. | 34 associados a junções sem volume. 10 fora da busca por distância ao nó. |
| Semente na barreira sem posição alternativa aceita | 5 | Classificação pelo exterior e busca em até quatro voxels por ar interno entre tampas ou por uma janela local fechada. | 4 associados a junções sem volume. 1 fora da busca por distância ao nó. |
| Fuga com alerta de passagem próxima ou retorno | 101 | Diagnóstico com planos temporários, busca da rota de fuga e consulta à nuvem original. Inclui os oito casos em que o reposicionamento da semente revelou uma fuga. O alerta bloqueou o reparo automático no recorte. | 87 associados a junções sem volume. 11 fora da busca por distância ao nó. 3 associados à mesma junção 023 salva. |
| Fuga persistente após a tentativa de tampa auxiliar | 17 | Reparo local e busca de tampa sintética com raio de até quatro voxels, sem fechamento aceito. | Os 17 ficaram fora da busca por distância ao nó. |
| **Total pendente** | **167** | | **125** associados a junções sem volume, **39** fora da busca e **3** associados à junção salva. |

| Levantamento | Recortes sem volume do trecho original |
| --- | ---: |
| Archamps PostEtroiture | 0 |
| Archamps PreEtroiture | 11 |
| Cascade de Môtiers | 57 |
| Markov Spodmol | 67 |
| Indian Tunnel | 32 |
| **Total** | **167** |

As linhas usam o desfecho da configuração considerada para cada
recorte no inventário. Há versões anteriores com desfechos
diferentes, como o `ramo_042_002` de Cascade, cuja tentativa de tampa
auxiliar antecedeu o alerta de passagem ambígua.

#### Auditoria do eixo ao longo da junção

Em Cascade de Môtiers, os planos usam a linha central fornecida
com o levantamento MainGallery, nos arquivos de nós e arestas
`*_from_LBC.txt`. As configurações desses planos têm
`centreline_extraction` nulo. A inspeção da junção 003 motivou
a checagem amostrada do percurso inteiro, do nó até a tampa,
além da checagem de aproximação de dois voxels.

Na nova execução, os dois contornos candidatos do ramo 19,
a 5,76 m e 6,40 m do nó, tiveram 23 voxels de parede
observada sobre cada trajetória amostrada. O ramo 48
continuou sem estação elegível e a junção 003 ficou sem
componente interno fechado para classificar os demais
voxels livres do eixo. A hipótese de continuação física
além da extremidade do grafo permanece em aberto.

A junção 023 voltou a fechar. Na reprodução pelos NPZs, os
eixos dos ramos 14, 15 e 16 ficaram no mesmo componente de
ar até suas tampas. As novas execuções ficaram em
`data/processed/experiments/juncoes_auto/auditoria_eixo_003_16cm/`
e `auditoria_eixo_023_16cm/`.

#### Eixos desviados e ramos curtos

A junção 003 revelou dois bloqueios independentes. Os dois cortes
candidatos do ramo 19 passaram na checagem da aproximação final,
embora cada percurso amostrado cruzasse 23 voxels de parede
observada. Um contorno local pode ter suporte mesmo quando o
eixo se desvia antes de alcançá-lo. Como a junção ficou aberta,
os relatórios confirmam o contato com a parede. A extensão do
trajeto pelo exterior e a frequência desse problema nos demais
recortes continuam por medir.

O ramo 48 termina como folha no grafo fornecido de Cascade, a
cerca de 0,95 m do nó da junção. A nuvem local sugere uma
continuação vertical além da ponta do eixo. O motivo de o eixo
terminar ali e a extensão da galeria permanecem incertos. A
busca atual exige que a primeira tampa fique a pelo menos oito
voxels do nó e reserva dois voxels antes da ponta do ramo.
A 16 cm, esses limites deixam o último corte possível do ramo
48 a cerca de 0,63 m, abaixo do mínimo de 1,28 m. O ramo ficou
sem estações para testar.

O artigo do catálogo relata que uma contração forte pode deslocar
nós para fora da parede observada, por exemplo em curvas
acentuadas. Essa limitação é compatível com o tipo de desvio
observado, mas sua contribuição para o ramo 19 ainda precisa de
verificação. A ferramenta do projeto também usa contração
laplaciana, com parâmetros e preparação próprios. Uma nova
extração permitiria comparar os eixos, mas a cobertura incompleta
da nuvem e a topologia em árvore continuam limitando o resultado.
[KarstConduitCatalogue, método de extração das linhas centrais](https://essd.copernicus.org/articles/17/4671/2025/#section3)

O ensaio proposto começa pelos braços sem estação elegível.
Mantém-se o voxel de 16 cm, a margem junto à extremidade e a
validação geométrica. A busca tenta estações mais próximas do
nó, começando pelas mais afastadas dentro do intervalo curto.
No ramo 48, um mínimo experimental de três voxels abriria um
intervalo aproximado de 0,48 a 0,63 m. A tampa precisaria de
contorno sustentado, separação das outras tampas e continuidade
do ar da junção até essa abertura. A junção 003 também precisaria
resolver o desvio do ramo 19.

Para investigar eixos desviados, o primeiro ensaio proposto é
recentrar apenas os trechos problemáticos usando seções
transversais sustentadas pela nuvem original. Preservam-se os nós
de junção e a identificação dos ramos. A comparação registra o
contato com a parede, a continuidade do eixo e a reprodução pelo
exterior antes e depois do ajuste. A junção 023 serve de controle.
Recalcular a linha inteira fica como comparação caso o diagnóstico
encontre desvios recorrentes em trechos distantes.

#### Busca alternativa de estações no ramo 48

A busca de três voxels foi implementada para os ramos sem estação
no intervalo padrão. A 16 cm, o ramo 48 ganhou duas estações na
junção 003, a 0,629 m e 0,48 m do nó. Ambas chegaram à checagem
vetorial da aproximação à tampa e foram rejeitadas porque o
eixo cruzava voxels de parede observada. Diminuir a distância
resolveu o bloqueio de comprimento, mas a junção continuou
sem tampa aceita nesse ramo.

A junção 023 serviu de controle. Seus três ramos mantiveram
a busca padrão e o volume voltou a fechar. O novo resultado
por estação e ramo ficou salvo em
`data/processed/experiments/juncoes_auto/ramos_curtos_003_023_16cm/resultados.json`.
A rodada foi limitada à junção 003 e ao controle 023.

#### Ensaio de recentramento nas junções 003 e 023

O ensaio usou a nuvem original e o grafo fornecido da galeria principal
de Cascade de Môtiers, a 16 cm. O recentramento é acionado com
`--recenter-axes` quando o fechamento padrão falha. Ele procura um
trajeto entre dois pontos do eixo original que estejam em fatias
delimitadas pela parede observada, com folga mínima de dois voxels.
[Regras da busca e da validação](../../planejamento-recortes-voxelizacao.md#recentramento-local-por-âncoras)

Na 003, faltou pelo menos uma âncora em cada ramo. Nenhum ajuste
foi aplicado e a junção manteve o resultado `ramo_sem_tampa_valida`.

| Ramo | Voxels de parede encontrados no eixo | Âncora antes | Âncora depois |
| --- | ---: | --- | --- |
| 19 | 41 | Ausente | Ausente |
| 27 | 24 | Ausente | Encontrada |
| 48 | 4 | Ausente | Ausente |

Essas contagens abrangem até 58 voxels do eixo a partir do nó,
ou até a ponta em ramos mais curtos. Os 23 voxels citados para o ramo
19 na rodada anterior foram medidos em trajetórias que terminavam
na tampa candidata. O ensaio confirma os cruzamentos, e a classificação
do ar ao redor do eixo da 003 segue em aberto.

Na 023, o fluxo padrão reproduziu **6.421 voxels de ar**. As matrizes
de ar, parede e das três tampas coincidiram exatamente com as da rodada
anterior. Na checagem dos NPZs pelo exterior, os eixos dos ramos 14,
15 e 16 permaneceram no mesmo componente de ar, que alcançou as três
tampas. Ao remover qualquer tampa isoladamente, o exterior alcançou
a semente. O recentramento ficou reservado ao caso em que a tentativa
padrão falhou.

Para reproduzir a rodada, use um inventário com os dois registros abaixo,
ambos com `falha_anterior: ambiguous_passage`, e execute
`python -m cavegen.datastream.junction_fallback INVENTARIO.json --recenter-axes --output PASTA_NOVA`.

| Junção | Caminho do `crop.json` a partir de `data/processed/` |
| --- | --- |
| 003 | `experiments/planejamento_auto_16cm/config_sementes_originais/cascadedemotiers/MainGallery/ramo_027_004/crop.json` |
| 023 | `crop_plans/cascadedemotiers/MainGallery/holdout_indian_tunnel/las5cm_16cm_rev/ramo_015_001/crop.json` |

O diagnóstico completo ficou em
`data/processed/experiments/juncoes_auto/recentramento_ancoras_003_023_16cm/resultados.json`.
Em testes sintéticos, o ajuste corrigiu um eixo que atravessava parede
quando havia duas âncoras e preservou o eixo original quando faltava uma.
O ensaio em nuvens reais se restringiu a essas duas junções.

#### Reexecução no inventário de recortes pendentes

Em 27/11/2026, o inventário de 167 recortes sem volume do trecho original
foi reprocessado a 16 cm com a auditoria dos eixos, a busca de estações
para ramos curtos e o recentramento por âncoras. A triagem reproduziu
as mesmas associações do piloto. Dos 167 recortes, 39 ficaram fora da
busca por distância ao nó, 125 permaneceram associados a junções sem
volume e três continuaram associados à junção 023 de Cascade de Môtiers.

| Levantamento ou variante | Avaliações de junção | Ramo sem tampa válida | Combinações sem fechamento | Volume reproduzido |
| --- | ---: | ---: | ---: | ---: |
| Cascade de Môtiers | 24 | 18 | 5 | 1 |
| Markov Spodmol | 28 | 24 | 4 | 0 |
| Archamps PreEtroiture | 2 | 2 | 0 | 0 |
| Indian Tunnel Full 10x | 7 | 7 | 0 | 0 |
| Indian Tunnel Full 1x | 1 | 1 | 0 | 0 |
| **Total** | **62** | **52** | **9** | **1** |

A rodada terminou sem novos volumes. A junção 023 voltou a fechar com
6.421 voxels de ar e três tampas, e a checagem pelo exterior passou.
Entre as 61 avaliações que acionaram o recentramento, a busca examinou
183 ocorrências de ramos incidentes, incluindo ramos que aparecem em
junções diferentes. Em 123, a janela amostrada não cruzou parede.
Em 56 faltaram duas âncoras válidas, em três faltou uma candidata em
pelo menos uma fatia e em uma faltou um trajeto admissível entre as
âncoras. Nenhum desses ramos teve seu eixo ajustado na rodada.

A busca para ramos curtos encontrou duas tampas candidatas no ramo 26
da junção 004 de Cascade, a 0,64 m e cerca de 0,775 m do nó. O piloto
anterior não tinha estações elegíveis para esse ramo. A 004 permaneceu
sem volume porque os ramos 27 e 28 continuaram sem tampas válidas.

O lote usou `data/processed/experiments/juncoes_auto/inventario_16cm.json`
com `--recenter-axes` e salvou `resultados.json`,
`comparacao_com_piloto.json` e a reprodução pelos NPZs em
`data/processed/experiments/juncoes_auto/recentramento_pendentes_16cm/`.

#### Meta de recortes para o piloto da GAN

A meta para o fold `holdout_indian_tunnel` é reunir 50 recortes
distintos em grades nativas de 64³ com voxels de 16 cm. A partição
continua por caverna.

| Partição | Levantamentos | Auditados no manifesto inicial | Meta | Faltam |
| --- | --- | ---: | ---: | ---: |
| Treino | Archamps e Cascade de Môtiers | 26 | 30 | 4 |
| Validação | Markov Spodmol | 8 | 10 | 2 |
| Teste | Indian Tunnel | 1 | 10 | 9 |
| **Total** | | **35** | **50** | **15** |

Cada inclusão precisa reproduzir o flood fill pelo exterior, passar nas
checagens de tampas e na triagem numérica do manifesto. Revisões de um
mesmo trecho e variantes de densidade da mesma fonte contam uma vez.
Os volumes de junção ficam registrados separadamente dos recortes de
galeria que acionaram a busca.

A primeira revisão adicional examina as variantes ainda não testadas
pelos algoritmos de ramos curtos e recentramento. Em Indian Tunnel,
24 dos 32 recortes pendentes têm falta de contorno como bloqueio inicial.
Dez deles estão fora do alcance da busca por junções e ficam como
prioridade para uma revisão de contornos no próprio trecho.

Os dez recortes para inspeção estão no plano `auto_full10x_16cm_rev`:
`ramo_001_001` a `ramo_001_008`, `ramo_008_003` e `ramo_009_001`.
Os dois contornos estão ausentes em cada `crop_validacao.json`.
A configuração atual de `ramo_001_001` e `ramo_008_003` já prevê
uma grade de 64³. As outras oito grades excedem 64 em pelo menos
um eixo e também precisam de revisão para entrar no piloto.

Na conferência do acervo a 16 cm, o `ramo_001_008` de Archamps
PreEtroiture passou na auditoria em 64³ e estava fora do manifesto
inicial. Foram encontradas duas versões do mesmo trecho, uma com a
nuvem original e outra com o PLY extraído. A nova auditoria incluiu
apenas a versão da nuvem original, já descrita no histórico da busca
de semente. O manifesto anterior foi preservado. A verificação de
hashes e de separação por caverna confirmou uma única adição em cada
um dos quatro folds, com todos os recortes anteriores preservados.

No fold inicial, a revisão passou a **27 de treino, 8 de validação
e 1 de teste**. Faltam **3, 2 e 9**, respectivamente. O manifesto
revisado está em
`data/processed/experiments/gan_piloto_16cm_revisao_recortes/splits.json`.

#### Ensaio complementar com a nuvem Full 1x de Indian Tunnel

A conferência dos planos a 16 cm manteve o mesmo limite de 8 m
ao nó na triagem. Nas configurações originais, 39 recortes
ficaram sem junção elegível. Eram 8 de Archamps PreEtroiture,
4 de Cascade, 12 de Markov e 15 de Indian Tunnel. Esses casos
dependem de uma revisão no próprio trecho, pois o ajuste de eixos
e a busca de estações para ramos curtos são chamados por junção.

Entre as variantes de nuvem dos recortes pendentes, a Full 1x
de Indian Tunnel tinha seis junções ainda sem avaliação com as
duas rotinas. A rodada complementar usou 15 recortes como entrada
para avaliar essas seis junções na nuvem mais densa. As cópias das
configurações preservaram o grafo, a origem, os ramos, as estações e
o voxel de 16 cm da rodada Full 10x. A junção 012 já tinha sido
avaliada em Full 1x. Nas revisões disponíveis de Archamps, Cascade e
Markov, a triagem encontrou os mesmos pares de nuvem e junção
já avaliados.

As seis junções (001, 002, 003, 004, 007 e 011) terminaram sem
tampa válida em ao menos um ramo. A Full 1x reproduziu as mesmas
contagens de tampas candidatas e de rejeições por ramo da Full 10x.
O ramo curto 15 foi testado nas junções 007 e 011, com seis estações
por junção rejeitadas por falta de contorno. Em 17 das 18 ocorrências
de ramos, o eixo amostrado ficou livre da parede. O ramo 6 da
junção 003 cruzou quatro voxels de parede e ficou sem duas âncoras.
A rodada terminou sem ajuste de eixo ou novo volume.

O inventário complementar e a triagem dos recortes distantes
do nó estão em
`data/processed/experiments/juncoes_auto/inventario_complemento_full1x_16cm/`.
Os resultados por recorte e a comparação com a Full 10x ficaram em
`data/processed/experiments/juncoes_auto/complemento_full1x_16cm/`.

#### Inspeção visual e aberturas documentadas de Indian Tunnel

Na inspeção do Plotly do plano `auto_full10x_16cm_rev`, os trechos
vistos nas duas pontas exibiram mais descontinuidades na parede. O
trecho intermediário mostrado no ramo 002 apresentou superfície mais
contínua. A prévia usa uma amostra da nuvem e a identificação de cada
abertura física depende da correspondência entre o mapa e os recortes.
A NASA descreve Indian Tunnel como um tubo de lava com colapsos e
claraboias e informa que o levantamento CAVES cobriu partes do
interior. Seu interesse como referência vem de uma origem geológica
distinta das outras cavernas do piloto.
[NASA Planetary Pits and Caves Analog Dataset](https://ti.arc.nasa.gov/dataset/caves/)

O mapa da página 4 do suplemento da CMU marca seis locais
levantados. A entrada norte coincide com o colapso 1. Aparecem
também a entrada pela escada, os colapsos 2, 3 e 4 e a saída sul.
O croqui sugere uma divisão perto da entrada pela escada. A
correspondência com o grafo estimado e com os recortes ainda precisa
ser estabelecida. As coordenadas UTM da tabela na página 3 são
dos pontos de estação dos escaneamentos de superfície. O plano
trabalha nas coordenadas locais da nuvem subterrânea.
[Suplemento cartográfico do levantamento](https://ti.arc.nasa.gov/dataset/caves/data/COTM_Supplemental_Info.pdf#page=4)

No ramo 002, o traço visto no fim de `ramo_002_002` e no início de
`ramo_002_003` corresponde ao mesmo corte, fixado a 12,45 m, com
16 setores sustentados no plano. Nos cortes vizinhos, a busca chegou
a 14 setores em algumas estações, mas falhou na checagem de contorno
completo. Já a varredura independente de perfis do ramo 002 encontrou
suporte entre 33,12 e 34,40 m e desse ensaio saiu o único volume de
teste em 64³ a 16 cm. A revisão visual do trecho intermediário deve
considerar tanto a escolha da estação quanto o suporte angular da
parede.

Na vista individual de `ramo_002_003`, o eixo estimado aparece
próximo a uma parede lateral e se vê uma descontinuidade na parte
inferior da nuvem. Para conferir se o recorte tinha retirado esses
pontos, foram comparadas fatias da Full 10x original e dos PLYs
vizinhos, com 32 cm de cada lado dos planos e células de 1 m na
projeção transversal de inspeção. A 17,00 m, a região inferior
descontínua aparece nas duas fontes. Nessa fatia foram contados
43.866 pontos na Full 10x e 43.729 nos PLYs. A 22,50 m também
aparecem lacunas inferiores. A 28,00 m há uma faixa inferior
contínua nessa escala de inspeção, e a 33,76 m há pontos que
ligam as duas paredes pela parte inferior. A evidência indica
lacunas locais de cobertura que variam ao longo do ramo. O mapa
de superfície documenta os acessos e colapsos e deixa em aberto
a causa das lacunas no piso. Uma tampa de extremidade e o
recentramento, por si sós, deixam essa parte da parede sem
evidência medida.

O HD contém `Section1/IndianTunnel_1.f32` com 11.800.438 pontos
e `Section2/IndianTunnel_2.f32` com 10.573.581. A amplitude vertical
nos eixos dos arquivos é de 2,64 m e 1,86 m, respectivamente, e são
coberturas locais do mesmo levantamento. O ensaio anterior com as
duas seções junto da Full 10x manteve oito fugas. O arquivo
`Wall/IndianTunnel_Wall.f32` tem 4.339.760 pontos e corresponde ao
painel de parede descrito no suplemento, útil para inspecionar
detalhe de superfície.

Depois da reorganização dos arquivos no HD, a Full 10x está em
`RAW/IndianTunnel/Full/IndianTunnel_full_10x.f32`. O plano arquivado
ainda referencia o caminho anterior com `IndianTunnel_cave/`. A
inspeção usa os PLYs já extraídos e uma nova extração precisa apontar
para a localização atual da nuvem original.

### Escala física da nuvem Elaphes

A leitura dos primeiros 64 KiB do LAZ original do LIRIS confirmou
um cabeçalho LAS 1.2 com 94.465.067 pontos e limites XYZ que coincidem
com os do PLY local até a precisão do registro versionado. O
cabeçalho não declara um sistema de referência ou uma unidade física.
Os fatores de escala do LAS decodificam os inteiros armazenados.

O 3D Tiles original do LIRIS usa como translação os mínimos XYZ
do LAZ e mantém uma transformação linear identidade. A variante
posicionada em Lyon também aplica apenas translação. Como a
especificação 3D Tiles 1.0 usa metros para distâncias lineares,
o vínculo entre os formatos sustenta interpretar os XYZ locais
do PLY em metros para o piloto de 16 cm.
[Dados do LIRIS](https://dataset-dl.liris.cnrs.fr/elaphes-cave/)
[Metadados do 3D Tiles original](https://dataset-dl.liris.cnrs.fr/elaphes-cave/Exp-Cloud-ELAPHS-94M-3DTiles/tileset.json)
[Especificação OGC 3D Tiles 1.0](https://docs.ogc.org/cs/18-053r2/18-053r2.html)

O capítulo de Hobléa e Philippe descreve a morfologia e o contexto
cárstico e dá coordenadas e altitudes para duas entradas. Ele pode
orientar uma conferência com pontos reconhecíveis, mas a evidência
da escala do PLY vem dos arquivos do levantamento digital.
[Le contexte karstologique](https://www.persee.fr/doc/mhnly_1627-3516_2001_num_2_1_1316)

O piloto de Elaphes selecionou três recortes nos ramos 003 e 006
do grafo podado da galeria exploratória. O planejamento usa voxels
de 16 cm e consulta até oito voxels de cada lado de uma estação
pendente. A etapa de voxelização usa a busca de semente do fluxo
padrão e pode tentar tampas auxiliares com raio de até quatro voxels.
A partição de teste de Elaphes ficou em um inventário local da
execução, separado dos folds de Indian Tunnel.

Depois da primeira leitura de teste do PLY ASCII, o fluxo passou
a usar uma cópia binária XYZ do mesmo levantamento para acelerar
as leituras sucessivas. A conversão conserva a ordem das observações
e usa a mesma precisão float32 do leitor PLY da Datastream.
O plano local e os resultados por recorte ficam em
`data/processed/experiments/elaphes_piloto_binario_16cm/`.

| Recorte de Elaphes | Grade original ZYX | Resultado |
| --- | --- | --- |
| `ramo_003_001` | 64×64×76 | Fuga com alerta de passagem próxima ou retorno |
| `ramo_006_001` | 64³ | Fuga com alerta de passagem próxima ou retorno |
| `ramo_006_002` | 64³ | 7.334 voxels de ar, sem reparo ou tampa auxiliar |

As seis extremidades tiveram suporte nos 16 setores. No
`ramo_006_002`, o flood fill pelo exterior voltou a isolar o
mesmo ar. Remover qualquer uma das duas tampas de extremidade
reabriu o volume. O `reference_audit.json` local aprovou esse
recorte na triagem da GAN com sua grade nativa de 16 cm. Ele
permanece como candidato a teste externo de Elaphes, em produto
separado do manifesto de Indian Tunnel.

### Ampliação do manifesto com máscaras de ar derivadas

A rodada usou `--fit-air-grid` nos mesmos 11 planos do manifesto
revisado a 16 cm. Os 36 recortes já aceitos foram preservados e
entraram mais dois de Archamps. A tabela registra a grade na qual
cada candidato foi fechado e auditado e a janela de 64³ usada
somente como entrada da GAN.

| Levantamento | Recorte | Grade original ZYX | Início da janela ZYX | Voxels de ar preservados |
| --- | --- | --- | --- | ---: |
| Archamps PostEtroiture | `ramo_001_005` | 64×64×68 | (0, 0, 2) | 12.455 |
| Archamps PreEtroiture | `ramo_002_007` | 64×64×70 | (0, 0, 3) | 13.796 |

O fold `holdout_indian_tunnel` passa a **29 treino, 8 validação
e 1 teste**, totalizando 38. Faltam **1, 2 e 9**, respectivamente,
para a meta de 50. Nos 46 volumes dos planos selecionados, oito
excederam a janela ou ficariam com margem insuficiente. A varredura
adicional em outros planos auditou 35 versões já salvas sem encontrar
outro recorte elegível fora do manifesto. O plano piloto antigo de
PostEtroiture contém mais de uma versão de um mesmo identificador
e foi sinalizado na varredura. As seis propostas revisadas de
PostEtroiture já pertencem aos planos selecionados.

O manifesto e o relatório completo ficam em
`data/processed/experiments/gan_piloto_16cm_indian_tunnel/`,
que preserva a configuração anterior ao fold cárstico.
[Método e reprodução da máscara de ar](README.md#máscara-derivada-de-ar-para-a-grade-da-gan)

### Piloto externo em Madeleine e Rupt du Puits

Em 27/11/2026, o piloto incluiu a Galerie du Filleul, em
Grotte de la Madeleine, e Cascades, em Rupt du Puits. Os dois
pacotes SwissUbase trazem nuvens do FARO Focus 3D e tabelas de
nós e arestas da linha central. O ensaio usou os grafos do
catálogo no sistema XYZ das nuvens, sem extrair um novo eixo.
Os DOI abaixo são os da versão 1.0 nos metadados que vieram
com os arquivos do HD. O MD5 de cada ZIP coincide com o
valor publicado nos metadados do pacote.
[Madeleine, versão 1.0](https://doi.org/10.60544/ckkg-gn58) ·
[Rupt du Puits, versão 1.0](https://doi.org/10.60544/t0nv-xj93)

| Levantamento | Ramos do grafo | LAS de 5 cm | LAS de 2 mm | Recortes por variante |
| --- | ---: | ---: | ---: | ---: |
| Madeleine / Filleul | 5 | 645.190 pontos | 15.916.629 pontos | 19 |
| Rupt du Puits / Cascades | 1 | 377.430 pontos | 13.045.683 pontos | 7 |

As duas rodadas mantiveram voxels de **16 cm**. O alvo de
comprimento nominal foi de aproximadamente 7 m, com pelo
menos um recorte por ramo e distribuição dos demais pelo
comprimento útil. A revisão de estações consultou a nuvem
original a até oito voxels de distância. As variantes
usaram os mesmos grafos e o mesmo ponto de partida do
planejamento, com novo ajuste dos contornos e possíveis
deslocamentos de estação em cada nuvem. O efeito da densidade
e o efeito dessas mudanças de estação podem coexistir.
A busca de semente e a tampa auxiliar foram limitadas a
quatro voxels. As falhas elegíveis seguiram para a triagem
de junções, com recentramento por âncoras disponível após
falha do fluxo padrão.

A execução local fica em
`data/processed/experiments/madeleine_rupt_16cm/`.
Cada variante guarda `entrada.json`, `recortes/plan.json`,
`recortes/recortes.html`, `resultados.json` e
`juncoes/resultados.json`. O `reference_audit.json` registra
a reprodução pelo exterior, o contato do ar com as duas
tampas e a triagem em 64³, inclusive a janela derivada de ar
quando aplicável. Os inventários locais marcaram cada caverna
como fonte de teste externo. Uma revisão de densidade permanece
uma versão da mesma galeria e os resultados ficam fora do
manifesto principal até a definição do conjunto comparativo.

| Fonte | Fecharam | Passaram na triagem da GAN | Contorno ausente | Semente na barreira | Fuga em passagem ambígua | Fuga sem apoio para o reparo |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Madeleine 5 cm | 4/19 | 4 | 7 | 2 | 4 | 2 |
| Madeleine 2 mm | 5/19 | 4 | 7 | 1 | 3 | 3 |
| Rupt du Puits 5 cm | 1/7 | 1 | 0 | 0 | 0 | 6 |
| Rupt du Puits 2 mm | 3/7 | 3 | 3 | 0 | 0 | 1 |

Considerando os identificadores uma vez por caverna, **oito
recortes fecharam e sete passaram na triagem**. Todos os
aprovados estão em 64³ nativos e todos os fechamentos deste
ensaio usaram tampas auxiliares sintéticas. As contagens abaixo
identificam a intervenção aplicada a cada variante.

| Caverna | Recorte | Ar a 5 cm de amostragem | Células auxiliares a 5 cm | Ar a 2 mm de amostragem | Células auxiliares a 2 mm |
| --- | --- | ---: | ---: | ---: | ---: |
| Madeleine | `ramo_001_002` | 6.527 | 114 | 6.316 | 106 |
| Madeleine | `ramo_001_006` | 3.791 | 1.059 | 4.012 | 1.182 |
| Madeleine | `ramo_001_008` | — | — | 15.218 | 481 |
| Madeleine | `ramo_002_001` | 7.528 | 286 | 7.302 | 270 |
| Madeleine | `ramo_002_003` | 14.528 | 415 | 11.815 | 523 |
| Rupt du Puits | `ramo_001_001` | 25.987 | 6 | 25.493 | 22 |
| Rupt du Puits | `ramo_001_002` | — | — | 24.758 | 25 |
| Rupt du Puits | `ramo_001_003` | — | — | 27.305 | 316 |

O 001/008 de Madeleine é o fechamento adicional da fonte
densa. Na grade nativa de 64×74×64, o ar ocupa 63 células no
eixo Y. Como o ajuste exige duas células de margem em cada
ponta do eixo reduzido, seriam necessárias 67 células. O volume
permanece disponível na grade nativa para inspeção. A magnitude
da intervenção em 001/006 também merece revisão geométrica
antes de usar o trecho como referência de teste.

Em Rupt du Puits, a nova rodada recuperou 001/002 e 001/003.
Nos três últimos recortes, o problema passou a ser a falta de
contorno. Dois cortes compartilhados ficaram com apenas 7 e 8
setores apoiados nas estações selecionadas. Na variante de
5 cm esses recortes tinham as duas tampas, mas vazavam. A
cobertura das estações e a capacidade de fechar a parede são
checagens distintas.

As duas junções de Madeleine ficaram sem tampa válida em
pelo menos um ramo nas duas densidades, mesmo após acionar o
recentramento. Em Cascades, o grafo tem um único ramo e a
triagem não encontrou junções a examinar. A repetição pelo
exterior reproduziu os 13 volumes salvos nas quatro
execuções, contando suas diferentes versões. A comparação por
identificador e os caminhos dos relatórios de repetição estão
em `comparacao.json`. Os sete candidatos de 64³ continuam
sujeitos à revisão geométrica das tampas auxiliares.

### Vallorbe e novo fold cárstico

O piloto de **Vallorbe / GalerieSemiActive** usou o LAS de
5 cm do BLK2GO, em coordenadas EPSG:2056, com **1.928.808
pontos**. O grafo fornecido tem 325 nós, 324 arestas e 11
ramos. Seis ramos tinham extensão útil para o planejador.
A extração, a busca de estações e a voxelização repetiram os
parâmetros do piloto de Madeleine e Rupt du Puits, com
voxels de 16 cm.
[Vallorbe, versão 1.0](https://doi.org/10.60544/5jz0-fx48)

Dos **26 recortes**, **11 fecharam** e passaram no replay
pelo exterior. Nove ficaram sem contorno, cinco vazaram com
alerta de outra passagem e um vazou sem pontos suficientes
nos bins necessários ao reparo local. A busca de junções
avaliou quatro nós e ficou sem tampa válida em pelo menos
um ramo em cada nó. Entre os fechamentos, nenhum usou
células de reparo local. Dez usaram de 4 a 160 células de
tampa auxiliar e o `ramo_004_004` fechou com as duas tampas
de extremidade. A triagem aceitou **8 recortes**, com seis
grades nativas de 64³ e duas janelas derivadas. Os outros
três interiores fechados excederam o limite ou a margem da
janela. A execução está em
`data/processed/experiments/vallorbe_16cm/`.

O fold ativo passa a ser **`holdout_carste`**. Ele conserva
29 recortes de treino de Archamps e Cascade de Môtiers e oito
de validação de Markov Spodmol, com as mesmas máscaras da
configuração anterior. O teste passa a usar 15 recortes de
cavernas cársticas reservadas, sendo quatro de Madeleine,
três de Rupt du Puits e oito de Vallorbe. Quando as duas
densidades deram um recorte elegível do mesmo identificador,
selecionou-se a versão com menos células de tampa auxiliar.
A seleção e as versões concorrentes são registradas em
`selecao_teste.json`.

O manifesto anterior foi arquivado em
`gan_piloto_16cm_indian_tunnel/`. O manifesto ativo ocupa
`gan_piloto_16cm_mascaras_ar/` e resolve os caminhos a
partir de `data/processed`. O `ramo_002_001` de Indian
Tunnel fica reservado em `avaliacao_externa_indian_tunnel.json`
para uma avaliação separada no domínio de tubo de lava.
[Inventário completo e comando de verificação do novo fold](../../relatorios/inventario-gan-holdout-carste.md)
