# Ajustes metodológicos recomendados para o texto do TCC

## 1. Ambiente de execução

Substituir a dependência rígida de AMD/ROCm por uma descrição em camadas:

- ambiente principal de treinamento: Google Colab com GPU NVIDIA/CUDA quando disponível;
- ambiente de desenvolvimento e integração: máquina local;
- ambiente AMD/ROCm: portabilidade experimental opcional.

## 2. Métricas

Recomenda-se que IoU e demais métricas quantitativas sejam calculadas em Python, não diretamente na Unity. A Unity deve ser descrita como ferramenta de visualização e demonstração.

## 3. Integração Unity

gRPC deve permanecer no projeto, mas como etapa posterior. Na primeira etapa, o fluxo por arquivos `.npz` e `.obj/.glb` é suficiente e mais reprodutível.

## 4. Treinamento versus inferência

Para GAN e PCGRL, o texto deve separar custo de treinamento e custo de geração. CA e Random Walk não possuem etapa de treinamento, logo comparações diretas só são justas no nível de inferência/geração.

## 5. Tabelas de resultado

Resultados obtidos em Colab, CPU local e ROCm não devem ser agregados como se fossem do mesmo ambiente. Cada tabela deve explicitar hardware, backend, versão de bibliotecas e tipo de runtime.
