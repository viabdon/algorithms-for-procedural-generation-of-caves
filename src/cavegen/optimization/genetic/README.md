# optimization/genetic — ajuste genético do CA guiado por SDF

Procura os hiperparâmetros do Cellular Automata guiado por SDF que fazem a
caverna gerada cair em cima do campo de uma ou mais cavernas reais
voxelizadas (por padrão, só o Elaphes 64³). O algoritmo genético (GA) propõe
as combinações, o CA gera uma caverna para cada uma, em cada caverna real, e
uma nota diz o quanto cada caverna gerada acertou o campo daquela caverna.
**No fim ele devolve a lista dos melhores parâmetros com as notas** (os 10
primeiros, por padrão).

Existe também uma **busca aleatória** (`--metodo aleatoria`, ou
`uv run poe busca-aleatoria`). Ela **não é um algoritmo genético**: só sorteia
parâmetros dentro das mesmas faixas, com o mesmo orçamento e o mesmo
avaliador, sem seleção, cruzamento nem mutação. Serve de controle: se o GA
não achar notas melhores que o sorteio, a seleção e a herança não estão
ajudando.

```
SDF da caverna com ln(1 + |d|) ──┬──> peso do CA ──┐
  (um campo por caverna)         │                 ├─> CA (sempre 40 passos) ─> caverna gerada
semente (chance_inicial, seed) ──┼─────────────────┘                                │
                                 └──> alvo da nota <────────────────────────────────┘
                                          │
              nota em cada caverna ─> média entre as cavernas ─> GA escolhe os próximos
```

> **Execuções antigas não são comparáveis.** `ga_001` a `ga_010`, em
> `results/`, usaram o alvo antigo (SDF do Elaphes com limiar −3 e log, 5.201
> voxels positivos, vazio aceito de 2.600,5 a 26.005), 3 seeds de ajuste,
> parada antecipada e só o Elaphes. A partir de 22/11/2026 o alvo é o próprio
> campo do peso, as seeds de ajuste são 5, o CA roda sempre as 40 iterações e
> pode haver várias cavernas (ver `docs/methodology-adjustments.md`). As
> notas antigas e novas medem coisas diferentes e não devem ser postas lado a
> lado. Os arquivos antigos ficam como estão, também com os campos antigos
> (`peso`, `alvo`, `nota_teto_trivial`...).

## Arquivos

| arquivo | o que tem |
|---|---|
| `algoritmo.py` | motor genérico do GA e a busca aleatória de controle; não conhece o CA |
| `aptidao.py` | a nota (`Alvo`), a faixa de vazio aceita (`Cortes`), a cópia pura e o resumo entre cavernas |
| `ca.py` | o cromossomo do CA (`GENES_CA`), a caverna (`Caverna`) e o avaliador que roda o CA nas cavernas e seeds |
| `executar.py` | linha de comando: carrega as cavernas, roda a busca, confere nas seeds reservadas, grava o resultado |
| `painel.py` | mostra o andamento no terminal (etapas, gerações, candidato atual, ranking) |
| `results/` | um `ga_NNN.npz` por execução (fora do Git) |

O motor (`algoritmo.py`) recebe só uma lista de genes e uma função de
avaliação; o que é específico do CA fica em `ca.py`.

## Como um algoritmo genético funciona

É uma busca inspirada em seleção natural. Em vez de testar todas as
combinações ou só sortear, ele usa as boas combinações já encontradas para
propor as próximas.

1. **Cromossomo**: uma combinação de hiperparâmetros, aqui um dict
   `{nome do gene: valor}`. Cada gene tem uma faixa permitida.
2. **Aptidão (nota)**: quanto o cromossomo é bom. Maior é melhor.
3. **População inicial**: 20 cromossomos sorteados dentro das faixas.
4. A cada **geração**:
   - **elitismo**: os 2 melhores passam intactos, sem gastar orçamento;
   - **seleção por torneio**: para cada pai, sorteia 3 cromossomos e fica o de
     maior nota. Quem é bom tem mais chance de ter filhos, mas o fraco ainda
     pode ganhar um torneio, o que mantém variedade;
   - **cruzamento uniforme** (chance 0,9): cada gene do filho vem do pai ou da
     mãe, meio a meio. Senão, o filho é cópia de um dos pais;
   - **mutação gaussiana** (chance 0,3 por gene): soma um desvio normal de 10%
     da faixa do gene e devolve o valor para dentro da faixa (e, se o gene tem
     passo, para o ponto da grade mais perto). É o que permite achar valores
     que nenhum pai tinha;
   - os 18 filhos e os 2 da elite formam a geração seguinte.
5. Para quando o **orçamento** (total de candidatos avaliados, padrão 400)
   acaba. A última geração pode ficar incompleta.

Com população 20 e orçamento 400 são a população inicial e mais umas 21
gerações completas. Um candidato repetido gasta orçamento do mesmo jeito (a
busca "pediu" ele), mas o CA não é rodado de novo: a nota é determinística e
fica em cache. O resultado conta quantos foram reaproveitados.

Os parâmetros do próprio GA ficam em `ConfiguracaoGA` (`algoritmo.py`). Eles
não foram ajustados; uma análise de sensibilidade deles é trabalho futuro.

## O cromossomo do CA

Definido em `GENES_CA` (`ca.py`). As faixas foram medidas no Elaphes 64³ em
12/11/2026, com folga em volta das melhores notas; a da `chance_inicial` foi
alargada para 0,2 a 0,8 em 19/11/2026. **As duas medições usaram o alvo
antigo (limiar −3)**; com o alvo de 22/11/2026 elas não foram refeitas.

| gene | faixa | o que faz |
|---|---|---|
| `chance_inicial` | 0,2 a 0,8, de 0,02 em 0,02 | chance de cada célula da semente nascer vazia |
| `sensibilidade` | 1 a 20, inteiro | mínimo de vizinhos (com o peso somado) para a célula ficar vazia; de 18 para cima a caverna sempre morria |

### Por que a chance inicial anda de 0,02 em 0,02

A matriz inicial é `numpy_rng(seed).random(forma) < chance_inicial`: a seed
sorteia um número para cada célula e a chance é o limiar. Com a mesma seed,
duas chances próximas só diferem nas células cujo número caiu entre elas.
Até 18/11/2026 o gene era contínuo, e a lista dos melhores saía cheia de
chances como 0,5639 e 0,564, que mudam umas 26 células em 262.144: a mesma
caverna, com diferença de nota do tamanho do ruído. Com o passo de 0,02
(`Gene(..., passo=0.02)`), cada vizinho da grade muda cerca de 2% das células
e a lista passa a mostrar diferenças reais. O sorteio escolhe um ponto da
grade com chance igual, e a mutação soma o desvio normal e volta para o ponto
mais perto.

**As execuções até `ga_009` usaram a chance contínua de 0,3 a 0,7 e 50
iterações; não são o mesmo espaço de busca das seguintes.**

### O que fica fora do cromossomo

- **campo**: cada caverna tem um campo só, o SDF dela com `ln(1 + |d|)` e
  escala 1, que é ao mesmo tempo o peso do CA e o alvo da nota (ver abaixo).
  Ele entra no CA **como está**: nada o multiplica, comprime ou corta. A
  escala do log é **fixa em 1, por decisão metodológica**: até 15/11/2026 ela
  era um gene, e o GA a subia até o peso dominar os vizinhos (ver "O decalque
  e a retirada da escala");
- **borda**: sempre `NEAREST`, que repete a beirada da grade. `ZEROS` fecharia
  e `ONES` abriria a caverna onde ela toca a borda, e `RANDOM` depende da sorte;
- **iterações**: o CA roda **sempre** `MAX_ITERACOES = 40`, sem nenhuma
  parada antecipada, calcula a nota em todo passo e a melhor iteração sai
  junto com a nota (ver abaixo);
- **modo do peso**: sempre o completo (`MODO_PESO`, gravado no resultado). O
  modo "só negativo" existe no CA, mas não entrou no ajuste. O modo do peso é
  uma escolha **do CA**, independente do método de busca: o GA e a busca
  aleatória usam o mesmo avaliador e, portanto, o mesmo modo. Trocar o modo
  não cria outro método de busca, e trocar o método não muda o modo.

## A matemática, passo a passo

### 1. O SDF: distância com sinal

O SDF (*signed distance field*) dá a cada voxel a sua distância até a
superfície da caverna, com um sinal que diz de que lado ele está. A
ferramenta [`tools/sdf`](../../../../tools/sdf/README.md) faz isso em três
passos, a partir da grade de superfície voxelizada (1 = parede observada):

1. **Inundação** ([`tools/flood_fill`](../../../../tools/flood_fill/README.md)):
   a água entra pela beirada da grade e se espalha pelos voxels que não são
   parede. O que ela alcança é **externo**; a parede é a **borda**; o que não
   é parede e a água não alcança é **interno**.
2. **Distância**: para cada voxel, a distância euclidiana (em voxels) até o
   voxel de borda mais próximo. A borda fica com 0.
3. **Sinal**: interno positivo, externo negativo. O sinal não vem da
   distância (que é sempre positiva), e sim da inundação.

Por que o interno é positivo: ele é "a caverna", o lugar onde a nota quer
vazio, e positivo é o que soma. A borda é zero porque a distância dela até
ela mesma é zero: ela é a fronteira entre os dois lados. O externo é negativo
porque é o lado de fora: quanto mais longe da parede, mais negativo.

**O que é o interno no Elaphes.** O PLY observa a parede, não o ar. Como a
caverna tem entradas, o ar do túnel se liga ao lado de fora e a água o
alcança: ele fica **externo** (negativo). O interno é a espessura da parede
voxelizada (e buracos fechados), não o ar transitável. O
`docs/methodology-adjustments.md` (seção 1) registra que esse campo não
valida `VOID` real. No Elaphes 64³ são 292 voxels internos, 783 de borda e
261.069 externos.

### 2. O log: por que `sinal(d) · ln(1 + |d|)`

O SDF cru vai de −63,16 a +2,00 no Elaphes. O CA soma o peso à contagem de
vizinhos (de 0 a 27), e a nota soma o alvo nos voxels vazios. Com o SDF cru,
um voxel a 63 voxels da parede pesaria 63 vezes mais que um voxel colado
nela, e dominaria as duas contas. O logaritmo **comprime**: cresce rápido
perto de zero e devagar depois, então a distância grande pesa só um pouco
mais que a pequena.

Mas `ln(d)` sozinho não serve, por dois motivos:

- **não existe para d negativo**, e o externo inteiro é negativo. Por isso a
  conta usa o valor absoluto `|d|` (só a distância) e devolve o sinal no fim,
  multiplicando por `sinal(d)`;
- **vai a menos infinito perto de zero** (`ln(0) = −∞`), e a borda é
  exatamente zero. Somar 1 antes resolve: `ln(1 + 0) = ln(1) = 0`, então a
  borda continua 0 e o campo continua finito.

O resultado, `sinal(d) · ln(1 + |d|)`, mantém o zero na borda, o sinal de
cada lado e a ordem dos voxels (quem estava mais longe continua mais longe),
só que comprimida. Valores reais do Elaphes 64³, escala 1, sem limiar
(`tools/sdf/npz/elaphes_surface_64_sdf_log1.npz`):

| região | d (voxels) | `sinal(d) · ln(1 + \|d\|)` | voxels com esse d |
|---|---|---|---|
| interno, mais fundo | +2 | +1,0986 | 4 |
| interno | +√3 ≈ +1,73 | +1,0051 | 4 |
| interno | +√2 ≈ +1,41 | +0,8814 | 27 |
| interno, colado na borda | +1 | +0,6931 | 257 |
| borda | 0 | 0 | 783 |
| externo, colado na borda | −1 | −0,6931 | 1.095 |
| externo | −2 | −1,0986 | 624 |
| externo | −3 | −1,3863 | 830 |
| externo | −5 | −1,7918 | 652 |
| externo | −10 | −2,3979 | 186 |
| externo | −20 | −3,0445 | 77 |
| o mais distante | −63,16 | −4,1614 | 1 |

Sem o log, o voxel mais distante vale 63 vezes o de d = −1; com o log, 6
vezes (4,16 / 0,69). O campo final vai de −4,16 a +1,10. Como a contagem de
vizinhos vai de 0 a 27, o peso é uma **dica**: empurra a célula, mas os
vizinhos ainda decidem.

A ferramenta do SDF também desloca o zero (limiar) antes do log; o GA **não
usa** o limiar desde 22/11/2026. A ordem limiar → log e o que acontece na
ordem inversa estão no [README do `tools/sdf`](../../../../tools/sdf/README.md#3-manipulação-limiar-e-log).

### 3. A nota de uma caverna

```
nota = soma(alvo nos voxels vazios) / soma(alvo onde ele é positivo)
```

- **O numerador** percorre os voxels que a caverna gerada deixou vazios e
  soma o valor do alvo em cada um. Vazio no interno soma (+0,69 a +1,10),
  vazio na borda não muda nada (0), vazio no externo **desconta** (−0,69 a
  −4,16). Sem o desconto, encher a grade inteira acertaria todo o interno e
  ganharia a nota máxima; com ele, encher a grade do Elaphes dá −4.033.
- **O denominador** é o máximo que o numerador pode alcançar: vazio em todo
  voxel positivo e em nenhum negativo. No Elaphes ele vale 210,35 (a soma
  dos 292 internos); no Indian Tunnel, 191,63.
- **Por que o teto é 1**: o numerador nunca passa do denominador, porque o
  melhor que dá para fazer é somar todos os positivos sem descontar nada.
  Dividir um pelo outro dá 1 nesse caso, 0 com a grade toda rocha (nenhum
  vazio, nada somado) e um número negativo quando o vazio fora pesa mais que
  o de dentro. Não há piso: a nota pode ser muito negativa.
- **Por que a nota sai "quebrada"** (0,543 e não 10 mil pontos): ela é a
  **fração do máximo possível**. 0,543 quer dizer que a caverna gerada somou
  54,3% do que a caverna perfeita somaria, já descontado o vazio fora. A
  soma crua dependeria do tamanho e da forma de cada caverna (210,35 no
  Elaphes, 191,63 no Indian Tunnel) e não daria para comparar cavernas.
  Dividindo, a nota fica na mesma régua em todas, e multiplicar o alvo por
  qualquer constante não a muda (a constante aparece em cima e embaixo).
- Um exemplo de equilíbrio: no Elaphes, um voxel vazio em d = −1 (−0,69)
  cancela exatamente um voxel vazio em d = +1 (+0,69).

### 4. A faixa de vazio aceita

Antes da nota, o vazio total da caverna gerada precisa estar numa faixa
relativa ao **número de voxels positivos do alvo** (não à grade):

```
0,5 × positivos ≤ vazio ≤ 5 × positivos      (Cortes: fator_minimo, fator_maximo)
```

Fora dela, a nota daquele passo é `-inf` (`NOTA_MINIMA`), que nunca vence.

| caverna | voxels positivos | vazio aceito |
|---|---|---|
| Elaphes 64³ | 292 | de 146 a 1.460 |
| Indian Tunnel 64³ | 265 | de 132,5 a 1.325 |

Por que existe: sem o mínimo, uma grade toda rocha (nota 0) venceria qualquer
caverna que escavasse um pouco fora da forma (nota negativa). Sem o máximo,
nada impediria cavernas muito maiores que a forma de competir. A caverna
perfeita (interno + borda: 292 + 783 = 1.075 voxels no Elaphes) cabe na
faixa. A faixa **não interrompe o CA**: ele roda as 40 iterações e a faixa só
decide a nota de cada passo.

> **Atenção (22/11/2026).** Com o alvo sem limiar, a faixa encolheu de
> 2.600,5–26.005 para 146–1.460 voxels no Elaphes (de 1%–10% para
> 0,06%–0,56% da grade). Na execução curta de validação, a maior parte dos
> candidatos foi cortada: eles enchem a grade ou morrem, e só passam pela
> faixa de forma transitória. Rever os fatores ou as faixas dos genes é
> decisão pendente do Felipe.

**Até 22/11/2026 havia parada antecipada**: o CA parava antes das 40
iterações se o vazio estivesse acima do máximo sem diminuir, abaixo do mínimo
sem aumentar, ou se menos de 0,01% da grade mudasse num passo
(convergência). Ela saiu porque o GA é rápido e tem poucos genes: economizar
tempo não importa, e é melhor que a nota de cada passo venha da grade de
verdade. A parada por convergência também saiu: com o corte em 0,01% (26
células em 64³), ela repetia a nota do passo em que parou mesmo quando ainda
mudavam algumas células, e sem ela o código fica mais simples. A
penalização continua igual: encher ou esvaziar a grade inteira dá `-inf` em
todo passo.

### 5. Seeds, média e escolha da iteração

**A seed é só o número que inicializa o sorteador** (`numpy_rng(seed)`) da
matriz inicial. A **porcentagem** de vazio é outra coisa: é o gene
`chance_inicial`. A mesma seed com a mesma chance dá sempre a mesma grade.

Cada candidato roda nas **5 seeds de ajuste** (1 a 5), **com a mesma chance
nas 5**: só o ruído muda de uma para outra. As seeds de ajuste são fixas, as
mesmas para todos os candidatos, por três motivos: a comparação é justa
(todos enfrentam as mesmas grades iniciais), a nota é determinística (o mesmo
candidato dá sempre a mesma nota) e, por isso, o cache de repetidos funciona.
Cinco seeds deixam a nota menos sujeita à sorte de uma grade só (até
22/11/2026 eram 3).

Para cada passo t de 1 a 40:

1. em cada caverna, a nota do passo é a **média das 5 seeds**;
2. a nota do passo do candidato é a **média dessas notas entre as cavernas**;
3. a **melhor iteração** é o passo de maior média, **uma só para todas as
   cavernas**, e essa média é a nota do candidato.

Se uma seed é cortada num passo, a média da caverna naquele passo vira
`-inf`, e a do candidato também: ele precisa ficar na faixa em todas as seeds
de todas as cavernas ao mesmo tempo.

No final, cada parâmetro da lista dos melhores roda nas **seeds reservadas**,
em todas as cavernas, com o número de iterações já escolhido, sem escolher
de novo. São **10 seeds**, que a busca nunca vê, sem nenhuma em comum com as
de ajuste. Os números delas (101 a 110) são **só rótulos**, escolhidos para
não coincidir com 1 a 5: são 10 grades, não 110. É a nota que mede se o
parâmetro generaliza para grades que a busca nunca viu.

Como nada interrompe o CA, rodar N iterações dá exatamente os N primeiros
passos de uma execução de 40: a nota da iteração escolhida se reproduz bit a
bit fora da busca.

### 6. Várias cavernas: média, mínimo, máximo e desvio

Com `--cavernas`, o mesmo candidato é avaliado em todas as cavernas. Cada
uma tem o seu campo (peso e alvo) e a sua faixa de vazio, relativa aos
positivos dela: cavernas de tamanhos diferentes têm faixas diferentes. Na
iteração escolhida, o resumo entre as cavernas é:

- **média**: o critério de ordenação do ranking (cada caverna pesa igual);
- **mínimo e máximo**: a pior e a melhor caverna;
- **desvio**: desvio padrão populacional das notas por caverna (0 com uma só,
  `-` no painel e `NaN` no arquivo se alguma caverna foi cortada);
- **a nota de cada caverna**, lado a lado.

Por que mostrar mais que a média: uma média alta pode esconder uma caverna
que encaixa perfeitamente e puxa a média para cima, enquanto as outras ficam
medianas. O objetivo é qualidade proporcional entre as cavernas.

**Não é teste de generalização.** Todas as cavernas de `--cavernas` entram na
busca, e a conferência nas seeds reservadas usa as mesmas cavernas (só o
ruído inicial muda). O resultado mede robustez entre as cavernas da busca;
para dizer que os parâmetros generalizam para outra caverna, ela teria de
ficar fora da busca e entrar só na conferência (pendente de decisão).

Com poucas
cavernas o desvio padrão é instável (com duas, ele é só metade da diferença
entre elas), então o mínimo e as notas por caverna, lado a lado, são a
leitura mais direta. O ranking continua ordenado só pela média; o resto é
para ler.

**Uma iteração para todas as cavernas.** O número de iterações escolhido é
um só por candidato. Isso tem custo: uma caverna pode estar no seu melhor
passo e outra não. Na validação, `chance_inicial=0,66, sensibilidade=15`
tinha o melhor passo do Elaphes na iteração 23 (+0,172); com o Indian Tunnel
junto, a iteração escolhida virou a 19, onde o Elaphes vale −0,972.

**O que a caverna precisa ter.** O arquivo tem que ser o SDF com log de
escala 1 e sem limiar, como o `tools/sdf` grava; outro limiar ou outro log
param a execução dizendo qual caverna. O SDF precisa de pelo menos um voxel
positivo (senão a nota dividiria por zero), e a grade precisa ser cúbica
(a semente do CA é um cubo); nos dois casos o erro diz qual caverna e por
quê. A mesma caverna duas vezes também é recusada, mesmo com outro nome
(mesmo sha256), porque pesaria em dobro na média. Uma grade cúbica de outro lado (32³, por exemplo) roda, mas o painel
avisa: o protocolo é 64³, e um voxel de 32³ é duas vezes maior por lado,
então a mesma sensibilidade não quer dizer a mesma coisa nas duas.

**Grades de superfície que já existem no projeto** (22/11/2026):

| caverna | grade | onde | SDF com log 1 |
|---|---|---|---|
| Elaphes | 64³, 1.049 voxels de superfície | `data/processed/references/elaphes_surface_64.npz` | `tools/sdf/npz/elaphes_surface_64_sdf_log1.npz` |
| Indian Tunnel (NASA) | 64³, 1.145 voxels de superfície | `indian_tunnel_temp/npz/indian_tunnel_surface_64.npz` | `tools/sdf/npz/indian_tunnel_surface_64_sdf_log1.npz` |
| Elaphes (do Pablo) | 32³, 245 voxels de superfície | `data/processed/references/elaphes_surface_32_pablo.npz` | não gerado: é a mesma caverna em outra resolução |

No Indian Tunnel, o interno tem 265 voxels, dos quais 98 são buracos fechados
do oco do túnel (o túnel tem só 6 voxels de altura e o teto encosta no chão
em partes; ver `indian_tunnel_temp/README.md`).

Para pôr outra caverna: gere o SDF da grade de superfície dela com a
ferramenta do SDF e passe o nome (ou o caminho) em `--cavernas`.

### 7. Por que o alvo é o mesmo campo do peso

Os dois vêm do SDF da mesma caverna. Sem o peso, o CA só gera "geodos" sem
relação com a caverna, então guiar e pontuar com a mesma caverna é
inevitável. Até 22/11/2026 o alvo era o SDF com o zero deslocado 3 voxels
para fora (5.201 positivos no Elaphes); agora é **o próprio campo do peso**,
sem deslocamento, para avaliar exatamente os voxels que o SDF define como
caverna, sem a faixa extra de 3 voxels em volta. O que isso implica:

- **A cópia pura vale 1.** O peso binarizado (positivo vira vazio) acerta
  exatamente todos os positivos do alvo e nenhum negativo, que é a nota
  máxima. É a única nota de referência (ver abaixo).
- **A nota mede aderência ao campo, não ganho gerativo.** Uma nota perto de
  1 quer dizer que o CA reproduziu o sinal do peso que ele mesmo recebeu, não
  que gerou uma caverna nova parecida com a real.
- **No Elaphes, o positivo é a espessura da parede, não o ar do túnel** (ver
  a seção 1). A nota mede o quanto o CA acerta essa casca de 292 voxels, e não
  semelhança com o vazio real do Elaphes.

### 8. A referência: cópia pura

Junto com o resultado sai, por caverna, a nota da **cópia pura**: o peso
binarizado (`peso > 0` vira vazio), sem rodar o CA e sem passar pela faixa.
Com o alvo igual ao peso ela dá exatamente 1 em toda caverna. Ela fica como
conferência (se não der 1, peso e alvo não são o mesmo campo) e como régua:
a nota do CA se lê contra o 1. Até 22/11/2026 havia também o "teto trivial"
(o peso cortado no limiar do alvo); sem o limiar, ele é a mesma conta que a
cópia pura e saiu.

## Como usar

O campo de cada caverna é gerado uma vez com a ferramenta do SDF. Se algum
faltar, o `executar.py` para e diz o comando.

```bash
uv run python -m tools.sdf.sdf --log 1                                    # Elaphes
uv run python -m tools.sdf.sdf indian_tunnel_temp/npz/indian_tunnel_surface_64.npz --log 1
```

Depois, pelo atalho do Poe (as opções da tabela abaixo vão direto depois do
nome):

```bash
uv run poe ga                                      # GA, orçamento 400, só o Elaphes
uv run poe ga --cavernas elaphes indian_tunnel     # GA nas duas cavernas
uv run poe ga --orcamento 200 --seed 2 --top 5
uv run poe busca-aleatoria --orcamento 200         # controle, não é GA
```

O atalho só chama `python -m cavegen.optimization.genetic.executar`, que
também pode ser rodado direto.

O terminal mostra as quatro etapas enquanto roda (execução curta de
validação, 22/11/2026):

```
[1/4] Carregando as cavernas (o campo de cada uma é o peso e o alvo dela)
  elaphes  tools/sdf/npz/elaphes_surface_64_sdf_log1.npz
      grade 64x64x64, campo de -4.16 a +1.10, 292 voxels positivos; vazio aceito de 146 a 1460; cópia pura +1.000
  indian_tunnel  tools/sdf/npz/indian_tunnel_surface_64_sdf_log1.npz
      grade 64x64x64, campo de -3.89 a +1.10, 265 voxels positivos; vazio aceito de 132 a 1325; cópia pura +1.000
  genes chance_inicial [0.2, 0.8, de 0.02 em 0.02], sensibilidade [1, 20]
  seeds de ajuste [1, 2, 3, 4, 5]; reservadas 101 a 110 (10 seeds); 40 iterações sempre

[2/4] Busca genética: 40 candidatos, população 20, elite 2, seed 0
  geração   0 | 20/40 | melhor -0.073 (chance_inicial=0.5 sensibilidade=13) | válidos 3/20 | média -3.098 | 123.1 s
  candidato 23/40 · geração 1 · chance_inicial=0.68 sensibilidade=13 -> cortado (no fim: vazio_demais) · melhor -0.073

[3/4] Conferindo os 10 melhores nas 10 seeds reservadas, em 2 caverna(s)
   3/5 chance_inicial=0.66 sensibilidade=15: ajuste -0.577, reservadas -0.249 (elaphes -0.345, indian_tunnel -0.153), pior seed -2.184

[4/4] Gravando o resultado
```

- **geração**: uma linha por geração completa, com a melhor nota vista até
  ali, quantos da população não foram cortados, a média deles e o tempo da
  geração. Na busca aleatória, que não tem gerações, a linha sai a cada lote
  de 20 candidatos.
- **candidato**: a linha de baixo, reescrita no lugar a cada candidato, com os
  genes e a nota (ou `cortado`, com onde o vazio terminou nas seeds que
  acabaram fora da faixa, ou `[repetido]` quando veio do cache). Ela só
  aparece num terminal de verdade, não quando a saída vai para um arquivo.

O painel só imprime: com ou sem ele, a busca dá exatamente os mesmos
candidatos e notas.

Num terminal de verdade, o painel usa cores e emojis: notas positivas em
verde, negativas em amarelo e cortadas em vermelho; `⭐ novo recorde` quando
o melhor sobe numa geração; `⚠️ frágil` quando um parâmetro é cortado numa
seed reservada; medalhas nos 3 primeiros da lista final. Fora do terminal
(saída indo para arquivo) ou com a variável `NO_COLOR` definida, o texto sai
puro, como nos exemplos (só o `novo recorde` e o `frágil` aparecem sem a
estrela e o emoji). Se o console não imprime emoji (codificação sem
Unicode), ficam só as cores.

| opção | padrão | o que é |
|---|---|---|
| `--metodo` | `genetico` | `genetico` (o GA) ou `aleatoria` (a busca aleatória de controle) |
| `--cavernas` | `elaphes` | nomes ou caminhos `.npz`; um nome vira `tools/sdf/npz/<nome>_surface_64_sdf_log1.npz` |
| `--orcamento` | 400 | candidatos avaliados, contando repetidos |
| `--populacao` | 20 | cromossomos por geração (só no GA) |
| `--seed` | 0 | semente da **busca**, não do CA |
| `--saida` | `results/` desta pasta | onde gravar o `ga_NNN.npz` |
| `--top` | 10 | quantos melhores parâmetros listar no fim |

No fim o terminal mostra a lista dos melhores parâmetros, sem repetir
combinação e sem os cortados. O título diz o critério da ordem. Com uma
caverna:

```
5 melhores parâmetros, ordenados pela nota de ajuste (média das 5 seeds de ajuste em elaphes):
  reservadas: média nas 10 seeds reservadas; pior seed: a menor nota entre elas
  #  chance_inicial   sensibilidade iteracoes nota ajuste reservadas pior seed
  1            0.66              15        23      +0.172    cortado   cortado
  4            0.66              17         4      -0.414     -0.461    -0.839
```

Com várias, a nota de ajuste é a média entre as cavernas, seguida do mínimo,
do máximo e do desvio entre elas e da nota de cada uma:

```
5 melhores parâmetros, ordenados pela média entre as 2 cavernas nas 5 seeds de ajuste:
  mín, máx e desvio: entre as cavernas; reservadas: média entre as cavernas nas 10 seeds reservadas; pior seed: a menor nota entre elas
  #  chance_inicial   sensibilidade iteracoes média ajuste     mín     máx desvio elaphes indian_tunnel reservadas pior seed
  1             0.5              13        18       -0.073  -0.173  +0.028  0.100  -0.173        +0.028    cortado   cortado
  3            0.66              15        19       -0.577  -0.972  -0.182  0.395  -0.972        -0.182     -0.249    -2.184
```

`reservadas` é a média entre as cavernas nas 10 seeds reservadas; `pior seed`
é a menor nota de todas as seeds reservadas em todas as cavernas. Um
`cortado` nas reservadas quer dizer que o parâmetro passou nas 5 seeds de
ajuste, mas foi cortado em pelo menos uma reservada: ele é frágil. Para
comparar GA e busca aleatória com justiça, use o mesmo `--orcamento` e as
mesmas `--cavernas`. O consumo de tempo e memória da busca inteira vai para a
planilha do `track_resources`, com o nome do `ga_NNN` e as cavernas no
rótulo.

**Tempo.** Nesta máquina, cada candidato leva cerca de 3,1 s por caverna (5
seeds × 40 iterações em 64³): 3,1 s com o Elaphes, 6,1 s com o Elaphes e o
Indian Tunnel. No orçamento 400, o tempo depende de quantos candidatos se
repetem (o cache não refaz o CA): as execuções antigas do GA tiveram de 93 a
185 candidatos únicos, o que dá de 5 a 10 min por caverna; a busca aleatória
repete menos (cerca de 300 únicos entre os 620 pontos da grade), cerca de 15
min por caverna.

### O que fica no `ga_NNN.npz`

| campo | conteúdo |
|---|---|
| `genes_nomes`, `genes` | cromossomo de cada avaliação, na ordem em que foi feita |
| `notas`, `iteracoes`, `geracao` | nota (média entre as cavernas), melhor iteração e geração de cada avaliação |
| `melhor_acumulado` | melhor nota vista até cada avaliação: a curva GA × busca aleatória |
| `reaproveitadas` | candidatos repetidos que vieram do cache |
| `detalhes` | JSON por avaliação: `entre_cavernas` (média, mínimo, máximo, desvio e a nota de cada caverna) e, em `cavernas`, por caverna: a nota de cada seed na iteração escolhida, `fim` (onde o vazio terminou em cada seed), e o vazio e as mudanças em cada passo |
| `melhores` | a lista dos melhores: posição, genes, iterações, `nota_ajuste` (o critério), `ajuste` (o resumo entre as cavernas), `nota_reservada_media` e `reservadas` (o resumo nas reservadas, a pior seed e a nota de cada seed em cada caverna) |
| `campeao`, `nota_reservada_media` | o primeiro da lista, com o resumo de ajuste e das reservadas |
| `nota_copia_pura` | a cópia pura de cada caverna (1 quando o alvo é o peso) |
| `cavernas` | por caverna: `nome`, arquivo (`origem`), `sha256`, `convencao`, `limiar`, `escala_log`, `forma`, `referencia_alvo` (voxels positivos) e `faixa_vazio` |
| `criterio_ranking` | o critério da ordem, por extenso |
| `config`, `genes_limites`, `cortes`, `max_iteracoes`, `borda`, `modo_peso`, `sementes_*`, `seed`, `ambiente` | tudo o que é preciso para refazer a execução (inclui o commit) |

Os campos extras são strings JSON:

```python
import json
import numpy as np

with np.load("src/cavegen/optimization/genetic/results/ga_011.npz") as r:
    melhores = json.loads(str(r["melhores"]))
for m in melhores:
    print(m["posicao"], m["genes"], m["iteracoes"], m["nota_ajuste"],
          m["ajuste"]["por_caverna"], m["nota_reservada_media"])
```

### Usar em código

```python
from cavegen.optimization.genetic.algoritmo import ConfiguracaoGA, evoluir
from cavegen.optimization.genetic.ca import GENES_CA, AvaliadorCA
from cavegen.optimization.genetic.executar import (
    SEMENTES_AJUSTE,
    caminho_da_caverna,
    carregar_caverna,
)

cavernas = [carregar_caverna(caminho_da_caverna(nome))[0]
            for nome in ("elaphes", "indian_tunnel")]
avaliador = AvaliadorCA(cavernas, SEMENTES_AJUSTE)
nota, detalhes = avaliador({"chance_inicial": 0.5, "sensibilidade": 13})
print(nota, detalhes["iteracoes"], detalhes["entre_cavernas"])
resultado = evoluir(GENES_CA, avaliador, ConfiguracaoGA(orcamento=100), seed=0)
for a in resultado.melhores(10):  # sem repetidos e sem cortados, do melhor ao pior
    print(a.genes, a.nota, a.detalhes["iteracoes"], a.detalhes["entre_cavernas"]["por_caverna"])
```

## O decalque e a retirada da escala

As primeiras execuções (`ga_001` e `ga_002`, orçamento 200, seed 0, ainda com
o alvo antigo) tinham a escala do log como gene:

| método | campeão | nota ajuste | nota reservada |
|---|---|---|---|
| GA | chance 0,30, sensibilidade 1, escala 7,25, 7 iterações | 0,982 | 0,982 |
| aleatória | chance 0,51, sensibilidade 1, escala 9,19, 6 iterações | 0,975 | 0,979 |

As duas buscas foram parar na sensibilidade 1 com escala alta. É o
**decalque**: com a escala alta, o peso passa dos 27 vizinhos possíveis, os
vizinhos deixam de importar e a regra do CA vira um limiar sobre o SDF. O CA só
pinta a região do alvo, e seeds diferentes dão quase a mesma caverna (IoU entre
as seeds de 0,92 a 0,96). A nota fica perto do máximo (1) sem o CA gerar
nada.

O papel do SDF aqui é dar uma dica ao CA, não a resposta. Por isso a escala
saiu do cromossomo e ficou fixa em 1: o peso entra com os valores que o
arquivo tem. **`ga_001` e `ga_002` foram gerados com a escala como gene e não
são comparáveis com as execuções a partir de `ga_003`.**

Sem a escala (`ga_003` e `ga_004`, orçamento 100, seed 0, alvo antigo):

| método | campeão | nota ajuste | nota reservada | IoU entre seeds |
|---|---|---|---|---|
| GA | chance 0,56, sensibilidade 13, 23 iterações | 0,637 | 0,656 | 0,52 |
| aleatória | chance 0,42, sensibilidade 11, 20 iterações | 0,617 | 0,639 | 0,46 |

O decalque sumiu. Com sensibilidade de 1 a 8, a grade enche quase toda já no
primeiro passo e o candidato é cortado; as notas válidas começavam na
sensibilidade 9. Os campeões formavam caverna e variavam com a seed (IoU
0,46 a 0,52, contra 0,92 a 0,96 no decalque). O GA ficou só 0,02 acima da
busca aleatória, com uma seed de busca para cada um, o que ainda não mostra
que o GA ganha do sorteio.

A penalização por diversidade (`nota × (1 − IoU médio entre as cavernas das
seeds)`) segue como proposta em aberto, separada desta mudança.

## Testes

```bash
uv run python -m unittest tests/test_genetic.py tests/test_genetic_revisor.py tests/test_genetic_painel.py -v
```

`test_genetic.py` cobre o motor, a nota, a faixa de vazio, a cópia pura, o
resumo entre cavernas, a caverna, o avaliador (sem parada antecipada, com a
penalização preservada, várias cavernas) e o executor (5 seeds, `--cavernas`,
erros por caverna); `test_genetic_painel.py`, o observador e o painel.
`test_genetic_revisor.py` tem os testes adversariais do revisor (gene inteiro
com limite fracionário, orçamento exato, cache, tudo cortado sem NaN,
seeds reservadas fora da busca, reprodutibilidade do campeão gravado).

## Mais contexto

- Decisões e justificativas: `docs/methodology-adjustments.md`, blocos
  "Ajuste genético do CA" e "Revisão do ajuste genético do CA".
- Tarefas e critérios de aceite: `docs/tarefas-felipe-sdf-ca.md`.
- O SDF, o limiar, o log e a ordem entre eles: [`tools/sdf/README.md`](../../../../tools/sdf/README.md).
