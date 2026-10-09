# Arquitetura técnica do pipeline experimental

## Estado do repositório e decisão

Python permanece como ambiente de preparação, reconstrução, métricas e benchmark;
Unity renderiza as malhas finais, e gRPC é posterior. A etapa Poisson em Python
produz um arquivo de malha e metadados; não depende de renderização em Python.
O código atual lê XYZ em
lotes, calcula limites, gera `surface_voxels` por ocupação de pontos, produz
`Volume3D` para Random Walk/CA e extrai malhas desses volumes por Marching
Cubes. **Marching Cubes não reconstrói a point cloud real**; a rota de
referência agora possui um primeiro protótipo de Screened Poisson em
`cavegen.meshing.poisson`, ainda sem malha real aceita. No Elaphes, o ensaio
global mais denso (22.368 representantes, `depth=8`) melhorou a distância
ponto→malha, mas manteve 175 arestas de borda, 27 não manifold e extrapolação
até o limite cúbico do Poisson. Remover vértices de baixa densidade reduz
extrapolação e aumenta aberturas; essas candidatas não alimentam ainda o SDF.

A referência real passará pela sequência principal:

```text
point cloud XYZ (+ atributos úteis)
  -> amostragem espacial/controle de memória e normais orientadas
     ↳ linha central exploratória (LBC + MST) para inspecionar orientação por trecho
  -> Screened Poisson Surface Reconstruction
     (Ball Pivoting/Alpha Shapes como fallbacks de reconstrução)
  -> malha validada, aproximadamente watertight, com entradas/tampas marcadas
  -> voxelização da barreira + classificação interior/exterior
     (flood fill principal; testes de ocupação/winding como comparação/fallback)
  -> distâncias à superfície + sinal da classificação = SDF físico em grade
  -> TSDF truncado/normalizado + rótulos VOID/SURFACE/SOLID/UNKNOWN
```

O SDF exige uma decisão de sinal; não substitui a classificação. O flood fill
exige uma barreira adequada; em cavernas abertas, entradas legítimas precisam
de tratamento explícito para não produzirem vazamento. Uma malha watertight
pode conter tampas artificiais e, portanto, ainda requer validação geométrica
e semântica. O artefato de `surface_voxels` atual permanece útil para inspeção
e comparação com pontos observados, mas não é a entrada final do SDF.
A [linha central exploratória](linha-central-elaphes-exploracao.md), adaptada de
[Racine et al.](../resumos-teoricos/linha-central-racine.md), também não define
o interior: ela pode sugerir várias posições interiores e trechos de
orientação das normais **depois** de conferir os nós com cortes do scan. A
poda precisa preservar o ramo real curto perto de X≈30 e revisar a bifurcação
maior perto de X≈42; um limiar global de comprimento apagaria geometria real.

## Contratos entre as etapas

| Artefato | Convenção | Uso |
| --- | --- | --- |
| Point cloud | XYZ contínuo, fonte e atributos registrados | Estimar normais e reconstruir malha |
| Linha central candidata | Nós XYZ, arestas, recorte, parâmetros e trechos validados | Inspeção e possível apoio à orientação local; não fornece sinal por si |
| Malha real candidata | Vértices XYZ, faces orientadas, faces sintéticas marcadas | Inspeção, classificação e distância |
| Grade de classificação | ZYX, shape, origem, espaçamento, região válida | Sinal e incerteza do SDF |
| SDF físico | `float32[D,H,W]`, distância à malha, negativo em `VOID` | Geometria e avaliação |
| TSDF | `clip(SDF, -τ, τ) / τ`, `τ > 0` documentado | Entrada/alvo de aprendizagem e controle |
| Rótulos | `VOID`, `SURFACE`, `SOLID/EXTERIOR`, `UNKNOWN` | Máscaras e visualização |
| Volume gerado | `Volume3D.data: bool[D,H,W]`, `True = VOID` | Baselines, redes e métricas |

O `UNKNOWN` deve ser representado por máscara de validade ou rótulo separado;
não é um valor de distância positivo nem negativo. Nas células válidas,
`SDF < -ε` define `VOID`, `|SDF| ≤ ε` define `SURFACE` e `SDF > ε` define
`SOLID/EXTERIOR`. Fixar `ε` em unidade física e estudar sensibilidade à
resolução. Preservar campo contínuo e rótulos separadamente. A mesma
transformação XYZ↔ZYX deve valer para malha, SDF, CA e saídas neurais.
O domínio da grade deverá derivar da **malha aceita**, com margem física e
padding documentados, em vez de exigir uma região de interesse fixa para cada
scan. A conversão para o eixo vertical da Unity pertence à exportação e deve
ser testada com pontos de referência, preservando o contrato ZYX interno.

## Campos diferentes para referência e controle

**SDF de referência:** calculado da malha real aceita, com interior/exterior
validado e `UNKNOWN`. Serve à construção da referência, às métricas e,
somente no treino, a possíveis alvos de aprendizagem.

**SDF de controle do CA:** campo simplificado e independente da referência de
teste, derivado por exemplo de tubos, esqueleto procedural ou pontos de
entrada/saída. Enviesa a regra local do CA em direção a uma forma coesa.
`CA+SDF` deve manter o CA original como baseline. Usar o SDF exato da caverna
de teste caracteriza reconstrução condicionada e exige avaliação separada.

Após validar `CA+SDF`, um algoritmo genético poderá otimizar parâmetros da
regra e do condicionamento. Seu custo de busca será contabilizado separadamente
da geração; dados de teste não participam da aptidão.

## Modelos neurais e avaliação

Uma GAN pode aprender `VOID` binário ou TSDF, decisão dependente de dados
reais válidos e suficientes. O PCGRL usa o dataset para extrair metas
estruturais de treino quando elas forem confiáveis; requer especificação do
MDP e ambiente pequeno antes de PPO. O resumo de Deep RL do projeto recomenda
começar por Narrow 3D, conectividade e ocupação, deixando Conv3D e controle
mais elaborado para depois.

IoU volumétrica compara apenas `VOID` real validado e `VOID` gerado no mesmo
domínio e máscara válida. ASSD, Hausdorff95 e Surface Dice comparam superfícies
compatíveis e distinguem faces observadas de tampas sintéticas. Conectividade,
ocupação, largura e diversidade são dimensões adicionais. Dividir exemplos
por caverna ou região espacial independente para evitar vazamento entre
patches. Registrar origem, parâmetros, tempo de preparação, otimização/treino,
geração e exportação por hardware/backend.

As decisões e riscos estão em
[`methodology-adjustments.md`](methodology-adjustments.md), e as tarefas por
responsável estão em [`Orientacao-codex.md`](../../Orientacao-codex.md).
O processamento de bins, normais e octree está detalhado em
[`amostragem-normais-screened-poisson.md`](amostragem-normais-screened-poisson.md).
Os HTMLs de inspeção da linha e das malhas podem ser regenerados pelo
[`plot_elaphes.py`](../../plots/plot_elaphes.py); eles são diagnósticos em
Python, enquanto Unity permanece o visualizador das malhas finais.
