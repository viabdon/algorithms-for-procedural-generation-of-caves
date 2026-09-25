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

## 6. Vetorização da contagem de vizinhos no autômato celular

A contagem de vizinhos do autômato celular deixou de ser um laço tríplice em Python, que visitava célula por célula e somava o cubo 3×3×3 ao redor de cada uma, e passou a ser uma convolução do volume por um kernel 3×3×3 de uns (`scipy.ndimage.convolve`). A justificativa é de validade da comparação, não de conveniência: como o TCC mede desempenho computacional de métodos com e sem IA, e os métodos baseados em IA executam sobre bibliotecas compiladas e aceleradas por GPU, medir o autômato celular em Python interpretado faria os números descreverem a implementação em vez do algoritmo, enviesando a comparação contra o método não-IA. A operação é matematicamente a mesma — a soma da vizinhança de todas as células é, por definição, uma convolução —, com a diferença de que o percurso das vizinhanças passa a ocorrer em código compilado, de uma só vez, em vez de em laços interpretados. O tratamento de borda foi reexpresso como uma moldura de uma célula aplicada ao volume antes da convolução, o que faz os três modos (borda vazia, borda cheia e borda sorteada) percorrerem o mesmo caminho de código, em vez de virarem casos especiais dentro da contagem.

O ganho medido em volumes de 64³ foi de duas ordens de grandeza: de 2,67 s para 0,0064 s por iteração, entre 400 e 580 vezes mais rápido conforme a medição. Na prática isso muda o que é viável experimentalmente. Uma varredura completa das combinações de sensibilidade, tratamento de borda e número de iterações, que exigiria cerca de 12 horas de execução, passa a levar menos de dois minutos, o que dispensa paralelização e permite repetições suficientes para tratamento estatístico. Volumes de 128³, antes inviáveis a aproximadamente 25 s por iteração, passam a custar 0,045 s, ampliando a faixa de resolução que o trabalho pode investigar.

A equivalência entre as duas versões foi verificada e não é aproximada: os resultados são idênticos bit a bit em toda a faixa de sensibilidade (0 a 27), em volumes cúbicos e não cúbicos, e ao longo de múltiplas iterações. Dos 26 volumes já gerados e armazenados antes da mudança, 24 são reproduzidos exatamente pela nova implementação; as duas exceções usam borda sorteada, que nunca foi reproduzível, pois sorteia valores novos a cada execução — limitação que passa a estar documentada e que exclui esse modo de borda de comparações que exijam repetição idêntica. A verificação está fixada como teste automatizado, no qual o laço original é preservado como oráculo. Isso também resolve a medição de complexidade de implementação: ela continua sendo calculada sobre a versão em laço, que é a tradução literal da regra do autômato, de modo simétrico ao que se faz do lado da IA, onde se contabiliza a definição do modelo e não o código interno da biblioteca.
