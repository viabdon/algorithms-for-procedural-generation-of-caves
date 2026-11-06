# Arquitetura técnica do pipeline experimental

## Decisão vigente em 18/10/2026

O fluxo principal parte dos geradores e é executado em Python. A reconstrução do Elaphes, o SDF real e a IoU volumétrica contra o scan saíram do caminho crítico do benchmark. A decisão consta do [resumo quinzenal](relatorios/resumo-quinzenal-tcc-2026-10-18.docx).

```text
gerador -> Volume3D (bool[D,H,W], ZYX) -> NPZ
        -> métricas e CSV em Python
        -> malha de visualização por Marching Cubes -> Unity
```

`True`/`1` significa ar e `False`/`0`, sólido. A grade final de medição é `64³` em ZYX. Sementes, parâmetros, hardware e orçamento devem acompanhar cada experimento; tamanho físico do voxel só pode ser declarado se houver uma escala conhecida. Marching Cubes extrai malhas dos volumes gerados; não reconstrói a nuvem real. Unity serve à inspeção, e gRPC fica para depois do benchmark científico.

## Contrato público do SDF de volumes gerados

Para uma caverna voxelizada com interior conhecido, o SDF é um campo `float32[D,H,W]` na mesma grade ZYX do volume. O sinal é **positivo no interior do vazio da caverna**, **negativo no exterior sólido** e **zero nos voxels classificados como borda**. A magnitude é a distância euclidiana até o voxel de borda mais próximo, expressa em **voxels**; o zero fica no centro do voxel de borda. A classificação auxiliar do Random Walk (`classificar` em `src/cavegen/generators/random_walk/voxelizacao.py`) trata como borda o voxel vazio que toca sólido por uma das seis faces, com fora da grade contando como sólido; o protótipo de SDF do Random Walk, hoje só no histórico (`a58155e`), partia dessa classificação. Guardar a convenção de sinal, a regra de borda, os eixos e a unidade nos metadados.

Este é o contrato escolhido para novos campos sintéticos; não afirma que já exista uma API pública de SDF integrada ao pacote `cavegen`. Se um futuro campo usar espaçamento físico ou outra regra de borda, a conversão e os metadados precisarão ser explícitos.

## Contratos e implementação no `main`

| Etapa | Contrato | Estado |
| --- | --- | --- |
| Random Walk e CA básico | Saída-alvo `Volume3D` booleano em ZYX | Random Walk já retorna `Volume3D`; CA retorna matriz e histórico e precisa de adaptação ao benchmark |
| Persistência | Volume gerado em NPZ | Implementada |
| Avaliação estrutural | `evaluate_structure(Volume3D)` → `StructuralMetrics` imutável | Ocupação, componentes e EDT, validações e degeneração explícitas; registro plano `structural-v1` |
| Benchmark inicial | Uma linha por execução no CSV central, com NPZ rastreável | Código de persistência incremental e medições iniciais disponível; importação bloqueada pela API do CA; protocolo e resultados finais pendentes |
| Marching Cubes | Malha derivada do volume gerado | Disponível para visualização |
| GAN e PCGRL | Devem gerar `Volume3D` | Interfaces ainda lançam `NotImplementedError` |
| CPU/GPU/VRAM e descritores adicionais | Protocolo e instrumentação | Amostrador disponível; protocolo e inclusão no CSV ainda pendentes |

A transformada de distância descreve o espaço livre em unidades da grade atual. Seus resumos não validam, por si sós, a largura de todos os túneis. Resolução, espaçamento e bordas precisam ser explicitados para interpretações físicas.

O [contrato estrutural](metricas-estruturais.md) usa conectividade 6 por padrão,
spacing ZYX explícito e exterior sólido para a EDT de volumes mistos. Volumes
totalmente sólidos ou abertos têm distâncias ausentes e motivo de degeneração.
O benchmark obtém as colunas do agregador e acrescenta linhas a
`results/csv/experiments.csv`, preservando NPZ em subpastas por experimento.

`python -m cavegen` abre o menu interativo em `cavegen.menu`. A interface usa
`run_configuration` para geração e `evaluate_archive` para reavaliar NPZ.
Ambos usam a mesma construção e persistência de registros, preservando o
cabeçalho `structural-v1`; reavaliações usam a variante `structural_evaluation`
e não preenchem custos de geração. Operações repetitivas futuras devem ser
adicionadas ao menu com serviços reutilizáveis, validação, cancelamento e
glossário no documento da funcionalidade.

## Código de clássicos integrado e histórico da branch `CA`

O CA foi reorganizado em um pacote com convolução 3D para contar a vizinhança, bordas configuráveis, sementes/resultados NPZ, menu e pesos espaciais opcionais. O peso é somado à contagem antes do limiar em cada passo. Testes da branch verificam equivalência com a versão em laço nas bordas determinísticas e igualdade entre CA sem peso e com peso zero. A borda aleatória não é reproduzível bit a bit.

O rastreador novo amostra tempo, CPU e RSS do processo, além de GPU/VRAM quando houver leitura; resultados ausentes não devem ser interpretados como zero. O benchmark usa o `ResourceSampler` para tempo e pico de RSS; CPU e GPU/VRAM são amostradas, mas não entram nas 45 colunas do CSV central. Ele ainda não importa neste checkout, porque a integração do CA será feita separadamente pelo Felipe.

### Random Walk (migração verificada em 02/11/2026, commits `216f38d` a `e121f44`)

O gerador público de Random Walk passou a ser o random walk ponderado por waypoints do projeto base (3D-Cave-Generation, commit `7a6c617`), no pacote `src/cavegen/generators/random_walk/`. Ele substitui `src/cavegen/generators/random_walk.py` (random walk de 6 direções com `steps` e `brush_radius`), que foi apagado. O protótipo `random_walk_temp/` também foi apagado; a migração não mudou a lógica, e os NPZ da seed 1 das quatro cavernas são idênticos bit a bit aos do protótipo.

| Etapa | Contrato | Estado |
| --- | --- | --- |
| Grafos de waypoints | `configs/random_walk/<caverna>.yaml`, exportados uma vez da cena Unity por `exportar_cena.py`; eixos da Unity | Implementado; quatro cavernas, grafo idêntico ao da cena |
| Caminhada | `gerar_caminhos(grafo, rng) -> (pontos, inicios)`, porte de `WeightedRandomWalk.cs`/`PathGenerator.cs` com `numpy_rng` | Implementado; testes com tradução literal do C# como oráculo |
| Voxelização | Cápsulas de raio `raio_voxels` (padrão 1,5) em grade cúbica, encaixe com a mesma escala e margem de 2 voxels | Implementado |
| Gerador | `generate_random_walk(shape, seed, caverna, weight, k, spacer, raio_voxels) -> Volume3D` e `RandomWalkGenerator`; grade cúbica com lado > 5 | Implementado |
| Menu | `menu.py` grava `results/result_000.npz` por `run_and_save`, medido com `track_resources`, e plota caminhos ou grade classificada; não passa pelo benchmark | Implementado (`658d397`) |
| SDF do Random Walk | Contrato de SDF sintético acima | Fora do pacote por decisão do Felipe; protótipo só no histórico (`a58155e`) |
| Benchmark | Aceitar os parâmetros novos | Lado do Random Walk adaptado no merge da `main` de 04/11/2026; só executa depois da integração do CA |

Os waypoints vêm de modelos de cavernas reais do projeto base, portanto a forma da caverna não é independente dessa informação. O raio padrão de 1,5 voxel em `64³` engrossa os tubos em relação à escala original. Os grafos são encontrados por caminho relativo ao arquivo, o que exige rodar do repositório ou de instalação editável. Detalhes, números medidos e limites em [Random Walk](random-walk.md).

## Referência real como frente exploratória

O PLY do Elaphes contém pontos de parede observada. A grade diagnóstica `32³` marca 245 voxels de superfície em 32.768 células. Ela não representa ar; seu complemento mistura interior, exterior e regiões não observadas. Portanto, a grade não é uma referência para IoU com os volumes gerados.

Os experimentos de amostragem, Screened Poisson, linha central, orientação de normais e espessamento estão preservados na branch `experiment/elaphes-meshing` e em artefatos locais. Nenhuma malha avaliada validou conjuntamente fechamento, ausência de auto-interseções, conectividade e aderência à nuvem. Não há classificação interior/exterior nem SDF real confiável para o benchmark. A conclusão vale para os testes feitos no Elaphes, sem demonstrar impossibilidade geral. Ball Pivoting, Alpha Shapes, winding numbers e fechos controlados permanecem hipóteses sem comparação concluída nesse conjunto.

Na branch `CA`, `sdf_temp/` calcula flood fill e distância euclidiana à borda da grade de superfície `64³`. O campo também usa interior positivo, exterior negativo e distância em voxels, mas seu "interno" pode ser espessura de parede ou buracos fechados; entradas abertas tornam o ar do túnel alcançável pelo exterior. Compartilhar sinal e unidade com o contrato sintético não torna as classes semanticamente equivalentes. O campo serve ao ensaio de peso espacial, mas não valida `VOID` real, distância física ou IoU volumétrica.

O scan pode apoiar inspeção qualitativa e propriedades efetivamente observáveis. Métricas de superfície exigiriam regiões alinhadas e comparáveis, tolerância e distinção entre parede medida e geometria extrapolada. IoU de superfície não substitui automaticamente IoU volumétrica.

## Extensões

Uma variante de CA com peso espacial já existe na branch `CA`. O ensaio com o campo do Elaphes demonstra o efeito do peso na regra, sem fornecer avaliação de semelhança volumétrica real. A extensão guiada requer campo procedural com semântica e unidade documentadas, independente do scan de teste. Peso zero já foi verificado contra o CA básico; ainda falta comparar resultados sob protocolo comum. Está planejado ajustar geneticamente parâmetros de CA e Random Walk, com orçamento e sementes de avaliação reservadas, custo de busca separado e controle por busca simples de mesmo orçamento.

Uma GAN requer volumes de treino com semântica válida; dados sintéticos verificam a infraestrutura, mas não sustentam alegação de aprendizagem de cavernas reais. PCGRL deve começar com ambiente pequeno e recompensa de conectividade e ocupação, após definição do MDP. Ambos ainda não geram volumes no código atual.

Ver [ajustes metodológicos](methodology-adjustments.md) e [roadmap](roadmap.md).
