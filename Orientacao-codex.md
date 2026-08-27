# Lista de tarefas — dados reais, voxelização e IA

## Parsers e inspeção de datasets

- [x] Corrigir a configuração do Elaphes para o formato `.ply` em
  `configs/datasets.yaml`.
- [x] Implementar o parser incremental `.f32` em `src/cavegen/datastream/f32.py`:
  validação do layout, `numpy.memmap` somente leitura e lotes XYZ `float32`.
- [x] Implementar o parser incremental `.ply` em `src/cavegen/datastream/ply.py`:
  validação de cabeçalho, PLY ASCII por streaming e PLY binário por
  `numpy.memmap`.
- [x] Criar testes sintéticos para PLY ASCII, binário little-endian e cabeçalho
  inválido em `tests/test_ply.py`.
- [ ] Inspecionar formalmente `data/raw/nasa/indian_tunnel.f32`: confirmar
  endianness, layout de sete atributos e valores plausíveis de XYZ.
- [ ] Inspecionar o cabeçalho real de
  `data/raw/elaphes/elaphes_cave.ply`: confirmar formato, propriedades de
  vértice e que `vertex` é o primeiro elemento suportado pelo parser.
- [x] Adicionar `reservoir_sample_xyz` em `cavegen.datastream.sampling` para
  amostragem reprodutível por `max_points`, sem carregar o dataset inteiro.

## Pré-processamento e voxelização

- [ ] Calcular `min_xyz` e `max_xyz` incrementalmente a partir dos lotes XYZ.
  O contrato, as validações e o teste esperado estão em `docs/roadmap.md`.
- [ ] Definir e implementar a normalização espacial, incluindo o tratamento de
  eixos degenerados e a decisão entre preservar proporção ou preencher o cubo.
- [ ] Criar `src/cavegen/core/voxelization.py` para gerar
  `surface_voxels: np.ndarray[bool]` a partir de pontos normalizados.
- [ ] Testar primeiro uma referência pequena em resolução `32³`; só então
  avaliar `64³` e `128³`.
- [ ] Salvar referências de superfície em `.npz` com metadados de origem,
  resolução e normalização.
- [ ] Documentar em `docs/` a diferença metodológica entre `surface_voxels` e
  `void_voxels`, incluindo as limitações de usar IoU diretamente entre ambos.
- [ ] Definir e justificar qualquer conversão de superfície para volume vazio
  antes de comparar dados reais com os geradores.

## Dataset para GAN e Colab

- [ ] Gerar um dataset sintético inicial com Random Walk e Cellular Automata.
- [ ] Produzir inicialmente cerca de 1.000 volumes `32³` e manter dados e
  checkpoints fora do Git.
- [ ] Definir o formato para PyTorch: `(B, 1, D, H, W)`.
- [ ] Criar notebook mínimo em `notebooks/colab/` com instalação, carregamento
  de `.npz`, visualização de slices, `Dataset`, `DataLoader` e inspeção de um
  batch.
- [ ] Implementar um baseline neural simples (autoencoder ou DCGAN) antes de
  iniciar WGAN ou PCGRL.

## Ordem recomendada

1. Validar os dois datasets reais com seus parsers.
2. Calcular limites e normalização incrementalmente.
3. Voxelizar a superfície em baixa resolução e documentar a semântica.
4. Gerar o dataset sintético e preparar o notebook Colab.
5. Treinar GAN; deixar PCGRL para depois do baseline clássico e neural.
