# Random Walk com pontos sorteados (experimento)

Experimento de um Random Walk que monta a caverna sem pontos marcados à mão. É uma ferramenta auxiliar do CA (gera redes que viram peso) e não entra na comparação do TCC: nada em `src/` depende dela, só os testes em `tests/test_random_walk_points.py`. Ela reaproveita só a caminhada (`caminhar`) e a voxelização (`voxelizar`) do RW do pacote e o SDF de `cavegen/tools/sdf/`.

## Motivação

No Random Walk do projeto base, alguém marca os pontos que a caminhada deve seguir. Este experimento investiga como gerar também esses pontos de forma procedural.

A ideia aqui é tornar esses pontos automáticos: eles são sorteados e se organizam sozinhos em veios, sem nenhuma marcação manual.

## A ideia

### Caminhos independentes

1. Gerar aleatoriamente uma pequena quantidade de pontos, em lugares aleatórios.
2. Dividir os pontos em 50% sources e 50% targets.
3. Cada source vai até o target mais próximo com o Random Walk.
4. Duas ou mais sources podem se conectar ao mesmo target, e isso é aceitável.
5. Assim que um target é conectado, tanto a source quanto o target viram nós. Os targets desconectados de tudo são excluídos.

Até aqui, o esperado é ter vários caminhos independentes.

### Veio central

6. Depois que tudo é nó conectado, o processo vem de cima até encontrar o nó de y mais alto e desce até o nó mais baixo conectado a ele. A partir desse nó, ele só olha para os nós que estão abaixo.
7. Dos nós abaixo, escolhe o de menor nota, que junta o ângulo de desvio e a distância até o nó. O ângulo sai de um triângulo retângulo traçado do nó atual até o nó avaliado, medido no nó atual (0° é reto para baixo, 90° é na horizontal). A nota é

   `nota = p · ângulo / 90° + (1 − p) · distância / maior distância entre os candidatos`

   As duas partes vão de 0 a 1, e o peso `p` (`peso_angulo`, padrão 0,5) decide quanto cada uma conta. Só pelo ângulo (`p = 1`, a regra da primeira versão), um nó reto embaixo e lá no fundo sempre ganha, e o veio desce quase em linha reta. Com a distância, um nó um pouco mais torto e mais perto pode ganhar, e o veio faz mais curvas. Com `p = 0`, vence só o mais perto.
8. A conta não precisa ser feita para todos os nós. De cada veio, entra só o nó mais alto que não esteja acima do nó atual. Isso evita escolher um nó que jogue o caminho de volta para cima nos passos seguintes.
9. Depois de achar o nó, aplica o Random Walk até ele, como se fosse um par source e target.
10. O processo se repete até não haver mais nós nos níveis mais baixos.

Até aqui, o esperado é ter alguns fragmentos pelo caminho, com uma linha completa no meio. Essa linha é o **veio central**, que é tratado de forma diferente dos outros caminhos.

### Ligação dos fragmentos

11. Descendo novamente a partir do topo, o processo encontra os caminhos soltos. De cada um, pega o nó mais próximo de um nó do veio central e aplica o Random Walk para conectá-lo a esse nó.

### Progressão no plot

O plot mostra, na mesma figura, a progressão dos veios:

1. Os pontos divididos em source e target.
2. Os pontos conectados.
3. O veio central.
4. Tudo conectado.

## Como rodar

```bash
uv run python -m cavegen.tools.random_walk_points.menu                # gerar e plotar
uv run python -m cavegen.tools.random_walk_points.plot 1 progressao   # plotar direto um resultado
uv run python -m cavegen.tools.random_walk_points.peso 1 2            # peso do CA a partir do resultado 1, com log x2
uv run python -m unittest tests/test_random_walk_points.py -v # conferir as regras
```

Os resultados vão para `results/`, os SDF para `npz/` e as figuras para `plots/`, todos fora do Git. O `peso.py` grava o peso na pasta de pesos do CA.

| Arquivo | O que faz |
|---|---|
| `generator.py` | As etapas da ideia (`gerar_rede`) e a escavação na grade |
| `results.py` | Grava e lê `result_000.npz` |
| `plot.py` | A figura da progressão, com controle deslizante, e a grade escavada |
| `menu.py` | Menu de terminal, como o do CA |
| `peso.py` | Transforma um resultado em peso do CA, para testes |
| `tests/test_random_walk_points.py` | Testes das regras, na suíte do projeto |

## Decisões de implementação

Pontos em que a ideia deixava margem, resolvidos no código. Todos podem ser trocados em `generator.py`.

- **A descida dentro de um veio nunca sobe.** Se o nó de entrada só alcança o resto do veio passando por um target acima dele, o veio central para ali e escolhe o próximo nó pela nota da etapa 7.
- **A distância da nota é euclidiana em 3D e é dividida pela do candidato mais longe.** Assim ela fica entre 0 e 1 como a parte do ângulo e não depende do tamanho da grade. No empate vence o nó de menor índice, como na regra antiga.
- **Resultado gravado antes da nota é lido com `peso_angulo = 1`.** É a regra com que ele foi gerado: com `p = 1`, os resultados 1 a 3 saem idênticos ao que estava gravado.
- **O veio central pode pegar outro nó de um veio já visitado.** Por isso, ele sempre termina no nó mais baixo de todos.
- **Caminho solto é o veio sem nenhuma ligação até o veio central.** Um veio em que o central passou só por parte dos nós já conta como ligado.
- **As contas são por nó, não por voxel.** Duas caminhadas que se cruzam no espaço continuam sendo veios separados até a etapa 11.
- **A caverna é encaixada na grade no final**, como no RW do pacote. Assim, uma caminhada que sai um pouco da caixa não é cortada na parede.
- **Sem `track_resources` na geração.** A planilha de recursos é a da comparação do TCC, e este experimento não entra nela.

## O que os testes mostraram até agora

**O veio central fica curto.** Só pelo ângulo (`p = 1`), mais pontos quase não aumentam o número de nós dele. A causa provável é a regra do ângulo: nós bem mais abaixo tendem a ter ângulo menor, e cada descida nova cai cerca de 20 voxels numa grade de 64. Foi isso que levou à nota com a distância. Média de 30 seeds (0 a 29), demais parâmetros no padrão:

| Pontos | Nós no veio central (`p = 1`) | (`p = 0,5`) | Descidas novas (`p = 1`) | (`p = 0,5`) | Nós fora dele (`p = 1`) | (`p = 0,5`) |
|---|---|---|---|---|---|---|
| 16 | 5,0 | 5,5 | 1,5 | 1,8 | 7,7 | 7,2 |
| 24 | 5,1 | 6,2 | 1,5 | 2,1 | 14,1 | 13,0 |
| 48 | 6,4 | 7,9 | 2,5 | 3,2 | 31,8 | 30,3 |
| 96 | 6,7 | 8,4 | 2,7 | 3,7 | 70,3 | 68,6 |

Com `p = 0,5`, o veio central ganha de 10% a 25% de nós e faz mais paradas no caminho. Ainda falta ver se isso muda a forma da caverna e o CA guiado por ela.

**O CA guiado por essa rede se parte.** Medido com a regra antiga (`p = 1`). O resultado 1 (seed 1, 24 pontos) virou o `peso_005` do CA. Com seed 8 do CA, s = 12, borda zeros, 4 iterações e log × 2, o CA saiu com 6806 vazios em 5 pedaços (dois grandes e três de até 6 voxels). O corte principal fica numa descida do veio central. Em outras 10 seeds sorteadas com o mesmo peso, a média foi de 4,6 pedaços, contra 1,7 do peso do Elaphes com o mesmo log.
