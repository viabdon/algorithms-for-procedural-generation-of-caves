# tools/sdf — SDF manipulável

Calcula o SDF de uma grade de superfície; sem argumento, a do Elaphes. O sinal
vem do flood fill, que é uma ferramenta à parte
([`tools/flood_fill`](../flood_fill/README.md)): o `sdf.py` chama a inundação
direto da grade e grava só o SDF e o plot dele. Depois, o SDF pode ser
manipulado (limiar e logaritmo, ver a etapa 3) para virar peso do CA ou
pontuação de um algoritmo genético, sempre com a manipulação gravada no npz.

```
data/processed/references/elaphes_surface_64.npz   grade 64³ (depth, height, width), 1 = superfície observada
  -> sdf.py [--limiar L] [--log E]
       1. tools/flood_fill: 0 vazio, 1 borda, 2 interno
       2. tira o 2, binariza a borda, mede a distância
       3. devolve o sinal: interno +, externo -               (SDF base)
       4. desloca o zero para d = L, depois comprime com o log (opcional)
       npz/elaphes_surface_64_sdf[_limiarL][_logE].npz
```

Os links `file:///` abrem no navegador (cole na barra de endereço). As figuras
carregam o Plotly pela internet, então precisa estar online.

## Pastas

| pasta | conteúdo | no git |
|---|---|---|
| `../../data/processed/references/` | npz base do Elaphes (entrada) | não (vem do PLY em `data/raw`) |
| `npz/` | o SDF | não (regenerado) |
| `plots/` | figura do SDF | não (regenerado) |
| `articles/` | artigos de base (EDT e FEED) | não (PDFs das editoras) |

## Etapas

### 0. Entrada

O npz de entrada já está sem o outlier: o voxel (13, 60, 31) do plot, o único
da grade sem nenhum dos 26 vizinhos cheios, foi zerado uma vez por um script
avulso. O script saiu do projeto por ser um caso específico e fica no
histórico do git (commit `d20feaf`, `sdf_temp/remover_outlier.py`).

### 1. Inundação (flood fill)

Separa borda e interno pela conectividade com o lado de fora da grade. Fica em
[`tools/flood_fill`](../flood_fill/README.md), com a metodologia, os
resultados, as limitações e a comparação com as abordagens descartadas.

### 2. SDF

`sdf.py` classifica a grade com a inundação e:

1. tira os voxels 2 (interno) e binariza: só a borda (1) fica 1;
2. mede a distância euclidiana de cada voxel até o voxel de borda mais
   próximo (`scipy.ndimage.distance_transform_edt`, exata);
3. volta com o sinal pela máscara do interno guardada no passo 1.

| região | sinal | no Elaphes 64³ |
|---|---|---|
| interno (era 2) | positivo | 292 voxels, até +2,00 |
| borda (era 1) | 0 | 783 voxels |
| externo (água) | negativo | 261.069 voxels, até −63,16 |

A distância está em voxels. Como a superfície é o próprio voxel de borda, o
zero cai no centro dele, sem correção de meio voxel. O interno é fino (a
parede da caverna voxelizada tem poucos voxels de espessura), por isso o
máximo positivo é só 2.

**De onde vem cada parte.** A distância sozinha é sempre positiva: ela diz
quão longe da borda o voxel está, não de que lado. O lado vem da inundação:
a água entra pela beirada da grade e o que ela alcança é externo; o que não é
parede e ela não alcança é interno. O interno fica positivo porque é a
caverna, o lugar onde quem usa o campo (o peso do CA, a nota do GA) quer
vazio, e positivo é o que soma. A borda fica 0 porque é a própria superfície,
a fronteira entre os dois lados. O externo fica negativo, e mais negativo
quanto mais longe da parede.

**O que o interno é no Elaphes.** O PLY observa a parede, não o ar. Como a
caverna tem entradas, o ar do túnel se liga ao lado de fora e a água o
alcança: ele fica externo. O interno é a espessura da parede voxelizada (e
buracos fechados), não o ar transitável; o `docs/architecture.md` registra
que esse campo não valida `VOID` real.

**Sinal:** interno positivo, combinado para este experimento. O
`docs/architecture.md` usa o inverso (`SDF < 0` no `VOID`); para mudar, troque
`SINAL_INTERNO` para `-1`. O npz guarda a convenção usada no campo
`convencao`.

O npz traz `sdf` (`float32`, o campo já manipulado, se houver manipulação),
`borda` e `interno` (máscaras `uint8`), `convencao`, `limiar` (0 no SDF base),
`escala_log` (só quando há log) e `metadata`.

**Plot:** paleta Tropic do plotly, do verde-azulado (mais negativo) ao rosa
(mais positivo), esticada de `CORTE_NEGATIVO = -10` até o máximo (+2 no SDF
base). O
branco do meio da paleta cai em −4, não no zero da borda: o externo de −1 a
−3 também sai rosado. A opacidade sobe em linha reta do corte (100%
transparente) até o valor mais positivo (opaco). Abaixo do corte o voxel nem
entra no plot: dos 262.144 voxels, ficam 28.321. Cada nível distinto do SDF
vira um trace (o plotly só aceita uma opacidade por trace); no Elaphes são 89
níveis.

- [elaphes_surface_64_sdf.html](file:///C:/Users/Felipe%20Cruz/Desktop/CESUPA/TCC/code/algorithms-for-procedural-generation-of-caves/tools/sdf/plots/elaphes_surface_64_sdf.html)

A EDT do scipy entra por enquanto. A implementação do artigo do Fuseiller
(`articles/`) pode substituir `distancia_ate_borda()`: qualquer EDT exata dá o
mesmo resultado, então o npz do scipy serve de referência para testar.

### 3. Manipulação (limiar e log)

O SDF base dá 0 na borda: quem escava ali não ganha nada, e todo voxel de fora
perde. Para o campo servir de pontuação com alguma tolerância, `manipular_sdf`
aplica duas transformações, **sempre nesta ordem**, sem recalcular a distância:

1. **Limiar** (`--limiar L`): o zero passa para `d = L`, ou seja,
   `campo = d − L`. Basta somar uma constante, porque a distância até a borda
   não muda; do lado de fora, o campo deslocado é exatamente a distância até a
   superfície empurrada `|L|` voxels para fora. Com `L = −4`:

   | voxel | SDF base | campo |
   |---|---|---|
   | interno (+2) | +2 | +6 |
   | borda | 0 | +4 |
   | fora, a 4 voxels | −4 | 0 (neutro) |
   | fora, a 10 voxels | −10 | −6 |

2. **Log** (`--log E`): `comprimir_log`, `E · sinal(x) · ln(1 + |x|)`.
   O SDF cru vai até −63,16 no Elaphes; sem compressão, o voxel mais
   distante pesaria 63 vezes o voxel colado na parede. O log cresce rápido
   perto de zero e devagar depois, então a distância grande pesa só um pouco
   mais que a pequena (com `E = 1`, 4,16 contra 0,69: 6 vezes). O `ln(x)`
   sozinho não serve: **não existe para x negativo** (o externo inteiro), por
   isso a conta usa `|x|` e devolve o sinal no fim; e **vai a menos infinito
   em x = 0** (a borda), por isso o `1 +`, que leva a borda a `ln(1) = 0`. A
   tabela com os valores reais do Elaphes (escala 1, sem limiar) está no
   [README do GA](../../src/cavegen/optimization/genetic/README.md#2-o-log-por-que-sinald--ln1--d).

As duas transformações ficam em `src/cavegen/sdf/manipulacao.py`, porque são
do SDF e o CA (peso) e o GA (peso e alvo) também as usam; o pacote não
importa de `tools/`, então este script importa de lá.

**A ordem importa: primeiro o limiar, depois o log.** O log leva 0 em 0, então
o zero que o limiar pôs em `d = L` continua lá depois do log. Na ordem
inversa (log primeiro, depois somar `|L|`), o zero iria para onde o log vale
`L`, ou seja, `ln(1 + |d|) = |L|`, `|d| = e^|L| − 1`. Com o `L = −3` que o GA
usou até 22/11/2026, o zero sairia de `d = −3` para `d ≈ −19,09`, 16 voxels
mais longe da parede: a borda valeria +3 em vez de +1,39, e a região
positiva do Elaphes teria 72.027 voxels em vez de 5.201. Por isso
`manipular_sdf` fixa a ordem.

As duas transformações só crescem, então a ordem dos voxels não muda: o corte
do plot passa pela mesma conta (`corte_do_campo`) e mostra os mesmos voxels,
os que estão a até 10 voxels da borda. O hover chama de borda o valor que a
borda tem no campo (+4 com `L = −4`).

No Elaphes 64³ (`L = −4`): a região com nota positiva passa de 292 voxels
(só o interno) para 7.891, e 401 voxels ficam exatamente neutros. Com
`L = −4` e log × 2, o campo vai de −8,19 a +3,89, com a borda em +3,22.

**Para o algoritmo genético, atenção ao alvo:** desde 22/11/2026 o GA do CA
usa, em cada caverna, **um campo só, sem limiar**: o SDF com log de escala 1
(`--log 1`), que é o peso do CA e o alvo da nota ao mesmo tempo. No Elaphes
são 292 voxels positivos, só a espessura da parede (o ar do túnel é alcançado
pela água e fica negativo), e o `docs/architecture.md` registra que esse campo
não valida `VOID` real. A nota mede aderência a esse campo, não ao vazio real.
De 12/11 a 22/11/2026 o alvo foi o SDF com `L = −3` e log (5.201 positivos, a
casca mais a faixa de até 3 voxels em volta); o limiar continua disponível na
ferramenta, mas o GA não o usa mais. Ver `docs/methodology-adjustments.md`.

## Como regenerar

A entrada vem da voxelização do PLY (que fica em `data/`, fora do git), da
raiz do projeto:

```
uv run python -m cavegen.datastream.run_reference_voxelization --ply data/raw/elaphes/elaphes_cave.ply --output data/processed/references/elaphes_surface_64.npz --shape 64 64 64
```

A voxelização devolve o outlier: zere o índice (60, 31, 13) da grade
`surface_voxels` (o (13, 60, 31) do plot) antes de seguir.

Depois, o SDF (a inundação roda dentro dele):

```
uv run python -m tools.sdf.sdf [superficie.npz]                       # SDF base
uv run python -m tools.sdf.sdf [superficie.npz] --log 1               # o campo do GA (peso e alvo)
uv run python -m tools.sdf.sdf [superficie.npz] --limiar -4            # zero a 4 voxels para fora
uv run python -m tools.sdf.sdf [superficie.npz] --limiar -4 --log 2    # e depois o log × 2
```

O campo do GA de outra caverna sai da grade de superfície dela, por exemplo
`uv run python -m tools.sdf.sdf indian_tunnel_temp/npz/indian_tunnel_surface_64.npz --log 1`,
que grava `npz/indian_tunnel_surface_64_sdf_log1.npz` (265 voxels positivos).

Cada combinação grava um npz e um plot com o nome dela, e o SDF base continua
com o mesmo nome de antes (`elaphes_surface_64_sdf.npz`), que é o peso padrão
do CA. Um campo manipulado entra no CA como qualquer SDF:
`uv run python -m cavegen.generators.cellular_automata.pesos tools/sdf/npz/<campo>.npz`
(sem passar outra escala de log, para não comprimir duas vezes).

O plot da inundação sozinha sai com `uv run python -m tools.flood_fill.inundacao`.
