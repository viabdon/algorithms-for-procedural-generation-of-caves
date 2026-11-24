# cavegen/tools — ferramentas auxiliares

Códigos que servem de apoio a outros códigos do projeto, sem ser um dos
algoritmos comparados no TCC. Hoje preparam entradas para o Cellular Automata
(o peso guiado por SDF), mas podem ser usados por qualquer outro gerador ou
experimento.

Até 22/11/2026 elas ficavam em `tools/`, na raiz, fora do pacote, e o pacote
não podia importá-las: o `pyproject.toml` só empacota `src/`, então `tools/`
só era importável rodando da raiz. Agora moram em `src/cavegen/tools/`, e o CA
e o GA podem usar o SDF daqui de qualquer pasta (a etapa 2 do GA chama
`cavegen.tools.sdf.sdf.gravar_campo`). Continuam não sendo algoritmos
comparados.

| pasta | o que faz | quem usa |
|---|---|---|
| [`flood_fill/`](flood_fill/README.md) | inundação: separa borda, interno e buracos fechados de uma grade, com plot | `sdf/`, `indian_tunnel_temp/` |
| [`sdf/`](sdf/README.md) | SDF de uma grade de superfície, com o sinal vindo do `flood_fill/`, manipulável (limiar e log) e com plot | `random_walk_points/`, `indian_tunnel_temp/`, o peso padrão do CA |
| [`random_walk_points/`](random_walk_points/README.md) | Random Walk com pontos sorteados, cuja rede vira peso do CA | o CA, pelos pesos |

## Reutilização no projeto

Antes de implementar uma operação, procure sua implementação em `cavegen.tools`.
Os geradores, a datastream e os experimentos importam dali o cálculo compartilhado.
Quando outro fluxo precisar de uma operação existente, extraia a parte comum para
`tools` e preserve as convenções e interfaces específicas de cada consumidor.

`plot_volumes.py` fornece as funções Plotly compartilhadas e gera HTML a partir de volumes do
benchmark com `python -m cavegen.tools.plot_volumes caminho/do/volume.npz`.

## Como rodar

Como módulo do pacote (`-m`):

```bash
uv run python -m cavegen.tools.flood_fill.inundacao
uv run python -m cavegen.tools.sdf.sdf
uv run python -m cavegen.tools.random_walk_points.menu
```

Os testes ficam em `tests/` (por exemplo `tests/test_random_walk_points.py`) e
rodam com a suíte completa.

## Dados

Cada ferramenta grava suas saídas dentro da própria pasta (`npz/`, `plots/`,
`results/`...), como o CA faz com as dele. Entrada que mais de uma ferramenta usa, como a grade de
superfície do Elaphes, fica em `data/processed/references/`. Nada disso vai
para o Git: ver o `.gitignore`.
