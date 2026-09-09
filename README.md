# CaveGen TCC — Algoritmos de Geração Procedural de Cavernas 3D

Repositório do Trabalho de Conclusão de Curso **"Algoritmos de Geração Procedural de Cavernas: Uma Comparação Holística"**.

O objetivo do projeto é comparar algoritmos clássicos e baseados em aprendizado de máquina para geração procedural de cavernas tridimensionais. A comparação considera custo computacional, tempo de execução, consumo de recursos, complexidade de implementação e similaridade volumétrica em relação a referências reais ou análogos quantitativos de cavernas.

## Estratégia atual

A arquitetura foi reorganizada para priorizar um pipeline científico **offline-first**:

1. Python gera volumes 3D padronizados em voxels.
2. As métricas quantitativas são calculadas em Python.
3. Os volumes e meshes são exportados para arquivos (`.npz`, `.obj`, `.glb`) para inspeção e visualização.
4. Unity é usada inicialmente como visualizador, não como fonte das métricas científicas.
5. gRPC entra como fase posterior para integração interativa Python ↔ Unity.
6. Google Colab/CUDA é o backend inicial para treinamento de GAN/PCGRL.
7. AMD/ROCm fica como portabilidade opcional se houver tempo.

Essa decisão reduz risco operacional e mantém o foco principal na comparação quantitativa dos algoritmos.

## Algoritmos previstos

- Random Walk 3D
- Cellular Automata 3D
- GAN 3D, inicialmente com DCGAN/WGAN simplificada em volumes pequenos
- PCGRL 3D, inicialmente com ambiente reduzido e recompensas simples

## Convenção de volume

Neste repositório, um volume 3D é representado por um `numpy.ndarray` booleano de forma `(depth, height, width)`.

- `True`: voxel aberto, isto é, espaço de caverna/túnel.
- `False`: voxel fechado/sólido.

Essa convenção permite calcular IoU, conectividade e morfologia diretamente sobre o espaço navegável da caverna.

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

## Primeiro teste

Gere volumes de Random Walk e Cellular Automata em pequena escala:

```bash
uv run python -m cavegen.benchmark.run_generation_benchmark \
  --config configs/experiments/baseline_32.yaml \
  --out results/csv/baseline_32.csv
```

Os volumes gerados serão salvos em `results/volumes/` e a tabela de tempos em `results/csv/`.

## Voxelização de referência PLY

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
observada, e não espaço aberto de caverna; por isso ela ainda não deve ser usada
diretamente nas métricas dos volumes gerados.

Execução registrada para o Elaphes em `32³`: 245 de 32.768 voxels (0,75%) foram
marcados como superfície. O arquivo `elaphes_surface_32.npz` é um artefato local
de dados processados e não faz parte do Git.

## Exportação para mesh

```bash
uv run python -m cavegen.meshing.export_mesh \
  --input results/volumes/random_walk_seed_0.npz \
  --output results/meshes/random_walk_seed_0.obj
```

## Roadmap resumido

1. Criar esqueleto técnico do repositório.
2. Implementar Random Walk 3D e Cellular Automata 3D.
3. Implementar métricas em Python: IoU, conectividade e estatísticas morfológicas.
4. Exportar volumes e meshes para visualização offline.
5. Criar visualizador simples em Unity por importação de arquivos.
6. Treinar modelos GAN/PCGRL no Colab.
7. Rodar benchmark principal com mesmas seeds, dimensões e métricas.
8. Adicionar gRPC como integração interativa.
9. Testar portabilidade AMD/ROCm se houver tempo.

## Observação sobre benchmarks

As métricas finais devem ser calculadas em ambiente controlado e reportadas com separação clara entre:

- tempo de treinamento;
- tempo de inferência/geração;
- custo de renderização/visualização;
- custo de integração, caso gRPC seja usado.

Não misture resultados de Colab, máquina local e ROCm na mesma tabela principal sem identificá-los como ambientes distintos.
