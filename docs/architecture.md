# Arquitetura técnica atualizada

## Decisão principal

O projeto passa a adotar uma arquitetura **offline-first** no estágio inicial. A geração, as métricas e os benchmarks ficam centralizados em Python. A Unity é mantida como visualizador e demonstrador gráfico, enquanto gRPC é deslocado para uma fase posterior.

## Justificativa

A comparação científica depende de métricas reprodutíveis. Por isso, IoU, conectividade, estatísticas morfológicas e tempo de execução devem ser calculados por scripts Python versionados, com entradas e saídas rastreáveis. Unity é adequada para inspeção visual e demonstração, mas não deve ser a fonte primária dos resultados quantitativos.

## Fluxo de dados inicial

```text
Python generator -> Volume3D (.npz) -> metrics CSV
                 -> mesh (.obj/.glb) -> Unity visualizer
```

## Fluxo de dados posterior com gRPC

```text
Unity client -> GenerateCave request -> Python gRPC server
Unity renderer <- voxel bytes / mesh data <- Python gRPC server
```

## Convenção dos dados

Todos os algoritmos devem produzir a mesma representação interna:

```text
numpy.ndarray[bool], shape = (depth, height, width)
True  = espaço aberto de caverna
False = espaço fechado/sólido
```

Essa padronização evita que diferenças de representação contaminem a comparação entre algoritmos.

## Backends de execução

- Google Colab/CUDA ou CPU: ambiente inicial de treinamento e prototipação.
- CPU local: desenvolvimento, testes unitários e baselines clássicos.
- AMD/ROCm: portabilidade opcional após estabilização do pipeline.

## Separação metodológica obrigatória

Para GAN e PCGRL, os resultados devem separar:

1. custo de treinamento;
2. custo de inferência/geração;
3. custo de exportação/meshificação;
4. custo de visualização ou integração, se medido.
