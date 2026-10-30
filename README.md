# CaveGen TCC — Algoritmos de Geração Procedural de Cavernas 3D

Repositório do Trabalho de Conclusão de Curso **"Algoritmos de Geração Procedural de Cavernas: Uma Comparação Holística"**.

O objetivo do projeto é comparar algoritmos clássicos e baseados em aprendizado de máquina para geração procedural de cavernas tridimensionais. A avaliação atual prioriza custo computacional, estrutura, controle e diversidade dos volumes gerados. A IoU volumétrica contra o scan do Elaphes saiu do escopo atual porque ainda não há uma referência validada de seu espaço interno.

## Estratégia atual

A arquitetura prioriza um pipeline científico **offline-first**:

1. Python gera volumes 3D booleanos em ZYX, persiste NPZ e calcula métricas e CSV.
2. Random Walk e Cellular Automata básico formam o benchmark inicial, com
   domínio, resolução, sementes e orçamento documentados.
3. Malhas extraídas dos volumes gerados por Marching Cubes permitem inspeção
   na Unity; gRPC é posterior.
4. GAN e PCGRL são frentes futuras; a branch `CA` contém um protótipo de CA
   com peso espacial. O ajuste genético de parâmetros de CA e Random Walk
   está planejado; seus espaços de busca e orçamento ainda serão definidos.
5. O Elaphes permanece referência de superfície para inspeção qualitativa,
   sem IoU volumétrica ou SDF real no benchmark atual.

Essa decisão reduz risco operacional e mantém o foco principal na comparação quantitativa dos algoritmos.

## Algoritmos previstos

- Random Walk 3D
- Cellular Automata 3D básico; uma variante guiada por campo procedural
  poderá ser estudada depois
- Ajuste genético dos parâmetros de CA e Random Walk
- GAN 3D, após auditar a semântica e a independência dos volumes de treino
- PCGRL 3D, após definir e validar um ambiente pequeno e a recompensa

## Convenção de volume

Neste repositório, um volume 3D é representado por um `numpy.ndarray` booleano de forma `(depth, height, width)`.

- `True`: voxel aberto, isto é, espaço de caverna/túnel.
- `False`: voxel fechado/sólido.

Essa convenção descreve os **volumes gerados**. Na grade diagnóstica de
superfície do Elaphes, `True` significa parede observada. Não existe uma
conversão validada dessa grade para o ar interno real.

Para o SDF de um volume gerado com vazio conhecido, o contrato adotado é
`float32[D,H,W]` em ZYX: **positivo no interior do vazio**, **negativo no
exterior sólido** e **zero na borda**, com distância euclidiana em **voxels**
até o voxel de borda mais próximo. O protótipo `random_walk_temp/` na branch
`CA` já usa essa convenção. A regra de borda e a origem do campo devem ser
registradas; o SDF ainda não é uma API integrada ao pacote principal.

## Estrutura

```text
cavegen-tcc/
├── configs/              # Configurações de algoritmos, experimentos e hardware
├── data/                 # Dados externos, brutos, processados e referências
├── docs/                 # Arquitetura, roadmap e decisões metodológicas
├── models/               # Checkpoints de modelos treinados
├── notebooks/colab/      # Notebooks de treino e prototipação no Colab
├── proto/                # Arquivos .proto para a fase gRPC
├── results/              # CSVs, figuras, meshes e relatórios de profiling
├── src/cavegen/          # Pacote Python principal
└── unity/                # Visualizador Unity e futura integração gRPC
```

## Instalação local mínima com uv

O projeto usa `pyproject.toml` como fonte principal das dependências. O `uv` cria o ambiente virtual, instala o pacote em modo editável e sincroniza as dependências declaradas no projeto.

```bash
uv sync
```

Para instalar também as dependências de aprendizado de máquina e profiling:

```bash
uv sync --extra ml --extra profiling
```

No Google Colab, quando estiver trabalhando a partir de uma cópia do repositório:

```bash
pip install uv
uv pip install -e . --system
```

Os arquivos em `requirements/` ficam apenas como fallback/compatibilidade para ambientes em que `uv` não estiver disponível.

## Validação para contribuições e forks

Depois de sincronizar as dependências, execute a suíte unitária completa antes
de abrir um PR, criar um commit importante ou integrar mudanças de outra
branch:

```bash
uv run python -m unittest discover -s tests -v
```

Para investigar apenas um módulo, substitua o caminho pelo arquivo desejado:

```bash
uv run python -m unittest tests/test_normalization.py -v
```

Os comandos abaixo são verificações leves que não exigem os datasets externos:

```bash
# Confere se a interface de linha de comando pode ser importada.
uv run python -m cavegen.datastream.run_reference_voxelization --help

# Detecta espaços em branco e outros problemas de patch no Git.
git diff --check
```

## Primeiro teste

Gere volumes de Random Walk e Cellular Automata em pequena escala:

```bash
uv run python -m cavegen.benchmark.run_generation_benchmark \
  --config configs/experiments/baseline_32.yaml \
  --out results/csv/baseline_32.csv
```

Os volumes gerados serão salvos em `results/volumes/` e a tabela de tempos em `results/csv/`.

## Voxelização direta de superfície para diagnóstico

Para inspecionar uma nuvem de pontos PLY como grade de voxels de superfície,
execute uma primeira passagem em baixa resolução. O leitor processa o arquivo
em lotes, portanto não carrega toda a nuvem na memória:

```bash
uv run python -m cavegen.datastream.run_reference_voxelization \
  --ply /caminho/para/elaphes_cave.ply \
  --bounds data/params/elaphes_xyz_bounds.json \
  --shape 32 32 32 \
  --batch-size 65536 \
  --progress-every 1000000 \
  --output data/processed/references/elaphes_surface_32.npz \
  --report-slices
```

O comando usa os limites XYZ previamente calculados, normaliza os pontos para
índices ZYX, mostra o progresso a cada milhão de vértices e salva a grade como
um `.npz` comprimido. O arquivo preserva os limites XYZ, a resolução, o caminho
da fonte e a convenção de normalização. Nessa grade, `True` significa superfície
observada, e não espaço aberto de caverna. Ela serve ao diagnóstico do scan e
não fornece a classificação volumétrica necessária para IoU.

Execução registrada para o Elaphes em `32³`: 245 de 32.768 voxels (0,75%) foram
marcados como superfície. O arquivo `elaphes_surface_32.npz` é um artefato local
de dados processados e não faz parte do Git.

## Limite da referência real

Os experimentos com amostragem, Screened Poisson, linha central, orientação
de normais e espessamento não produziram uma malha com interior validado para
o Elaphes. Mesmo as malhas sem arestas de borda no teste de dilatação tiveram
auto-interseções. A grade de parede observada não pode ser invertida para
obter o vazio: seu complemento reúne interior, exterior e regiões não
observadas. Assim, SDF real e IoU volumétrica contra o scan não fazem parte
do benchmark atual. Os experimentos estão preservados na branch
`experiment/elaphes-meshing` e em artefatos locais; o
[resumo quinzenal](docs/relatorios/resumo-quinzenal-tcc-2026-10-18.docx)
registra os resultados e limites.

Na branch `CA` (`a58155e`), o CA já aceita um peso espacial somado à
contagem de vizinhos. Há testes de equivalência entre ausência de peso e
peso zero. A branch também contém flood fill e EDT experimentais da grade
de **parede** do Elaphes, além de uma caminhada ponderada por waypoints
voxelizada em `random_walk_temp/`. O campo do Elaphes usa o mesmo sinal e
unidade, mas seu "interno" pode representar parede ou buracos fechados;
não fornece `VOID` real validado.
O guia por waypoints vem de modelos de cavernas reais e também não é um
controle totalmente independente de referências. Um guia procedural com
semântica, escala e sinal definidos continua pendente. O benchmark da branch
ainda precisa de integração: ele importa `generate_cellular_automata`, nome
ausente no pacote reorganizado. O ajuste genético de CA e Random Walk está
planejado, com custo de busca separado do tempo de geração.

## Exportação de volumes gerados para malha

```bash
uv run python -m cavegen.meshing.export_mesh \
  --input results/volumes/random_walk_seed_0.npz \
  --output results/meshes/random_walk_seed_0.obj
```

## Roadmap resumido

1. Usar `64³` em ZYX nas medições finais; fechar sementes, repetições e
   ambiente de execução, e reexecutar Random Walk e CA básico.
2. Fechar avaliação estrutural com ocupação, conectividade e componentes;
   documentar a unidade da transformada de distância.
3. Auditar dados para GAN e definir o MDP de um PCGRL pequeno; separar treino
   e geração quando houver modelos funcionais.
4. Definir e executar o ajuste genético de parâmetros dos dois clássicos;
   considerar CA com guia procedural como extensão.
5. Consolidar resultados em Python e inspecionar volumes e malhas na Unity.

A lista detalhada, com decisões ainda abertas, está em
[`Orientacao-codex.md`](Orientacao-codex.md). A justificativa das métricas e da
delimitação do scan está em [`docs/methodology-adjustments.md`](docs/methodology-adjustments.md).
As tarefas individuais estão em
[`Pablo`](docs/tarefas-pablo-reconstrucao-modelos.md) e
[`Felipe`](docs/tarefas-felipe-sdf-ca.md).

## Observação sobre benchmarks

As métricas finais devem ser calculadas em ambiente controlado e reportadas com separação clara entre:

- tempo de treinamento;
- tempo de inferência/geração;
- custo de renderização/visualização;
- custo de integração, caso gRPC seja usado.

Não misture resultados de Colab, máquina local e ROCm na mesma tabela principal sem identificá-los como ambientes distintos.

As medições finais de estrutura usarão volumes `64³` em ZYX. CA e Random Walk
podem permanecer na CPU enquanto modelos neurais usam GPU para treino ou
inferência; o backend deve aparecer nos resultados de custo. Não é requisito
portar o CA para GPU apenas para produzir os mesmos volumes. Uma comparação
direta de tempo precisa considerar ambiente, etapa medida e transferências.
