# inundacao — borda e interno por flood fill

Primeira etapa da pipeline do SDF (ver [README.md](README.md)). Separa os
voxels do Elaphes em borda e interno pela conectividade com o lado de fora da
grade, em vez de pela contagem de vizinhos. Entrada:
`entrada/elaphes_surface_64.npz` (o npz base do Elaphes).

O link abre no navegador (cole na barra de endereço). A figura carrega o Plotly
pela internet, então precisa estar online.

- [elaphes_surface_64_inundacao.html](file:///C:/Users/Felipe%20Cruz/Desktop/CESUPA/TCC/code/algorithms-for-procedural-generation-of-caves/sdf_temp/plots/elaphes_surface_64_inundacao.html)

## O problema que motivou

Duas abordagens foram testadas antes e descartadas (os scripts e as figuras
foram apagados; ficam aqui só os números, para comparação):

- **Classificação por vizinhos de face:** borda era todo voxel cheio com pelo
  menos uma face vazia. Como o Elaphes tem falhas internas, voxels no meio da
  caverna encostavam nesses vazios e saíam como borda, mesmo cercados de parede.
- **Preenchimento por CA** (von Neumann s=5 de 6 e Moore s=20 de 26, só acende
  zeros): tapava parte das falhas, mas julga só pela vizinhança local e não
  sabe se um vazio está dentro da caverna ou numa dobra da parede externa. O
  von Neumann chegou a acender 2 voxels por fora.

## Como funciona a inundação

A pergunta muda de "esse vazio tem muitos vizinhos cheios?" para **"existe um
caminho desse vazio até o lado de fora sem atravessar parede?"**.

1. A água começa **fora da grade**, por todos os lados.
2. A cada passo, todo vazio que encosta em água **por uma face** vira água.
3. A água nunca entra em voxel cheio.
4. Repete até um passo não mudar mais nada.

O vazio que a água não alcança é **buraco fechado**: está lacrado por parede.

Exemplo em 2D (`#` caverna, `.` vazio, `~` água), estado final:

```
~ ~ ~ ~ ~ ~ ~
~ # # # # # ~
~ # . . . # ~     os "." do meio nunca foram alcançados:
~ # . . . # ~     são o buraco fechado
~ # # # # # ~
~ ~ ~ ~ ~ ~ ~
```

Se a parede tiver uma fresta, a água entra e o buraco deixa de ser fechado.

### É um autômato celular

O `scipy.ndimage.binary_fill_holes` é uma chamada de `binary_dilation`. No
vocabulário do CA do projeto:

| parâmetro | inundação |
|---|---|
| vizinhança | von Neumann (6 faces) |
| sensibilidade | 1 (basta um vizinho ser água) |
| borda | `ONES` (fora da grade é água) |
| máscara | só vazio pode virar água; caverna nunca |
| iterações | até estabilizar |
| estado inicial | tudo seco |

No fim ele inverte o resultado: o que não virou água é caverna + buracos
fechados. No script: `buracos_fechados = binary_fill_holes(cheio) & ~cheio`.

A vizinhança de 6 é proposital: com 26 (Moore), a água passaria na diagonal por
frestas de canto, e paredes quase fechadas vazariam.

## Classificação

Script: `inundacao.py`. Depois de inundar, cada voxel da grade recebe:

| valor | significado | no plot |
|---|---|---|
| 0 | **vazio**: o que a água alcança, o lado de fora | não é plotado |
| 1 | **borda**: cheio que encosta na água por alguma face | Magma, meio da paleta, opacidade 0,5 |
| 2 | **interno**: tudo o que a água não alcança e não é borda | Magma, topo da paleta, opaco |

O interno junta duas coisas: os voxels cheios que não encostam na água e os
**buracos fechados** (vazios que a água não alcança). Para o que vem depois,
importa só a borda e o volume que ela envolve, então o vazio de dentro conta
como interno.

Fora da grade conta como água, então voxel cheio colado na borda do cubo é 1.
A borda fica translúcida para dar para ver o interno através dela.

## Resultados

Grade base: 1049 voxels cheios.

| | vizinhos de face | inundação |
|---|---|---|
| borda (1) | 853 | 783 |
| interno (2) | 196 | 292 |

- O interno da inundação são 266 voxels cheios + 26 de buraco fechado.
- Água: 261.069 voxels. Buracos fechados: 26 voxels em 6 componentes
  (tamanhos 17, 3, 3, 1, 1, 1).
- Os 26 voxels de buraco encostam em 86 voxels da caverna. É essa parede em
  volta que fazia o buraco parecer grande nos plots da classificação por
  vizinhos de face.
- 70 voxels que a classificação por vizinhos de face marcava como borda só
  encostavam em buraco fechado, nunca na água: a inundação os passa para
  interno.
- Coerência com o CA: tudo o que o Moore preencheu (15 com 2 iterações, 18 com
  4) estava dentro desses 26.

## Limitação: frestas

O método é tudo ou nada. Um caminho contínuo de vazios por face, do buraco até
o lado de fora, basta para a água entrar e o buraco inteiro virar externo.

O que **não** quebra:
- furo isolado no meio da parede;
- furos internos ligados entre si, sem saída para fora.

Ou seja, a exigência é que a **borda externa** esteja fechada; o meio pode ter
falhas.

Estimativa de quanto vazio está "quase fechado", tapando frestas pequenas com
*closing* morfológico (conectividade 6) antes de inundar:

| frestas tapadas antes | vazio interno |
|---|---|
| nenhuma (o que está no npz e na figura) | 26 |
| até 1 voxel | 48 |
| até 2 voxels | 64 |

É uma estimativa por cima: o *closing* também pode tapar dobras reais da parede
externa.

Formas de contornar sem consertar os dados na mão:
- *closing* antes de inundar, com fresta pequena;
- um CA de preenchimento antes de inundar, como o Moore testado antes (o CA
  conserta localmente, a inundação decide globalmente);
- grade de resolução menor, onde frestas finas somem sozinhas (perde detalhe).

## Relação com o SDF

Um SDF precisa do sinal: dentro ou fora. A inundação é uma forma clássica de
decidir esse sinal (o que a água alcança é fora). A distância vem depois, na
etapa `sdf.py`.

## Arquivos

| arquivo | conteúdo |
|---|---|
| `inundacao.py` | inundação, classificação e plot |
| `npz/elaphes_surface_64_inundacao.npz` | `classificacao` (0 vazio, 1 borda, 2 interno), `agua`, `buracos_fechados` (para saber quais 2 eram vazio), `metadata` |
| `plots/elaphes_surface_64_inundacao.html` | figura |

O script é independente dentro de `sdf_temp/`: do resto do projeto ele só
usa a caixa wireframe, o gizmo e a câmera do plot do CA
(`cavegen.generators.cellular_automata.plot`).

## Como regenerar

Da raiz do projeto:

```
uv run python sdf_temp/inundacao.py
```

## Referências

- Wikipedia, "Flood fill": explicação rápida, com animações das versões de 4 e
  8 vizinhos em 2D.
- Gonzalez & Woods, *Digital Image Processing*, capítulo de processamento
  morfológico, seção "Hole Filling": preenchimento de buracos como dilatação
  repetida com máscara, igual ao scipy.
- Soille, *Morphological Image Analysis: Principles and Applications*
  (Springer, 2003): base teórica, sob o nome de reconstrução morfológica.
- Documentação do `scipy.ndimage.binary_fill_holes`: conectividade padrão de
  faces.
