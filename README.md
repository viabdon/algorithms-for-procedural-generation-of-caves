# CaveGen TCC — Algoritmos de Geração Procedural de Cavernas 3D

Repositório do Trabalho de Conclusão de Curso **"Algoritmos de Geração Procedural de Cavernas: Uma Comparação Holística"**.

O objetivo do projeto é comparar algoritmos clássicos e baseados em aprendizado de máquina para geração procedural de cavernas tridimensionais. A comparação considera custo computacional, tempo de execução, consumo de recursos, complexidade de implementação e similaridade volumétrica em relação a referências reais ou análogos quantitativos de cavernas.

## Estratégia atual

A arquitetura prioriza um pipeline científico **offline-first**:

1. Referências reais seguem point cloud → normais → Screened Poisson Surface
   Reconstruction → malha validada → classificação interior/exterior → SDF/TSDF
   → `VOID`, `SURFACE`, `SOLID` e `UNKNOWN`.
2. Python gera volumes 3D, calcula métricas e registra benchmarks.
3. Cellular Automata básico será comparado com versões guiadas por um SDF de
   controle e, em etapa final, otimizadas por algoritmo genético.
4. Arquivos `.npz` e malhas permitem inspeção na Unity; gRPC é posterior.
5. Colab/CUDA é opção inicial de treino neural, e AMD/ROCm é portabilidade
   opcional.

Essa decisão reduz risco operacional e mantém o foco principal na comparação quantitativa dos algoritmos.

## Algoritmos previstos

- Random Walk 3D
- Cellular Automata 3D básico, guiado por SDF e depois ajustado por algoritmo
  genético
- GAN 3D, com arquitetura a escolher após auditar os volumes disponíveis
- PCGRL 3D, após definir e validar o ambiente e a recompensa

## Convenção de volume

Neste repositório, um volume 3D é representado por um `numpy.ndarray` booleano de forma `(depth, height, width)`.

- `True`: voxel aberto, isto é, espaço de caverna/túnel.
- `False`: voxel fechado/sólido.

Essa convenção descreve os **volumes gerados**. A referência real incluirá
também SDF/TSDF, rótulos e máscara de `UNKNOWN`; IoU só será aplicada às
regiões `VOID` válidas e comparáveis.

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
não substitui a reconstrução de malha nem a classificação volumétrica.

Execução registrada para o Elaphes em `32³`: 245 de 32.768 voxels (0,75%) foram
marcados como superfície. O arquivo `elaphes_surface_32.npz` é um artefato local
de dados processados e não faz parte do Git.

## Reconstrução da referência real

A rota planejada parte novamente da point cloud em coordenadas contínuas.
Screened Poisson é o método principal para reconstruir a malha; Ball Pivoting
e Alpha Shapes são fallbacks a investigar. Entradas de caverna e faces de
fechamento sintéticas devem ser registradas. Felipe implementará flood fill e
SDF/TSDF inicialmente em casos sintéticos, enquanto Pablo prepara a malha.
O campo terá sinal negativo em `VOID`, positivo em `SOLID/EXTERIOR`, uma banda
`SURFACE` perto de zero e `UNKNOWN` onde a classificação for incerta.

Para o CA, um SDF de **controle simplificado**, independente da caverna de
teste, poderá enviesar a regra. Usar o SDF exato da referência de teste é um
experimento distinto de reconstrução condicionada. O algoritmo genético será
avaliado depois de estabilizar `CA+SDF`.

## Exportação de volumes gerados para malha

```bash
uv run python -m cavegen.meshing.export_mesh \
  --input results/volumes/random_walk_seed_0.npz \
  --output results/meshes/random_walk_seed_0.obj
```

## Roadmap resumido

1. Preparar normais, reconstruir e validar a malha da referência real.
2. Desenvolver em paralelo flood fill, SDF/TSDF e CA guiado por um campo
   sintético; depois integrar a malha real.
3. Validar rótulos, máscaras e métricas no mesmo domínio espacial.
4. Comparar CA básico, CA+SDF e, ao final, CA+SDF+algoritmo genético.
5. Auditar dados para GAN e formalizar o MDP antes do PCGRL; treinar modelos
   pequenos e separar custo de treinamento de geração.
6. Consolidar benchmarks em Python e visualizar os resultados na Unity.

A lista detalhada, com decisões ainda abertas, está em
[`Orientacao-codex.md`](Orientacao-codex.md). A justificativa das métricas e da
reconstrução está em [`docs/methodology-adjustments.md`](docs/methodology-adjustments.md).
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
