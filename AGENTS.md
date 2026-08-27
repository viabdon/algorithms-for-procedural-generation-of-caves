# Guia de colaboração

## Objetivo do projeto

Este repositório compara métodos de geração procedural de cavernas 3D. A
representação padrão dos algoritmos é um `numpy.ndarray` booleano com forma
`(depth, height, width)`, onde `True` indica espaço aberto.

## Convenções de desenvolvimento

- O pacote Python está em `src/cavegen/`; mantenha os módulos pequenos e com
  responsabilidades explícitas.
- Use type hints, docstrings no estilo NumPy e nomes claros em português ou
  inglês, sem misturá-los na mesma API pública.
- Para dados grandes, prefira processamento incremental, `numpy.memmap` e
  parâmetros de limite/amostragem; não carregue datasets completos por padrão.
- Preserve `float32` para coordenadas de nuvens de pontos, salvo motivo
  documentado para outra precisão.
- Valide formatos e dimensões antes de transformar dados. Mensagens de erro
  devem identificar o arquivo e a condição inválida.
- A entrada real descreve superfície; não a trate como o volume de vazios dos
  geradores sem uma conversão metodologicamente documentada.

## Verificação

- Antes de concluir uma mudança Python, execute os testes disponíveis e uma
  checagem de importação ou exemplo pequeno pertinente.
- Não versione dados brutos, arquivos processados grandes, checkpoints ou
  resultados experimentais volumosos.

## Progresso atual do pipeline

- O leitor de arquivos ``.f32`` em ``src/cavegen/datastream/f32.py`` valida o tamanho
  dos registros, abre os dados com ``numpy.memmap`` em modo somente leitura e
  preserva ``float32``.
- Os iteradores ``iter_f32_xyz`` e ``iter_ply_xyz`` entregam coordenadas XYZ
  incrementalmente em lotes de forma ``(n_no_lote, 3)``. O leitor PLY processa
  ASCII por streaming e PLY binário com ``numpy.memmap``.
- ``reservoir_sample_xyz`` em ``cavegen.datastream.sampling`` produz uma
  amostra uniforme e reprodutível, sem reter mais de ``max_points`` pontos.
- Antes de usar o PLY do Elaphes, inspecione o cabeçalho real e confirme o
  formato, as propriedades de vértice e a ordem dos elementos declarados.
- A próxima etapa é calcular limites espaciais incrementalmente com esses
  lotes. A voxelização deve primeiro produzir ``surface_voxels``; qualquer
  derivação de ``void_voxels`` exige decisão metodológica documentada.

## Modo de orientação

Quando a solicitação for didática, explique primeiro a teoria, os contratos de
entrada/saída, as decisões de memória e exemplos mínimos. Não implemente a
solução nos arquivos do projeto, a menos que isso seja pedido explicitamente.
