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
├── docs/                 # Tarefas, resumos teóricos e metodologia
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

A [explicação metodológica completa](docs/metodologia/amostragem-normais-screened-poisson.md)
detalha bins, estatísticas, normais, octree, parâmetros e os primeiros ensaios.

A rota parte novamente da point cloud em coordenadas contínuas. O protótipo
`cavegen.meshing.poisson` reutiliza o leitor PLY e os limites do JSON do Elaphes,
amostra um ponto por célula espacial sem carregar os 94 milhões de pontos e
estima/orienta normais para o Screened Poisson. O PLY não contém normais.
Os `batches` são blocos temporários de leitura; os `bins` são células 3D
persistentes definidas pelos limites XYZ. A regra `first` guarda o primeiro
ponto encontrado em cada bin ocupado. A regra `centroid` calcula a média dos
pontos e persiste contagem e desvio padrão XYZ por bin. Não há sorteio; com
mesmo PLY, ordem, limites, `--max-points` e regra, a amostra é reproduzível.
Esses bins formam uma grade regular; a octree adaptativa pertence ao Poisson.
`--max-points` limita o número de bins e o máximo de pontos retidos. Dispersão
alta pode indicar ruído ou superfícies distintas na mesma célula; nesse caso,
o centróide pode cair fora da superfície real.
Instale a dependência opcional no ambiente do projeto antes da reconstrução:

```bash
uv pip install --python .venv/bin/python -e '.[reconstruction]'
```

Uma passagem pelo arquivo ASCII de 6,3 GB pode levar vários minutos. A amostra
é persistida para ajustar os parâmetros da reconstrução sem reler o scan:

```bash
.venv/bin/python -m cavegen.meshing.poisson \
  --ply /run/media/midnavi/Pablo/TCC/DATA/RAW/elaphes_cave.ply \
  --bounds data/params/elaphes_xyz_bounds.json \
  --sample-path data/processed/elaphes_poisson_sample.npz \
  --sample-only

.venv/bin/python -m cavegen.meshing.poisson \
  --ply /run/media/midnavi/Pablo/TCC/DATA/RAW/elaphes_cave.ply \
  --bounds data/params/elaphes_xyz_bounds.json \
  --sample-path data/processed/elaphes_poisson_sample.npz \
  --output results/meshes/elaphes_candidate.obj
```

Para comparar centróides, use `--sampling-rule centroid` com outro
`--sample-path` e outro `--output`. O cache da amostra é específico da regra.

O `.obj` é um artefato de malha para inspeção e posterior importação na Unity;
Python não renderiza a malha. O JSON ao lado do OBJ registra parâmetros e
diagnósticos. A orientação global das normais pode ser ajudada por
`--interior-seed-xyz X Y Z` quando houver uma posição sabidamente navegável.
Essa *seed* é uma coordenada semântica de orientação, não uma seed de sorteio.
O protótipo usa uma thread no Poisson por padrão e grava a versão do Open3D,
o número de threads, a seed de orientação, o critério de amostragem e o hash
registrado da fonte. Se uma etapa futura introduzir sorteio, sua seed aleatória
também deverá ser persistida.
**O resultado é apenas uma malha candidata:** verificar entradas, extrapolações,
densidade, orientação e fechamento antes de usá-la no flood fill. Ball Pivoting
e Alpha Shapes são fallbacks a investigar. Entradas de caverna e faces de
fechamento sintéticas devem ser registradas. Felipe implementará flood fill e
SDF/TSDF inicialmente em casos sintéticos, enquanto Pablo prepara a malha.
O campo terá sinal negativo em `VOID`, positivo em `SOLID/EXTERIOR`, uma banda
`SURFACE` perto de zero e `UNKNOWN` onde a classificação for incerta.

Primeiro ensaio local: a leitura completa reteve 1.864 pontos em bins
`82×16×76` (529 s). Com `depth=7`, Open3D 0.20.0 e uma thread, o Poisson gerou
6.173 vértices e 12.212 triângulos, mas a malha tem 186 arestas de borda,
13 arestas não manifold e extrapola além do scan no eixo Y. **Essa candidata
não está aprovada para classificação volumétrica.** A unidade física das
coordenadas originais ainda precisa ser confirmada.

Comparação preliminar da regra `centroid` sobre os mesmos bins: 1.864
centróides, 215 arestas de borda, 3 arestas não manifold e 4 componentes de
triângulos, contra 186, 13 e 3 com `first`. Nenhuma malha é watertight, e o
centróide extrapola mais no eixo Y. A distância ponto–malha calculada sobre a
união das duas amostras deu p95 de 0,678 unidade XYZ para `centroid` e 0,712
para `first`; a diferença é pequena e essa amostra não substitui a comparação
com o scan completo. O desvio espacial p95 por bin foi 0,490 unidade XYZ.
Assim, o centróide isolado ainda não justifica aceitar a malha; investigar
resolução dos bins, regiões dispersas, orientação das normais e suporte local.

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
reconstrução está em [`ajustes de metodologia`](docs/metodologia/methodology-adjustments.md).
As tarefas individuais estão em
[`Pablo`](docs/tarefas/tarefas-pablo-reconstrucao-modelos.md) e
[`Felipe`](docs/tarefas/tarefas-felipe-sdf-ca.md). O [índice de documentação](docs/README.md)
reúne tarefas, teoria e as explicações da implementação.

## Observação sobre benchmarks

As métricas finais devem ser calculadas em ambiente controlado e reportadas com separação clara entre:

- tempo de treinamento;
- tempo de inferência/geração;
- custo de renderização/visualização;
- custo de integração, caso gRPC seja usado.

Não misture resultados de Colab, máquina local e ROCm na mesma tabela principal sem identificá-los como ambientes distintos.
