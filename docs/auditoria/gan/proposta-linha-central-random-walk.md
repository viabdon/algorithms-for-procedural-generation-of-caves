# Proposta: linha central percorrida por random walk

**Estado: proposta de 27/11/2026 (Felipe), ainda não implementada.**
Este documento registra a primeira etapa da ideia. As etapas de
correção seguintes e a organização da função ainda serão decididas.
A implementação deve ficar separada do código atual para que as duas
linhas centrais possam ser comparadas no mesmo lote de junções.

## O problema nas bifurcações

As linhas centrais usadas nos recortes vêm de contração laplaciana:
os grafos fornecidos pelo catálogo (arquivos `*_from_LBC`) e o grafo
estimado por [`tools/centreline.py`](../../../src/cavegen/tools/centreline.py).
A contração encolhe a nuvem de pontos e o que sobra vira o eixo. O
termo laplaciano puxa cada ponto para a média dos vizinhos e se comporta
como um encurtamento da curva: ele não procura o meio da galeria.

Num tubo simples, o resultado cai perto do eixo. Numa bifurcação, o
caminho mais curto que liga os três ramos corta a quina. Num Y
invertido, as duas pernas são puxadas uma para a outra e o nó de
junção sobe ou escorrega para o lado da ramificação. O trecho perto do
nó atravessa a rocha. A região da junção também tem mais pontos, e o
lado com mais massa puxa mais a média. Depois da contração, a árvore
geradora mínima liga os nós só por distância, sem verificar se a
aresta cruza a parede.

```text
   esperado            contração

      |                    |
      |                    |
      +                    |
     / \                   +      <- nó deslocado
    /   \                 /|\
   /     \               / | \    <- eixo cruza a rocha entre as pernas
```

Isso já apareceu nos ensaios do
[histórico](historico-voxelizacao.md#eixos-desviados-e-ramos-curtos):
na junção 003 de Cascade de Môtiers, os dois cortes candidatos do ramo 19
tiveram 23 voxels de parede observada no percurso do eixo. O
[recentramento por âncoras](../../planejamento-recortes-voxelizacao.md#recentramento-local-por-âncoras)
só ajusta o trecho de um ramo entre dois pontos fixos e não move o nó
de junção. Na reexecução de 27/11/2026, nenhum dos 183 ramos incidentes
teve o eixo ajustado; em 56 faltaram duas âncoras válidas.

## A ideia

Usar o grafo atual como mapa e não como eixo final. Dele se aproveitam
a topologia, as extremidades e os nós de ramificação. O eixo é refeito
por um caminhante que anda dentro da nuvem de pontos, como no Random
Walk ponderado já usado no projeto ([random-walk.md](../../random-walk.md)).

O caminhante tenta sempre percorrer o maior caminho possível da caverna,
de uma ponta à outra, sem entrar nas ramificações. As ramificações
recebem um tratamento separado depois.

## Etapa 1: o caminhante

O caminhante começa no ponto 0, numa extremidade do grafo, e avança em
passos curtos. A cada passo ele avalia as direções possíveis com cinco
pesos:

| Peso | Função |
| --- | --- |
| Guia da linha central | Favorece a direção que segue o grafo atual, para o caminhante não se perder na nuvem. |
| Inércia | Mantém uma angulação próxima da direção anterior, para ele seguir a galeria sem zigue-zague. |
| Penalidade de ré | Dá um peso alto para voltar no sentido oposto, para ele não refazer o caminho. |
| Medo das bordas | Afasta o caminhante das direções em que a parede está perto. |
| Desvio da ramificação | Perto de um nó de ramificação, afasta o caminhante da direção da saída lateral. É menor que o medo das bordas. |

### Como o caminhante enxerga as bordas

Em volta da posição atual há um kernel, uma vizinhança fixa dividida em
setores (cima, baixo, esquerda, direita, frente). Em cada passo o
caminhante conta quantos pontos da nuvem caem em cada setor. O que conta
é a quantidade de pontos, não a distância até eles.

A nuvem é um levantamento da superfície. O interior da galeria tem
poucos pontos, que vêm de erros de medição, e a parede tem muitos. Se o
caminhante está quase batendo na parede direita, o setor da direita fica
cheio. Se ele está encostando no teto, o setor de cima fica cheio.

Quando a contagem de um setor passa de um limiar, a direção desse setor
perde peso e a direção oposta ganha. A correção é limitada pela inércia,
para que o desvio não vire meia-volta. Quando o kernel está equilibrado,
o caminhante está longe o suficiente das bordas e segue a guia.

O mesmo mecanismo protege contra lacunas da nuvem. Uma falha no
levantamento é sempre menor que a seção interna da galeria, então mesmo
perto dela o kernel encontra os pontos da parede em volta. O setor da
falha continua com mais pontos que o lado interno, e o caminhante tende
a voltar para o meio da caverna.

O resultado da etapa é a sequência de posições do caminhante, que vira
o novo eixo da rota principal.

### Ramificações na primeira passada

Ao chegar numa ramificação, o caminhante encontra um espaço muito aberto
e o kernel fica com pouca informação. Numa saída lateral pequena de uma
galeria maior, o espaço extra fica do lado da ramificação. É por isso que
a contração puxa o eixo para lá, e o caminhante seria puxado da mesma
forma.

O grafo atual já indica onde estão os nós de ramificação e para que lado
sai cada ramo. Perto de um desses nós, a direção da saída lateral recebe
o peso de desvio da ramificação. O caminhante não precisa ir para o lado
oposto; ele só evita a direção do ramo e continua a linha principal. Esse
peso é menor que o medo das bordas, para que uma parede próxima continue
mandando no passo.

```text
          |  rota principal
          |
          +-----  ramificação: direção penalizada
          |
          |  o caminhante continua por aqui
```

### Checkpoints e segunda passada

Cada nó de ramificação que o caminhante atravessa vira um checkpoint.
O checkpoint guarda a posição em que ele passou pela junção e as direções
dos ramos que ficaram para trás, tiradas do grafo atual.

A primeira passada percorre toda a rota principal, de uma ponta à outra.
Depois o caminhante volta a cada checkpoint e percorre os ramos que ainda
não foram visitados. Nessa segunda passada, os pesos se invertem:

- a direção do ramo, como o grafo atual o encontrou, passa a ser a guia;
- os trechos já percorridos são penalizados, para que ele não refaça a
  rota principal nem outro ramo.

Um ramo que tenha suas próprias ramificações gera novos checkpoints, e o
processo se repete até não sobrar ramo do grafo sem percurso. O ponto do
checkpoint na rota principal é o candidato natural para o novo nó de
junção.

## Etapas 2 e 3

As próximas etapas corrigem os erros que o caminhante deixar. Ainda
serão definidas, depois de ver a etapa 1 em casos reais.

## Pontos em aberto

- **Ponto 0 e maior caminho**: qual extremidade é o ponto de partida e
  como escolher a rota principal. Uma opção é o caminho mais longo entre
  duas folhas da árvore.
- **Aleatório ou determinístico**: se o passo for sorteado, usar
  `numpy_rng(seed)` e registrar a semente, como no resto do projeto.
- **Tamanho do kernel e do passo**: as galerias têm calibres diferentes.
  Um raio fixo pode ser grande demais nas passagens estreitas. O passo
  precisa ser comparável ao voxel de 16 cm usado nos recortes.
- **Limiar de borda**: separar os pontos de ruído do interior da parede
  real. A densidade varia entre levantamentos (LAS de 5 cm, Indian
  Tunnel Full 1x e 10x).
- **Lacunas na nuvem**: o argumento de que a falha é menor que a seção
  vale para as lacunas comuns. Vale conferir nos casos reais as entradas
  abertas e as oclusões grandes do Indian Tunnel, onde a falha pode
  chegar perto do calibre da galeria.
- **Alcance do desvio da ramificação**: a que distância do nó o peso
  começa a agir e como medir a direção do ramo no grafo (tangente no nó
  ou média dos primeiros metros, já que o próprio grafo está deslocado
  perto da junção).
- **Rota principal versus ramo**: numa junção em Y simétrico, os dois
  ramos têm calibre parecido e a escolha da rota principal decide qual
  deles é penalizado.
- **Critério de parada**: chegar à extremidade final, ficar preso entre
  paredes ou se afastar demais do grafo.

## Como avaliar

A nova função deve ter o mesmo contrato de `estimate_centreline`: nós
XYZ, arestas por índice e proveniência, com um nome de método próprio.
Assim o planejador de recortes e o `junction_fallback` aceitam as duas
linhas centrais sem mudança.

1. **Caso sintético** em `tests/`: um Y invertido voxelizado em que a
   linha central atual cruza a parede. O novo eixo não pode cruzar.
2. **Lote real**: o inventário
   `data/processed/experiments/juncoes_auto/inventario_16cm.json`,
   rodado pelo `junction_fallback` com o eixo atual e com o novo.

A linha de base é a reexecução de 27/11/2026:

| Indicador | Eixo atual com recentramento |
| --- | ---: |
| Avaliações de junção | 62 |
| Ramo sem tampa válida | 52 |
| Combinações sem fechamento | 9 |
| Volumes reproduzidos | 1 (junção 023) |
| Ramos incidentes examinados | 183 |
| Ramos sem cruzamento de parede na janela | 123 |
| Ramos sem duas âncoras válidas | 56 |

Além dessas contagens, medir os voxels de parede cruzados pelo eixo, a
menor folga até a parede ao longo do eixo e o deslocamento dos nós de
junção. A junção 023 é o controle e precisa continuar fechando.
