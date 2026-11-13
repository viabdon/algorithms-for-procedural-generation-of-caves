# optimization/genetic — ajuste genético do CA guiado por SDF

Procura os hiperparâmetros do Cellular Automata guiado por SDF que fazem a
caverna gerada cair em cima da caverna real do Elaphes (64³). O algoritmo
genético (GA) propõe as combinações, o CA gera as cavernas e uma nota diz o
quanto cada caverna acertou o campo-alvo. Ao lado do GA roda uma **busca
aleatória** com o mesmo orçamento: ela é o controle que diz se o GA ganhou
alguma coisa com seleção e herança, ou se só sortear daria o mesmo.

```
SDF base do Elaphes ──log(escala)──> peso do CA ─┐
                                                 ├─> CA (até 50 passos) ─> caverna
semente (chance_inicial, seed) ──────────────────┘          │
                                                            v
SDF do Elaphes com limiar -3 e log ───────────────> nota da caverna ─> GA escolhe os próximos
```

## Arquivos

| arquivo | o que tem |
|---|---|
| `algoritmo.py` | motor genérico do GA e a busca aleatória; não sabe o que é um CA |
| `aptidao.py` | a nota (`Alvo`), os cortes de vazio e as regras de parada antecipada |
| `ca.py` | o cromossomo do CA (`GENES_CA`) e o avaliador que roda o CA nas seeds |
| `executar.py` | linha de comando: carrega os campos, roda a busca, grava o resultado |
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
     da faixa do gene e devolve o valor para dentro da faixa. É o que permite
     achar valores que nenhum pai tinha;
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
12/11/2026, com folga em volta das melhores notas.

| gene | faixa | o que faz |
|---|---|---|
| `chance_inicial` | 0,3 a 0,7 | chance de cada célula da semente nascer vazia |
| `sensibilidade` | 1 a 20, inteiro | mínimo de vizinhos (com o peso somado) para a célula ficar vazia; de 18 para cima a caverna sempre morria |
| `escala_log_peso` | 0,25 a 12 | escala do log aplicado ao SDF base antes de virar peso; as notas saturavam de 4 a 8 |

Ficam **fora** do cromossomo, fixos:

- **borda**: sempre `NEAREST`, que repete a beirada da grade. `ZEROS` fecharia
  e `ONES` abriria a caverna onde ela toca a borda, e `RANDOM` depende da sorte;
- **iterações**: o CA roda até `MAX_ITERACOES = 50`, calcula a nota em todo
  passo e a melhor iteração sai junto com a nota (ver abaixo);
- **modo do peso**: sempre o completo. O modo "só negativo" existe no CA, mas
  ainda não entrou no GA. No Elaphes os dois deram o mesmo resultado, porque o
  peso positivo do SDF base é só a casca de 292 voxels.

## Peso e alvo

Os dois vêm do SDF da mesma caverna. Sem o peso, o CA só gera "geodos" sem
relação com o Elaphes, então guiar e pontuar com a mesma caverna é inevitável.
A diferença está no que cada um usa:

- **peso** (guia o CA): o SDF base (interno +, borda 0, externo −) com
  `comprimir_log(sdf, escala_log_peso)`. A escala é gene, então o GA decide o
  quanto o peso manda.
- **alvo** (dá a nota): o SDF com o zero deslocado 3 voxels para fora e
  comprimido com log de escala 1. São 5.201 voxels positivos, a "caverna"
  que vale a pena acertar. Ele fica fixo durante toda a busca e é guardado
  somente leitura.

O alvo sai da ferramenta do SDF: `tools/sdf/npz/elaphes_surface_64_sdf_limiar-3_log1.npz`.

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

Depois de cada passo, o CA para antes das 50 iterações se:

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
repetida até o fim. No final, o campeão roda nas **seeds reservadas** 101 a 110
com o número de iterações já escolhido, sem escolher de novo. É a nota que
mede se ele generaliza para seeds que a busca nunca viu.

### Notas de referência

Junto com o campeão saem duas notas que não passam pelo CA nem pelos cortes,
para ler a nota do CA com contexto:

- **cópia pura**: o SDF base binarizado (positivo = vazio). No Elaphes dá
  0,10, porque o interno tem só 292 voxels;
- **teto trivial**: o SDF base binarizado no limiar do alvo (> −3). Dá
  exatamente 1, porque o alvo é o próprio SDF deslocado.

Ou seja, a nota mede **aderência ao campo**, não ganho gerativo. Chegar perto
de 1 pode ser só o CA aprendendo a deslocar o limiar do peso.

## Como usar

O alvo é gerado uma vez com a ferramenta do SDF. O peso é o SDF base, que a
mesma ferramenta grava sem argumentos.

```bash
uv run python -m tools.sdf.sdf                          # peso: SDF base
uv run python -m tools.sdf.sdf --limiar -3 --log 1      # alvo
```

Depois:

```bash
uv run python -m cavegen.optimization.genetic.executar                       # GA, orçamento 400
uv run python -m cavegen.optimization.genetic.executar --metodo aleatoria    # controle
uv run python -m cavegen.optimization.genetic.executar --orcamento 200 --seed 2
```

| opção | padrão | o que é |
|---|---|---|
| `--metodo` | `genetico` | `genetico` ou `aleatoria` |
| `--orcamento` | 400 | candidatos avaliados, contando repetidos |
| `--populacao` | 20 | cromossomos por geração (só no GA) |
| `--seed` | 0 | semente da **busca**, não do CA |
| `--peso` | SDF base do Elaphes | npz do `tools/sdf` usado como peso |
| `--alvo` | SDF com limiar −3 e log 1 | npz do `tools/sdf` usado como alvo |
| `--saida` | `results/` desta pasta | onde gravar o `ga_NNN.npz` |

Para comparar GA e busca aleatória com justiça, use o mesmo `--orcamento`.
No fim o terminal mostra o campeão, a nota nas seeds de ajuste e nas
reservadas e as notas de referência. O consumo de tempo e memória da busca
inteira vai para a planilha do `track_resources`, com o nome do `ga_NNN` no
rótulo para ligar a linha ao arquivo.

Com orçamento 200 a busca levou uns 40 s nesta máquina.

### O que fica no `ga_NNN.npz`

| campo | conteúdo |
|---|---|
| `genes_nomes`, `genes` | cromossomo de cada avaliação, na ordem em que foi feita |
| `notas`, `iteracoes`, `geracao` | nota, melhor iteração e geração de cada avaliação |
| `melhor_acumulado` | melhor nota vista até cada avaliação: a curva GA × aleatória |
| `reaproveitadas` | candidatos repetidos que vieram do cache |
| `detalhes` | JSON por avaliação: paradas, motivos, nota por seed, vazio e mudanças por passo |
| `campeao`, `notas_reservadas`, `nota_reservada_media` | o vencedor e como ele foi nas seeds reservadas |
| `nota_copia_pura`, `nota_teto_trivial` | as notas de referência |
| `config`, `genes_limites`, `cortes`, `faixa_vazio`, `sementes_*`, `peso`, `alvo`, `ambiente` | tudo o que é preciso para refazer a execução (inclui o commit) |

Os campos extras são strings JSON:

```python
import json
import numpy as np

with np.load("src/cavegen/optimization/genetic/results/ga_001.npz") as r:
    campeao = json.loads(str(r["campeao"]))
    curva = r["melhor_acumulado"]
print(campeao["genes"], campeao["iteracoes"], curva[-1])
```

### Usar em código

```python
from cavegen.optimization.genetic.algoritmo import ConfiguracaoGA, evoluir
from cavegen.optimization.genetic.aptidao import Alvo
from cavegen.optimization.genetic.ca import GENES_CA, AvaliadorCA

avaliador = AvaliadorCA(sdf_base, Alvo(campo_alvo), sementes=(1, 2, 3))
nota, detalhes = avaliador({"chance_inicial": 0.5, "sensibilidade": 12,
                            "escala_log_peso": 2.0})
resultado = evoluir(GENES_CA, avaliador, ConfiguracaoGA(orcamento=100), seed=0)
print(resultado.melhor.genes, resultado.melhor.nota)
```

## Primeiro resultado e o problema do decalque

Execuções com orçamento 200 e seed 0 (`ga_001` e `ga_002`):

| método | campeão | nota ajuste | nota reservada |
|---|---|---|---|
| GA | chance 0,30, sensibilidade 1, escala 7,25, 7 iterações | 0,982 | 0,982 |
| aleatória | chance 0,51, sensibilidade 1, escala 9,19, 6 iterações | 0,975 | 0,979 |

As duas buscas foram parar na sensibilidade 1 com escala alta. É o
**decalque**: com peso forte e sensibilidade mínima, o CA só pinta a região do
alvo, e seeds diferentes dão quase a mesma caverna (IoU entre as seeds de cerca
de 0,92 a 0,96). A nota fica perto do teto trivial sem o CA gerar nada. O log
não impede isso enquanto a escala for um gene livre, porque o GA aumenta a
escala. Um CA "de verdade" (chance 0,65, sensibilidade 14, escala 2) tira por
volta de 0,7, com IoU entre seeds de 0,51.

A correção ainda está em aberto. A proposta é multiplicar a nota pela
diversidade entre as seeds de ajuste: `nota × (1 − IoU médio entre as
cavernas)`. Com ela, o decalque cairia para cerca de 0,08 e o CA real ficaria
com cerca de 0,35. Ela ainda não está implementada.

## Testes

```bash
uv run python -m unittest tests/test_genetic.py tests/test_genetic_revisor.py -v
```

`test_genetic.py` cobre o motor, a nota, os cortes, o avaliador e o executor.
`test_genetic_revisor.py` tem os testes adversariais do revisor (gene inteiro
com limite fracionário, orçamento exato, cache, tudo cortado sem NaN,
seeds reservadas fora da busca, reprodutibilidade do campeão gravado).

## Mais contexto

- Decisões e justificativas: `docs/methodology-adjustments.md`, bloco "Ajuste
  genético do CA".
- Tarefas e critérios de aceite: `docs/tarefas-felipe-sdf-ca.md`.
- O SDF, o limiar e o log: [`tools/sdf/README.md`](../../../../tools/sdf/README.md).
