# cellular_automata/genetico — ajuste genético do CA guiado por SDF

Procura os hiperparâmetros do Cellular Automata guiado por SDF que fazem a
caverna gerada cair em cima do campo de cavernas reais voxelizadas (todas as
que estiverem em `1_entrada/`). O algoritmo genético (GA) propõe as
combinações, o CA gera uma caverna para cada uma, em cada caverna real, e uma
nota diz o quanto cada caverna gerada acertou o campo daquela caverna. **No
fim ele devolve a lista dos melhores parâmetros com as notas** (os 10
primeiros, por padrão), num arquivo de texto e num relatório com figuras.

Existe também uma **busca aleatória** (`--metodo aleatoria`, ou
`uv run poe busca-aleatoria`). Ela **não é um algoritmo genético**: só sorteia
parâmetros dentro das mesmas faixas, com o mesmo orçamento e o mesmo
avaliador, sem seleção, cruzamento nem mutação. Serve de controle: se o GA
não achar notas melhores que o sorteio, a seleção e a herança não estão
ajudando.

O GA é só do CA: até 22/11/2026 ele morava em `src/cavegen/optimization/genetic/`
como um módulo genérico de otimização, e agora mora na área do CA.

## O pipeline

Cada etapa lê a pasta da anterior e escreve na seguinte:

```
1_entrada/      as grades de superfície das cavernas reais, 64³ (você põe aqui)
    │  etapa 2, campos.py: o SDF de cada grade, com ln(1 + |d|), escala 1, sem limiar
2_campos/       um campo por caverna: o peso que guia o CA e o alvo que dá a nota
    │  etapa 3, busca.py: o GA (ou a busca aleatória) roda o CA nos campos
    │  etapa 4, resultados.py: a lista legível e as figuras
3_resultados/   ga_NNN.npz (tudo), ga_NNN_melhores.md (lista) e ga_NNN_relatorio.html (figuras)
```

```bash
uv run poe ga                                   # o fluxo inteiro, com todas as cavernas da entrada
uv run poe ga --cavernas elaphes --orcamento 40 # só uma caverna, orçamento pequeno
uv run poe ga-campos [--forcar]                 # só a etapa 2
uv run poe ga-busca [--cavernas ...]            # só a etapa 3 (os campos precisam estar em dia)
uv run poe ga-resultados [ga_012]               # só a etapa 4 (padrão: a última execução)
```

- **Entrada** (`1_entrada/`): um `.npz` por caverna, com `surface_voxels`
  (1 = parede observada) e `metadata`, no formato da voxelização do projeto.
  O nome da caverna é o do arquivo sem `_surface_64` (`elaphes_surface_64.npz`
  vira `elaphes`). Para pôr outra caverna, basta copiar a grade dela para cá.
  Hoje há duas, **copiadas** de onde a voxelização as grava
  (`data/processed/references/elaphes_surface_64.npz` e
  `indian_tunnel_temp/npz/indian_tunnel_surface_64.npz`): são arquivos de 2 KB,
  fora do Git, e os originais continuam sendo a entrada padrão das ferramentas
  de SDF e do Indian Tunnel. O sha256 de cada grade fica gravado no campo e no
  resultado, então a origem não se perde.
- **Campos** (`2_campos/`): a etapa 2 chama a ferramenta do SDF
  (`cavegen.tools.sdf.sdf.gravar_campo`, a mesma de sempre, sem nada
  reimplementado). Um campo é **refeito** quando falta, quando a grade da
  entrada mudou (o sha256 dela, gravado no campo, não bate) ou quando a versão
  do cálculo do SDF (`VERSAO_SDF`) mudou; senão é **reaproveitado**.
  `--forcar` refaz todos.
- **Busca**: sem `--cavernas`, usa todas as cavernas da entrada; com
  `--cavernas elaphes indian_tunnel`, só essas. Rodada sozinha, ela recusa um
  campo que falte ou esteja desatualizado e diz para rodar a etapa 2.
- **Resultados** (`3_resultados/`): ver "Os resultados", abaixo.

As três pastas ficam no Git só com um `.gitkeep`: as grades são dados, os
campos são regenerados e os resultados são execuções.

> **Execuções antigas não são comparáveis.** `ga_001` a `ga_010`, em
> `3_resultados/`, usaram o alvo antigo (SDF do Elaphes com limiar −3 e log,
> 5.201 voxels positivos, vazio aceito de 2.600,5 a 26.005), 3 seeds de ajuste,
> parada antecipada e só o Elaphes. A partir de 22/11/2026 o alvo é o próprio
> campo do peso, as seeds de ajuste são 5, o CA roda sempre as 40 iterações e
> pode haver várias cavernas (ver `docs/methodology-adjustments.md`). As
> notas antigas e novas medem coisas diferentes e não devem ser postas lado a
> lado. Os arquivos antigos ficam como estão, com os campos antigos (`peso`,
> `alvo`, `nota_teto_trivial`...), e a etapa 4 recusa esse formato dizendo por
> quê. `ga_011` já é do formato novo, mas foi gravado antes da nota por passo
> (a figura da trajetória dele mostra só o vazio).

## Arquivos

| arquivo | o que tem |
|---|---|
| `pipeline.py` | o fluxo inteiro: etapa 2, etapa 3 e etapa 4, em sequência |
| `campos.py` | etapa 2: as cavernas da entrada, o campo de cada uma e quando refazê-lo |
| `busca.py` | etapa 3: carrega os campos, roda a busca, confere nas seeds reservadas, grava o npz |
| `resultados.py` | etapa 4: lê o npz, grava a lista legível e o relatório, imprime o resumo |
| `figuras.py` | as figuras em Plotly, a partir do npz, sem depender de interface |
| `algoritmo.py` | motor genérico do GA e a busca aleatória de controle; não conhece o CA |
| `aptidao.py` | a nota (`Alvo`), a faixa de vazio aceita (`Cortes`), a cópia pura e o resumo entre cavernas |
| `ca.py` | o cromossomo do CA (`GENES_CA`), a caverna (`Caverna`) e o avaliador que roda o CA nas cavernas e seeds |
| `painel.py` | mostra o andamento no terminal (etapas, gerações, candidato atual, ranking) |

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
ferramenta [`cavegen/tools/sdf`](../../../tools/sdf/README.md) faz isso em três
passos, a partir da grade de superfície voxelizada (1 = parede observada):

1. **Inundação** ([`cavegen/tools/flood_fill`](../../../tools/flood_fill/README.md)):
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
(`2_campos/elaphes_surface_64_sdf_log1.npz`):

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
ordem inversa estão no [README do `cavegen/tools/sdf`](../../../tools/sdf/README.md#3-manipulação-limiar-e-log).

### 3. A nota de uma caverna

```
nota = soma(alvo nos voxels vazios) / soma(alvo onde ele é positivo)
```

- **O numerador** percorre os voxels que a caverna gerada deixou vazios e
  soma o valor do alvo em cada um. Vazio no interno soma (+0,69 a +1,10),
  vazio na borda não muda nada (0), vazio no externo **desconta** (−0,69 a
  −4,16). Sem o desconto, encher a grade inteira acertaria todo o interno e
  ganharia a nota máxima; com ele, encher a grade do Elaphes dá −4.033
  (quatro mil; −4.045,6 no Indian Tunnel). Esse valor fica gravado em cada
  execução (`nota_grade_cheia`) e sai no painel, como régua das notas
  negativas.
- **O denominador** é o máximo que o numerador pode alcançar: vazio em todo
  voxel positivo e em nenhum negativo. No Elaphes ele vale 210,35 (a soma
  dos 292 internos); no Indian Tunnel, 191,63.
- **Por que o teto é 1**: o numerador nunca passa do denominador, porque o
  melhor que dá para fazer é somar todos os positivos sem descontar nada.
  Dividir um pelo outro dá 1 nesse caso, 0 com a grade toda rocha (nenhum
  vazio, nada somado) e um número negativo quando o vazio fora pesa mais que
  o de dentro. O piso é o vazio só no externo, 1 abaixo da grade cheia
  (−4.034,2 no Elaphes): a nota pode ser muito negativa, e as notas de uma
  execução vão de perto de +1 a perto de −4.000.
- **Por que a nota sai "quebrada"** (0,543 e não 10 mil pontos): ela é a
  **fração do máximo possível**. 0,543 quer dizer que a caverna gerada somou
  54,3% do que a caverna perfeita somaria, já descontado o vazio fora. A
  soma crua dependeria do tamanho e da forma de cada caverna (210,35 no
  Elaphes, 191,63 no Indian Tunnel) e não daria para comparar cavernas.
  Dividindo, a nota fica na mesma régua em todas, e multiplicar o alvo por
  qualquer constante não a muda (a constante aparece em cima e embaixo).
- Um exemplo de equilíbrio: no Elaphes, um voxel vazio em d = −1 (−0,69)
  cancela exatamente um voxel vazio em d = +1 (+0,69).

### 4. O vazio mínimo aceito

Antes da nota, o vazio total da caverna gerada precisa passar de um mínimo
relativo ao **número de voxels positivos do alvo** (não à grade):

```
vazio ≥ 0,5 × positivos      (Cortes: fator_minimo; fator_maximo = None)
```

Abaixo dele, a nota daquele passo é `-inf` (`NOTA_MINIMA`), que nunca vence.

| caverna | voxels positivos | vazio aceito |
|---|---|---|
| Elaphes 64³ | 292 | a partir de 146 |
| Indian Tunnel 64³ | 265 | a partir de 132,5 |

Por que existe: sem o mínimo, uma grade toda rocha (nota 0) venceria qualquer
caverna que escavasse um pouco fora da forma (nota negativa). O mínimo **não
interrompe o CA**: ele roda as 40 iterações e o mínimo só decide a nota de
cada passo.

**Até 22/11/2026 havia também um máximo** (5 × positivos: 1.460 voxels no
Elaphes). Ele saiu por decisão do Felipe: com o alvo igual ao peso, a própria
nota já pune o excesso de vazio (encher a grade dá −4.033), e o máximo
transformava a maioria dos candidatos em `-inf`, sem direção para a seleção.
Na validação curta com ele (orçamento 40), só 5 de 31 candidatos tinham nota;
sem ele, na mesma execução, 23 de 29. `Cortes(0.5, 5.0)` ainda reproduz a
regra antiga, e as execuções gravadas com ela continuam legíveis (o
`faixa_vazio` delas tem os dois limites; o das novas tem `null` no máximo).

Com o máximo fora, as notas ficam em escalas muito diferentes (de +1 a cerca
de −4.000). O painel e a lista dos melhores mostram a nota de verdade, com as
colunas largas o bastante; as figuras usam uma escala log simétrica (ver
[Os resultados](#os-resultados)).

**Até 22/11/2026 havia parada antecipada**: o CA parava antes das 40
iterações se o vazio estivesse acima do máximo sem diminuir, abaixo do mínimo
sem aumentar, ou se menos de 0,01% da grade mudasse num passo
(convergência). Ela saiu porque o GA é rápido e tem poucos genes: economizar
tempo não importa, e é melhor que a nota de cada passo venha da grade de
verdade. A parada por convergência também saiu: com o corte em 0,01% (26
células em 64³), ela repetia a nota do passo em que parou mesmo quando ainda
mudavam algumas células, e sem ela o código fica mais simples. A
penalização continuou igual, e esvaziar a grade inteira dá `-inf` em todo
passo. Encher a grade, desde a saída do máximo, não é mais cortado: o passo
cheio vale a nota da grade cheia, mas como a iteração escolhida é a de maior
nota (seção 5), um candidato que enche aos poucos leva a nota do passo menos
cheio, quase sempre o 1. Na validação (`ga_013`), 18 dos 23 candidatos com
nota escolheram a iteração 1: 13 deles terminam a iteração 40 com mais de
100 mil voxels de vazio (de 262 mil), e os outros morrem.

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

O mesmo candidato é avaliado em todas as cavernas da busca. Cada
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

**Não é teste de generalização.** Todas as cavernas escolhidas entram na
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
escala 1 e sem limiar, como a etapa 2 grava; outro limiar ou outro log
param a execução dizendo qual caverna. O SDF precisa de pelo menos um voxel
positivo (senão a nota dividiria por zero), e a grade precisa ser cúbica
(a semente do CA é um cubo); nos dois casos o erro diz qual caverna e por
quê. A mesma caverna duas vezes também é recusada, mesmo com outro nome
(mesmo sha256), porque pesaria em dobro na média. Uma grade cúbica de
outro lado (32³, por exemplo) roda, mas o painel
avisa: o protocolo é 64³, e um voxel de 32³ é duas vezes maior por lado,
então a mesma sensibilidade não quer dizer a mesma coisa nas duas.

**Grades de superfície que já existem no projeto** (22/11/2026):

| caverna | grade | de onde veio | no GA |
|---|---|---|---|
| Elaphes | 64³, 1.049 voxels de superfície | `data/processed/references/elaphes_surface_64.npz` | copiada para `1_entrada/` |
| Indian Tunnel (NASA) | 64³, 1.145 voxels de superfície | `indian_tunnel_temp/npz/indian_tunnel_surface_64.npz` | copiada para `1_entrada/` |
| Elaphes (do Pablo) | 32³, 245 voxels de superfície | `data/processed/references/elaphes_surface_32_pablo.npz` | fora: é a mesma caverna em outra resolução |

No Indian Tunnel, o interno tem 265 voxels, dos quais 98 são buracos fechados
do oco do túnel (o túnel tem só 6 voxels de altura e o teto encosta no chão
em partes; ver `indian_tunnel_temp/README.md`).

Para pôr outra caverna: copie a grade de superfície dela para `1_entrada/`;
na próxima execução o pipeline gera o campo e a inclui.

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

```bash
uv run poe ga                                      # GA, orçamento 400, todas as cavernas da entrada
uv run poe ga --cavernas elaphes                   # só o Elaphes
uv run poe ga --orcamento 200 --seed 2 --top 5
uv run poe busca-aleatoria --orcamento 200         # o mesmo fluxo com a busca de controle (não é GA)
```

O atalho chama `python -m cavegen.generators.cellular_automata.genetico.pipeline`,
que também pode ser rodado direto. O terminal mostra a etapa 2 (o que foi
gerado ou reaproveitado), as quatro partes da busca e onde ficaram os
relatórios (execução curta de validação, 22/11/2026):

```
== Etapa 2: campos (SDF com log x1, sem limiar) ==
  elaphes: reaproveitado (elaphes_surface_64_sdf_log1.npz)
  indian_tunnel: reaproveitado (indian_tunnel_surface_64_sdf_log1.npz)

== Etapa 3: busca ==

[1/4] Carregando as cavernas (o campo de cada uma é o peso e o alvo dela)
  elaphes  src/cavegen/generators/cellular_automata/genetico/2_campos/elaphes_surface_64_sdf_log1.npz
      grade 64x64x64, campo de -4.16 a +1.10, 292 voxels positivos; vazio aceito a partir de 146
      cópia pura +1.000, grade cheia -4033.246
  indian_tunnel  src/cavegen/generators/cellular_automata/genetico/2_campos/indian_tunnel_surface_64_sdf_log1.npz
      grade 64x64x64, campo de -3.89 a +1.10, 265 voxels positivos; vazio aceito a partir de 132
      cópia pura +1.000, grade cheia -4045.606
  genes chance_inicial [0.2, 0.8, de 0.02 em 0.02], sensibilidade [1, 20]
  seeds de ajuste [1, 2, 3, 4, 5]; reservadas 101 a 110 (10 seeds); 40 iterações sempre

[2/4] Busca genética: 40 candidatos, população 20, elite 2, seed 0
  geração   0 | 20/40 | melhor -0.073 (chance_inicial=0.5 sensibilidade=13) | válidos 15/20 | mediana -2848.781 | 123.9 s
  candidato 23/40 · geração 1 · chance_inicial=0.68 sensibilidade=13 -> -1243.096 · melhor -0.073

[3/4] Conferindo os 10 melhores nas 10 seeds reservadas, em 2 caverna(s)
   3/5 chance_inicial=0.66 sensibilidade=15: ajuste -0.577, reservadas -0.249 (elaphes -0.345, indian_tunnel -0.153), pior seed -2.184

[4/4] Gravando o resultado
(... a tabela dos melhores ...)

== Etapa 4: resultados ==
  lista dos melhores  src/cavegen/generators/cellular_automata/genetico/3_resultados/ga_013_melhores.md
  relatório           src/cavegen/generators/cellular_automata/genetico/3_resultados/ga_013_relatorio.html  (abra no navegador)
```

- **geração**: uma linha por geração completa, com a melhor nota vista até
  ali, quantos da população não foram cortados, a mediana deles e o tempo da
  geração. Mediana, e não média: as notas vão de +1 a cerca de −4.000, e um
  candidato que enche a grade puxaria a média da geração inteira para lá.
  As colunas das tabelas crescem até caber o maior número. Na busca aleatória, que não tem gerações, a linha sai a cada lote
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
| `--cavernas` | todas as da entrada | nomes das cavernas de `1_entrada/` (na etapa 3 sozinha, também um caminho `.npz` de campo) |
| `--forcar` | não | refaz todos os campos, mesmo os em dia (pipeline e etapa 2) |
| `--metodo` | `genetico` | `genetico` (o GA) ou `aleatoria` (a busca aleatória de controle) |
| `--orcamento` | 400 | candidatos avaliados, contando repetidos |
| `--populacao` | 20 | cromossomos por geração (só no GA) |
| `--seed` | 0 | semente da **busca**, não do CA |
| `--top` | 10 | quantos melhores parâmetros listar no fim |
| `--entrada`, `--campos`, `--saida` | `1_entrada/`, `2_campos/`, `3_resultados/` | as pastas do fluxo |

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
10 melhores parâmetros, ordenados pela média entre as 2 cavernas nas 5 seeds de ajuste:
  mín, máx e desvio: entre as cavernas; reservadas: média entre as cavernas nas 10 seeds reservadas; pior seed: a menor nota entre elas
  #  chance_inicial   sensibilidade iteracoes média ajuste      mín      máx  desvio  elaphes indian_tunnel reservadas pior seed
  1             0.5              13        18       -0.073   -0.173   +0.028   0.100   -0.173        +0.028    cortado   cortado
  2            0.66              15        19       -0.577   -0.972   -0.182   0.395   -0.972        -0.182     -0.249    -2.184
 10             0.8              15        40     -540.946 -657.194 -424.697 116.248 -424.697      -657.194   -568.425  -752.550
```

Como ler notas tão diferentes (de `ga_013`, 22/11/2026, sem o limite de
cima): +1 é a cópia pura, 0 a grade sem vazio, e a grade cheia fica perto de
−4.000 (o valor de cada caverna sai no cabeçalho). Abaixo de −1, já há mais
vazio fora da forma do que a forma inteira vale. Média, mínimo e desvio entre
as cavernas estão na mesma unidade da nota: o desvio de 116 na linha 10 é
pequeno perto de −541 (as duas cavernas concordam que o parâmetro é ruim); o
de 0,100 na linha 1 é grande perto de −0,073 (uma caverna fica positiva e a
outra negativa). As duas cavernas têm quase a mesma grade cheia (−4.033 e
−4.046), então nenhuma domina a média por ter um piso mais fundo.

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
repetem (o cache não refaz o CA): as execuções do GA tiveram de 93 a 185
candidatos únicos (`ga_011`: 97), o que dá de 5 a 10 min por caverna; a
busca aleatória repete menos (cerca de 300 únicos entre os 620 pontos da
grade), cerca de 15 min por caverna. A etapa 2 leva poucos segundos por
caverna, e só quando o campo precisa ser refeito.

## Os resultados

Cada execução deixa três arquivos em `3_resultados/`, com o mesmo número:

| arquivo | o que é | como abrir |
|---|---|---|
| `ga_NNN_melhores.md` | os N melhores parâmetros (padrão 10) numa tabela de texto, com o resumo da execução e como testar uma linha no CA | qualquer editor de texto; no VS Code, a pré-visualização do Markdown mostra a tabela formatada |
| `ga_NNN_relatorio.html` | as figuras da execução e a mesma tabela | o navegador (o Plotly vem da internet, como nos outros HTML do projeto) |
| `ga_NNN.npz` | o registro completo da execução, para análise e reprodução | Python, ou `uv run poe ga-resultados ga_NNN`, que imprime o resumo sem escrever código |

A lista e a tabela do relatório saem do npz por uma função só
(`resultados.tabela_dos_melhores`), e a etapa 4 refaz os dois de qualquer
execução no formato novo:

```bash
uv run poe ga-resultados                      # a última execução
uv run poe ga-resultados ga_012               # uma execução (ou só o número: 12)
uv run poe ga-resultados 12 --comparar 13     # põe a curva de outra execução na primeira figura
```

Com `--comparar`, a etapa avisa (no terminal e no relatório) quando as
execuções não são comparáveis: cavernas ou campos, orçamento, seeds de
ajuste, faixa de vazio, iterações ou faixas dos genes diferentes. A curva
sai mesmo assim, porque comparar orçamentos diferentes pode ser de propósito.

**A lista dos melhores.** Uma linha por parâmetro: posição, `chance_inicial`,
`sensibilidade`, iterações, a nota média entre as cavernas (o critério da
ordem), a nota de cada caverna, o mínimo e o desvio entre elas, e nas seeds
reservadas a média e a pior seed. A tabela do terminal e a do HTML são a
mesma informação; a lista em Markdown existe para abrir sem navegador e sem
código. Para testar uma linha no CA: importe o campo da caverna como peso
(`uv run python -m cavegen.generators.cellular_automata.pesos <campo em 2_campos/>`)
e, no menu do CA (`uv run poe menu-ca`), use a chance inicial, a
sensibilidade, as iterações, a borda `nearest` e esse peso no modo completo.
O menu sorteia a matriz inicial sem seed fixa, então a caverna sai diferente
das seeds de ajuste: a nota da tabela é a média de 5 grades.

**As figuras do relatório** (todas em `figuras.py`, uma função por figura):

| figura | o que mostra | função |
|---|---|---|
| Melhor nota ao longo das avaliações | se a busca ainda sobe no fim do orçamento; com `--comparar`, o GA contra a busca aleatória na mesma figura | `figura_melhor_acumulado` |
| Mapa das notas pelos dois genes | a nota de cada combinação, com a chance inicial num eixo e a sensibilidade no outro: quase o espaço de busca inteiro. X vermelho é cortado pela faixa de vazio; célula vazia nunca foi pedida; a estrela é o campeão. A cor vai de −10.000 a +1 em log simétrico, fixa, com o zero no meio da paleta divergente: a mesma cor quer dizer a mesma nota em qualquer execução, e positivo nunca se confunde com negativo | `figura_mapa_dos_genes` |
| Nota de cada caverna nos melhores | as cavernas lado a lado, com a média e o desvio entre elas: quem é consistente e quem só vai bem numa | `figura_notas_por_caverna` |
| Notas por geração | a distribuição das notas em cada geração (na busca aleatória, em cada lote de sorteios) e a parte cortada | `figura_notas_por_geracao` |
| O campeão ao longo das iterações do CA | a nota de cada passo em cada caverna e a média, com a iteração escolhida marcada, e embaixo o vazio de cada seed com a faixa aceita sombreada (sem limite de cima, do mínimo até a grade cheia) | `figura_trajetoria` (outro da lista: `posicao=`) |
| Ajuste × seeds reservadas | a nota nas seeds da busca contra a nota em seeds que ela nunca viu; abaixo da diagonal ou com X, o parâmetro foi bem só nas grades da busca | `figura_ajuste_x_reservadas` |

**A escala das notas nas figuras (22/11/2026).** Sem o limite de cima do
vazio, as notas de uma execução vão de perto de +1 a perto de −4.000, e o que
importa ler fica entre −1 e +1. Num eixo linear, um único candidato que enche
a grade achataria todos os outros numa linha. Por isso todo eixo de nota (e a
cor do mapa) usa a escala log simétrica

```
y = sinal(nota) · log10(1 + |nota| / 0,1)
```

Perto do zero (|nota| bem menor que 0,1) ela é quase linear e guarda o sinal;
longe dele, cada década (−1, −10, −100, −1.000) ocupa o mesmo espaço. As
alternativas foram descartadas: cortar o eixo esconderia os candidatos que
enchem a grade (são a maioria em várias gerações) e mudaria de uma execução
para outra; o log comum não aceita nota negativa nem zero. As marcas dos
eixos e o hover mostram a nota de verdade, e o relatório explica a escala
acima das figuras. Na figura da nota por caverna, a barra de erro é
média ± desvio em nota de verdade, por isso fica assimétrica no eixo
comprimido. Nas caixas das notas por geração, a mediana e os quartis caem nos
mesmos candidatos (a compressão só cresce).

As duas últimas foram acrescentadas além do pedido inicial: a trajetória
mostra por que um campeão é frágil (o vazio só atravessa a faixa), e o
ajuste × reservadas é a leitura direta de quanto a nota generaliza para
grades novas. `figuras_da_execucao` devolve todas, na ordem, com título e
legenda: é o que uma aba do Streamlit chamaria, sem refazer nada. Para gerar
uma figura sozinha:

```python
from cavegen.generators.cellular_automata.genetico import figuras, resultados

execucao = resultados.ler_execucao("src/cavegen/generators/cellular_automata/genetico/3_resultados/ga_012.npz")
figuras.figura_mapa_dos_genes(execucao).write_html("mapa.html", include_plotlyjs="cdn")
```

### O que é o `ga_NNN.npz`, em linguagem simples

É um arquivo compactado do NumPy com várias "gavetas" (campos), cada uma
com um nome. Ele guarda **tudo** da execução: cada candidato que a busca
pediu, a nota dele, os detalhes de cada caverna e seed, a lista dos melhores,
a configuração e a máquina. Serve para analisar a execução depois e para
refazê-la exatamente. Algumas gavetas são números (arrays); as outras são
texto no formato JSON (dicionários e listas), que precisa ser decodificado.
Não é preciso abri-lo para saber os melhores: a lista em Markdown e o
relatório já saem dele.

| campo | o que guarda | para que serve |
|---|---|---|
| `metodo` | `genetico` ou `aleatoria` | saber qual busca rodou |
| `genes_nomes`, `genes` | os nomes dos genes e, para cada candidato pedido (na ordem), o valor de cada gene | refazer o mapa do espaço de busca |
| `notas` | a nota de cada candidato (média entre as cavernas; `-inf` se cortado) | a mesma ordem de `genes` |
| `iteracoes`, `geracao` | a iteração escolhida e a geração de cada candidato | a distribuição por geração |
| `melhor_acumulado` | a melhor nota vista até cada candidato | a curva GA × busca aleatória |
| `reaproveitadas` | quantos candidatos se repetiram (vieram do cache) | saber o custo de verdade |
| `detalhes` (JSON) | por candidato: `entre_cavernas` (média, mínimo, máximo, desvio, nota de cada caverna) e, em `cavernas`, por caverna: a nota de cada seed na iteração escolhida, a nota de cada passo (`notas_por_passo`, a média das seeds), onde o vazio terminou em cada seed (`fim`), e o vazio e as mudanças em cada passo | a trajetória de qualquer candidato |
| `melhores` (JSON) | a lista dos melhores: posição, genes, iterações, `nota_ajuste` (o critério), `ajuste` (o resumo entre as cavernas), `nota_reservada_media` e `reservadas` (o resumo nas seeds reservadas, a pior seed e a nota de cada seed em cada caverna) | a lista legível sai daqui |
| `campeao`, `nota_reservada_media` (JSON) | o primeiro da lista, com o ajuste e as reservadas | a leitura rápida |
| `nota_copia_pura` (JSON) | a cópia pura de cada caverna (1 quando o alvo é o peso) | a régua da nota |
| `cavernas` (JSON) | por caverna: `nome`, a grade de entrada (`entrada`) e o `sha256_entrada` dela, o arquivo do campo (`origem`) e o `sha256` dele, a versão do cálculo (`versao_sdf`), se o campo foi conferido com a grade da entrada (`conferido_com_entrada`: sim quando a caverna veio por nome, não quando veio um `.npz` direto), `convencao`, `limiar`, `escala_log`, `forma`, `referencia_alvo` (voxels positivos), `faixa_vazio` (o mínimo e o máximo de vazio aceitos, em voxels; o máximo é `null` desde 22/11/2026) e `nota_grade_cheia` (a nota de tudo vazio, a régua das notas negativas; só nas execuções a partir de 22/11/2026, depois da saída do máximo) | saber exatamente de qual arquivo e de qual versão veio cada caverna |
| `criterio_ranking` (JSON) | o critério da ordem, por extenso | ler o ranking sem adivinhar |
| `config`, `genes_limites`, `cortes`, `max_iteracoes`, `borda`, `modo_peso`, `sementes_ajuste`, `sementes_reservadas`, `seed`, `ambiente` (JSON) | os parâmetros do GA, as faixas dos genes, a faixa de vazio, o CA, as seeds, a semente da busca e a máquina, as versões e o commit | refazer a execução |

O jeito mais curto de ler, sem decodificar nada à mão:

```python
from cavegen.generators.cellular_automata.genetico.resultados import ler_execucao

execucao = ler_execucao("src/cavegen/generators/cellular_automata/genetico/3_resultados/ga_012.npz")
for m in execucao["melhores"]:
    print(m["posicao"], m["genes"], m["iteracoes"], m["nota_ajuste"], m["ajuste"]["por_caverna"])
```

À mão, com o NumPy: `np.load(caminho)["notas"]` para um array, e
`json.loads(str(np.load(caminho)["melhores"]))` para um campo JSON.

### Usar em código

```python
from cavegen.generators.cellular_automata.genetico.algoritmo import ConfiguracaoGA, evoluir
from cavegen.generators.cellular_automata.genetico.busca import (
    SEMENTES_AJUSTE,
    carregar_caverna,
    resolver_cavernas,
)
from cavegen.generators.cellular_automata.genetico.ca import GENES_CA, AvaliadorCA

# Os campos em dia de 2_campos/ (rode a etapa 2 antes), de todas as cavernas da entrada.
cavernas = [carregar_caverna(caminho)[0] for caminho in resolver_cavernas(None)]
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
uv run python -m unittest tests/test_genetic.py tests/test_genetic_revisor.py tests/test_genetic_painel.py tests/test_genetico_pipeline.py -v
```

`test_genetic.py` cobre o motor, a nota, a faixa de vazio, a cópia pura, o
resumo entre cavernas, a caverna, o avaliador (sem parada antecipada, com a
penalização preservada, várias cavernas) e a busca (5 seeds, `--cavernas`,
erros por caverna); `test_genetic_painel.py`, o observador e o painel.
`test_genetic_revisor.py` tem os testes adversariais do revisor (gene inteiro
com limite fracionário, orçamento exato, cache, tudo cortado sem NaN,
seeds reservadas fora da busca, reprodutibilidade do campeão gravado).
`test_genetico_pipeline.py` roda o pipeline com duas cavernas sintéticas 16³:
campos gerados, reaproveitados e refeitos (grade mudou, versão mudou,
`--forcar`), escolha de cavernas, a busca recusando campo desatualizado, a
rastreabilidade gravada, a lista em Markdown e as figuras a partir do npz.

## Mais contexto

- Decisões e justificativas: `docs/methodology-adjustments.md`, blocos
  "Ajuste genético do CA", "Revisão do ajuste genético do CA" e "O GA na área
  do CA, em pipeline".
- Tarefas e critérios de aceite: `docs/tarefas-felipe-sdf-ca.md`.
- O SDF, o limiar, o log e a ordem entre eles: [`cavegen/tools/sdf/README.md`](../../../tools/sdf/README.md).
