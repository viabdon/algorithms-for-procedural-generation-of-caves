# optimization/genetic — ajuste genético do CA guiado por SDF

Procura os hiperparâmetros do Cellular Automata guiado por SDF que fazem a
caverna gerada cair em cima da caverna real do Elaphes (64³). O algoritmo
genético (GA) propõe as combinações, o CA gera as cavernas e uma nota diz o
quanto cada caverna acertou o campo-alvo. **No fim ele devolve a lista dos
melhores parâmetros com as notas** (os 10 primeiros, por padrão).

Existe também uma **busca aleatória** (`--metodo aleatoria`), que só sorteia
parâmetros com o mesmo orçamento. Ela é opcional e serve de controle: se o GA
não achar notas melhores que o sorteio, a seleção e a herança não estão
ajudando.

```
SDF do Elaphes com log (como está) ──> peso do CA ┐
                                                  ├─> CA (até 40 passos) ─> caverna
semente (chance_inicial, seed) ───────────────────┘          │
                                                             v
SDF do Elaphes com limiar -3 e log ────────────────> nota da caverna ─> GA escolhe os próximos
```

## Arquivos

| arquivo | o que tem |
|---|---|
| `algoritmo.py` | motor genérico do GA e a busca aleatória; não sabe o que é um CA |
| `aptidao.py` | a nota (`Alvo`), os cortes de vazio e as regras de parada antecipada |
| `ca.py` | o cromossomo do CA (`GENES_CA`) e o avaliador que roda o CA nas seeds |
| `executar.py` | linha de comando: carrega os campos, roda a busca, grava o resultado |
| `painel.py` | mostra o andamento no terminal (etapas, gerações, candidato atual) |
| `results/` | um `ga_NNN.npz` por execução (fora do Git) |

O motor (`algoritmo.py`) recebe só uma lista de genes e uma função de
avaliação, então o mesmo motor serve depois para o Random Walk: basta escrever
outro `ca.py` com os genes e o avaliador dele.

## Como um algoritmo genético funciona

É uma busca inspirada em seleção natural. Em vez de testar todas as
combinações (impossível com genes contínuos) ou só sortear, ele usa as boas
combinações já encontradas para propor as próximas.

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
alargada para 0,2 a 0,8 em 19/11/2026.

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

Ficam **fora** do cromossomo, fixos:

- **peso**: o campo do arquivo entra no CA **como está**. Nada o multiplica,
  comprime ou corta: se o peso de um voxel é 4, o CA recebe 4. Até 15/11/2026
  havia um terceiro gene, `escala_log_peso`, que multiplicava o log do SDF. Ele
  saiu e não virou constante (ver "O decalque e a retirada da escala");

- **borda**: sempre `NEAREST`, que repete a beirada da grade. `ZEROS` fecharia
  e `ONES` abriria a caverna onde ela toca a borda, e `RANDOM` depende da sorte;
- **iterações**: o CA roda até `MAX_ITERACOES = 40`, calcula a nota em todo
  passo e a melhor iteração sai junto com a nota (ver abaixo);
- **modo do peso**: sempre o completo. O modo "só negativo" existe no CA, mas
  ainda não entrou no GA. No Elaphes os dois deram o mesmo resultado, porque o
  peso positivo do SDF base é só a casca de 292 voxels.

## Peso e alvo

Os dois vêm do SDF da mesma caverna. Sem o peso, o CA só gera "geodos" sem
relação com o Elaphes, então guiar e pontuar com a mesma caverna é inevitável.
A diferença está no que cada um usa:

- **peso** (guia o CA): o SDF (interno +, borda 0, externo −) comprimido
  com `ln(1 + |d|)`, mantendo o sinal, gravado pela ferramenta do SDF com
  `--log 1`. No Elaphes ele vai de −4,16 a +1,10. A contagem de vizinhos vai de
  0 a 27, então o peso é uma **dica**: empurra a célula, mas os vizinhos ainda
  decidem. O avaliador guarda uma cópia somente leitura e passa ao CA
  exatamente esses valores.
- **alvo** (dá a nota): o SDF com o zero deslocado 3 voxels para fora e
  comprimido com log de escala 1. São 5.201 voxels positivos, a "caverna"
  que vale a pena acertar. Ele fica fixo durante toda a busca e é guardado
  somente leitura.

Os dois saem da ferramenta do SDF, em `tools/sdf/npz/`:
`elaphes_surface_64_sdf_log1.npz` (peso) e
`elaphes_surface_64_sdf_limiar-3_log1.npz` (alvo).

## A nota

```
nota = soma(alvo nos voxels vazios) / soma(alvo onde ele é positivo)
```

Vazio onde o alvo é positivo soma, vazio onde ele é negativo tira. O máximo é
1: vazio em todo o positivo e em nenhum negativo. A nota pode ser negativa.
Multiplicar o alvo por uma constante não muda a nota, porque ela aparece em
cima e embaixo da fração. Por isso a escala do log do alvo não importa, só se
tem log ou não.

### Cortes e parada antecipada

A quantidade de vazio aceita é relativa ao alvo, não à grade: de 0,5× a 5× os
5.201 voxels positivos, ou seja, de 2.600 a 26.005 voxels vazios. Fora dessa
faixa a nota do passo é `-inf` (`NOTA_MINIMA`), que nunca vence.

Depois de cada passo, o CA para antes das 40 iterações se:

| motivo | quando |
|---|---|
| `vazio_demais` | acima do máximo e **não diminuiu** no passo |
| `vazio_de_menos` | abaixo do mínimo e **não aumentou** no passo |
| `convergiu` | menos de 0,01% da grade trocou de estado (26 células ou menos, em 64³) |

O "não diminuiu / não aumentou" existe porque o ruído inicial nasce com cerca
de 45% de vazio, bem acima do máximo, e só encolhe com as iterações. Cortar
logo no passo 0 mataria todo candidato.

### Seeds e escolha da iteração

Cada candidato roda nas **seeds de ajuste** 1, 2 e 3. A nota de cada passo é
a média das três; a **melhor iteração** é o passo de maior média, e essa média
é a nota do candidato. Se uma seed é cortada, a média do passo vira `-inf`:
o candidato precisa funcionar em todas.

A regra de geração é "rodar até N iterações, parando antes se a parada
antecipada disparar". Ela é determinística, então depois da parada a nota fica
repetida até o fim. No final, cada parâmetro da lista dos melhores roda nas
**seeds reservadas** 101 a 110 com o número de iterações já escolhido, sem
escolher de novo. É a nota que mede se ele generaliza para seeds que a busca
nunca viu.

### Notas de referência

Junto com o campeão saem duas notas que não passam pelo CA nem pelos cortes,
para ler a nota do CA com contexto:

- **cópia pura**: o peso binarizado (positivo = vazio; o log não muda o
  sinal). No Elaphes dá 0,10, porque o interno tem só 292 voxels;
- **teto trivial**: o peso binarizado no limiar do alvo (SDF > −3, que no
  peso com log é > −ln 4 ≈ −1,39). Dá exatamente 1, porque o alvo é o próprio
  SDF deslocado.

Ou seja, a nota mede **aderência ao campo**, não ganho gerativo. Chegar perto
de 1 pode ser só o CA aprendendo a deslocar o limiar do peso.

## Como usar

O peso e o alvo são gerados uma vez com a ferramenta do SDF. Se algum faltar,
o `executar.py` para e diz o comando.

```bash
uv run python -m tools.sdf.sdf --log 1                  # peso: SDF com ln(1 + |d|)
uv run python -m tools.sdf.sdf --limiar -3 --log 1      # alvo
```

Depois, pelo atalho do Poe (as opções da tabela abaixo vão direto depois do
nome):

```bash
uv run poe ga                                  # GA, orçamento 400
uv run poe ga --orcamento 200 --seed 2 --top 5
uv run poe ga-aleatoria --orcamento 200        # controle
```

O atalho só chama `python -m cavegen.optimization.genetic.executar`, que
também pode ser rodado direto.

O terminal mostra as quatro etapas enquanto roda:

```
[1/4] Carregando o peso e o alvo
  peso  tools/sdf/npz/elaphes_surface_64_sdf_log1.npz (de -4.16 a +1.10)
  alvo  tools/sdf/npz/elaphes_surface_64_sdf_limiar-3_log1.npz (5201 voxels positivos; ...)

[2/4] Busca genética: 60 candidatos, população 20, elite 2, seed 0
  geração   0 | 20/60 | melhor +0.406 (chance_inicial=0.32 sensibilidade=9) | válidos 6/20 | média -2.785 | 2.5 s
  geração   1 | 38/60 | melhor +0.406 (...) | válidos 11/20 | média -0.720 | 1.7 s
  candidato 47/60 · geração 2 · chance_inicial=0.56 sensibilidade=13 -> +0.612 (15 it) · melhor +0.406

[3/4] Conferindo os 5 melhores nas 10 seeds reservadas
   1/5 chance_inicial=0.32 sensibilidade=9: ajuste +0.406, reservadas +0.412 (mín +0.176)

[4/4] Gravando o resultado
```

- **geração**: uma linha por geração completa, com a melhor nota vista até
  ali, quantos da população não foram cortados, a média deles e o tempo da
  geração. Na busca aleatória, que não tem gerações, a linha sai a cada lote
  de 20 candidatos.
- **candidato**: a linha de baixo, reescrita no lugar a cada candidato, com os
  genes e a nota (ou `cortado`, com o motivo, ou `[repetido]` quando veio do
  cache). Ela só aparece num terminal de verdade, não quando a saída vai para
  um arquivo.

O painel só imprime: com ou sem ele, a busca dá exatamente os mesmos
candidatos e notas.

Num terminal de verdade, o painel usa cores e emojis: notas positivas em
verde, negativas em amarelo e cortadas em vermelho; `⭐ novo recorde` quando
o melhor sobe numa geração; `⚠️ frágil` quando um parâmetro é cortado numa
seed reservada; medalhas nos 3 primeiros da lista final. Fora do terminal
(saída indo para arquivo) ou com a variável `NO_COLOR` definida, o texto sai
puro, como nos exemplos acima (só o `novo recorde` e o `frágil` aparecem
sem a estrela e o emoji). Se o console não imprime emoji (codificação
sem Unicode), ficam só as cores.

| opção | padrão | o que é |
|---|---|---|
| `--metodo` | `genetico` | `genetico` ou `aleatoria` |
| `--orcamento` | 400 | candidatos avaliados, contando repetidos |
| `--populacao` | 20 | cromossomos por geração (só no GA) |
| `--seed` | 0 | semente da **busca**, não do CA |
| `--peso` | SDF com log 1 do Elaphes | npz do `tools/sdf` usado como peso, sem nenhuma escala |
| `--alvo` | SDF com limiar −3 e log 1 | npz do `tools/sdf` usado como alvo |
| `--saida` | `results/` desta pasta | onde gravar o `ga_NNN.npz` |
| `--top` | 10 | quantos melhores parâmetros listar no fim |

No fim o terminal mostra a lista dos melhores parâmetros, sem repetir
combinação e sem os cortados, com a nota nas seeds de ajuste e a média e o
mínimo nas reservadas:

```
10 melhores parâmetros (nota nas sementes de ajuste e média e mínimo nas 10 reservadas):
  #  chance_inicial   sensibilidade iteracoes nota ajuste reservadas     mín
  1          0.5589              13        23      +0.637     +0.656  +0.560
  2          0.5467              13        15      +0.614     +0.639  +0.578
  3             0.3               9        14      +0.577     +0.591  +0.409
  4          0.5911              14        10      +0.497       -inf    -inf
  ...
```

Um `-inf` nas reservadas quer dizer que o parâmetro passou nas 3 seeds de
ajuste, mas foi cortado em pelo menos uma das reservadas: ele é frágil. Para
comparar GA e busca aleatória com justiça, use o mesmo `--orcamento`. O consumo de tempo e memória da busca
inteira vai para a planilha do `track_resources`, com o nome do `ga_NNN` no
rótulo para ligar a linha ao arquivo.

Com orçamento 100 o GA levou 15 s e a busca aleatória 11 s nesta máquina.

### O que fica no `ga_NNN.npz`

| campo | conteúdo |
|---|---|
| `genes_nomes`, `genes` | cromossomo de cada avaliação, na ordem em que foi feita |
| `notas`, `iteracoes`, `geracao` | nota, melhor iteração e geração de cada avaliação |
| `melhor_acumulado` | melhor nota vista até cada avaliação: a curva GA × aleatória |
| `reaproveitadas` | candidatos repetidos que vieram do cache |
| `detalhes` | JSON por avaliação: paradas, motivos, nota por seed, vazio e mudanças por passo |
| `melhores` | a lista dos melhores: posição, genes, iterações, nota de ajuste e nota por seed reservada (média, mínimo e cada uma) |
| `campeao`, `notas_reservadas`, `nota_reservada_media` | o primeiro da lista e como ele foi nas seeds reservadas |
| `nota_copia_pura`, `nota_teto_trivial` | as notas de referência |
| `config`, `genes_limites`, `cortes`, `faixa_vazio`, `sementes_*`, `alvo`, `ambiente` | tudo o que é preciso para refazer a execução (inclui o commit) |
| `peso`, `ambiente.arquivo_peso`, `ambiente.sha256_peso` | de qual arquivo veio o peso, com o limiar e o log que a ferramenta aplicou e o hash do arquivo |

Os campos extras são strings JSON:

```python
import json
import numpy as np

with np.load("src/cavegen/optimization/genetic/results/ga_005.npz") as r:
    melhores = json.loads(str(r["melhores"]))
for m in melhores:
    print(m["posicao"], m["genes"], m["iteracoes"], m["nota_ajuste"], m["nota_reservada_media"])
```

### Usar em código

```python
from cavegen.optimization.genetic.algoritmo import ConfiguracaoGA, evoluir
from cavegen.optimization.genetic.aptidao import Alvo
from cavegen.optimization.genetic.ca import GENES_CA, AvaliadorCA

from cavegen.optimization.genetic.executar import ALVO_ELAPHES, PESO_ELAPHES, carregar_campo

peso, _ = carregar_campo(PESO_ELAPHES)
campo_alvo, _ = carregar_campo(ALVO_ELAPHES)
avaliador = AvaliadorCA(peso, Alvo(campo_alvo), sementes=(1, 2, 3))
nota, detalhes = avaliador({"chance_inicial": 0.5, "sensibilidade": 13})
resultado = evoluir(GENES_CA, avaliador, ConfiguracaoGA(orcamento=100), seed=0)
for a in resultado.melhores(10):  # sem repetidos e sem cortados, do melhor ao pior
    print(a.genes, a.nota, a.detalhes["iteracoes"])
```

## O decalque e a retirada da escala

As primeiras execuções (`ga_001` e `ga_002`, orçamento 200, seed 0) tinham a
escala do log como gene:

| método | campeão | nota ajuste | nota reservada |
|---|---|---|---|
| GA | chance 0,30, sensibilidade 1, escala 7,25, 7 iterações | 0,982 | 0,982 |
| aleatória | chance 0,51, sensibilidade 1, escala 9,19, 6 iterações | 0,975 | 0,979 |

As duas buscas foram parar na sensibilidade 1 com escala alta. É o
**decalque**: com a escala alta, o peso passa dos 27 vizinhos possíveis, os
vizinhos deixam de importar e a regra do CA vira um limiar sobre o SDF. O CA só
pinta a região do alvo, e seeds diferentes dão quase a mesma caverna (IoU entre
as seeds de 0,92 a 0,96). A nota fica perto do teto trivial sem o CA gerar
nada.

O papel do SDF aqui é dar uma dica ao CA, não a resposta. Por isso a escala
saiu do cromossomo e não virou constante: o peso entra com os valores que o
arquivo tem. **`ga_001` e `ga_002` foram gerados com a escala como gene e não
são comparáveis com as execuções a partir de `ga_003`.**

Sem a escala (`ga_003` e `ga_004`, orçamento 100, seed 0):

| método | campeão | nota ajuste | nota reservada | IoU entre seeds |
|---|---|---|---|---|
| GA | chance 0,56, sensibilidade 13, 23 iterações | 0,637 | 0,656 | 0,52 |
| aleatória | chance 0,42, sensibilidade 11, 20 iterações | 0,617 | 0,639 | 0,46 |

O decalque sumiu. Com sensibilidade de 1 a 8, a grade enche quase toda já no
primeiro passo e o candidato é cortado (`vazio_demais`); as notas válidas
começam na sensibilidade 9. Os campeões formam caverna e variam com a seed
(IoU 0,46 a 0,52, contra 0,92 a 0,96 no decalque). O GA ficou só 0,02 acima
da busca aleatória, com uma seed de busca para cada um, o que ainda não mostra
que o GA ganha do sorteio.

A penalização por diversidade (`nota × (1 − IoU médio entre as cavernas das
seeds)`) segue como proposta em aberto, separada desta mudança.

## Testes

```bash
uv run python -m unittest tests/test_genetic.py tests/test_genetic_revisor.py tests/test_genetic_painel.py -v
```

`test_genetic.py` cobre o motor, a nota, os cortes, o avaliador e o executor;
`test_genetic_painel.py`, o observador e o painel.
`test_genetic_revisor.py` tem os testes adversariais do revisor (gene inteiro
com limite fracionário, orçamento exato, cache, tudo cortado sem NaN,
seeds reservadas fora da busca, reprodutibilidade do campeão gravado).

## Mais contexto

- Decisões e justificativas: `docs/methodology-adjustments.md`, bloco "Ajuste
  genético do CA".
- Tarefas e critérios de aceite: `docs/tarefas-felipe-sdf-ca.md`.
- O SDF, o limiar e o log: [`tools/sdf/README.md`](../../../../tools/sdf/README.md).
