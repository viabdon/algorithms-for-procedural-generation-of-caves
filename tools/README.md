# tools — ferramentas auxiliares

Códigos que servem de apoio a outros códigos do projeto, sem ser um dos
algoritmos comparados no TCC. Hoje preparam entradas para o Cellular Automata
(o peso guiado por SDF), mas podem ser usados por qualquer outro gerador ou
experimento.

Ficam fora do pacote `cavegen` (`src/`) de propósito: nada em `src/` importa
daqui. Quem usa são os experimentos, os testes e quem roda os scripts.

| pasta | o que faz | quem usa |
|---|---|---|
| [`sdf/`](sdf/README.md) | inundação (flood fill) e SDF de uma grade voxelizada, com plot | `random_walk_points/`, `indian_tunnel_temp/`, o peso padrão do CA |
| [`random_walk_points/`](random_walk_points/README.md) | Random Walk com pontos sorteados, cuja rede vira peso do CA | o CA, pelos pesos |

## Como rodar

Sempre da raiz do projeto e como módulo (`-m`), para os imports `tools.…`
funcionarem:

```bash
uv run python -m tools.sdf.inundacao
uv run python -m tools.sdf.sdf
uv run python -m tools.random_walk_points.menu
```

Os testes ficam em `tests/` (por exemplo `tests/test_random_walk_points.py`) e
rodam com a suíte completa.

## Dados

Cada ferramenta grava suas entradas e saídas dentro da própria pasta (`npz/`,
`plots/`, `results/`...). Essas pastas não vão para o Git: ver o `.gitignore`.
