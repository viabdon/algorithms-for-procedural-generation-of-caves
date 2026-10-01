# Roadmap atualizado

## Fase 0 — Esqueleto do repositório (concluída)

Criar pacote Python, diretórios, configurações, README, arquivos de dependência e convenções de volume.

## Pré-processamento de referências reais

### Concluído — Implementar limites espaciais incrementais de nuvens de pontos

**Estado:** ``calculate_xyz_bounds`` foi implementada em
``cavegen.datastream.bounds`` e testada em ``tests/test_bounds.py``. Os parsers
``.f32`` e ``.ply`` fornecem os lotes XYZ ``float32`` de forma
``(n_no_lote, 3)`` que ela consome. O leitor PLY suporta payload ASCII por
streaming e payload binário por ``numpy.memmap``.

**Objetivo:** calcular a caixa delimitadora alinhada aos eixos da nuvem sem
carregar todos os pontos na memória:

```text
min_xyz = [menor_x, menor_y, menor_z]
max_xyz = [maior_x, maior_y, maior_z]
```

**Estratégia:** para cada lote, calcular mínimo e máximo locais por coluna e
combiná-los com acumuladores globais por ``numpy.minimum`` e
``numpy.maximum``. A implementação deve manter memória adicional constante,
além do lote atual.

**Cobertura dos dados:** para produzir limites usados na normalização e na
voxelização, a função deve consumir todos os vértices do iterador. Uma amostra
não garante conter os extremos reais e pode reduzir indevidamente a caixa,
causando distorção ou recorte de pontos. Amostras servem apenas para
visualização, estimativas exploratórias ou escolha preliminar de parâmetros;
nunca como limites definitivos da referência.

**Contrato proposto:** uma função genérica, fora dos parsers de formato, deve
receber um iterável de lotes XYZ e retornar ``(min_xyz, max_xyz)`` como dois
arrays ``float32`` de forma ``(3,)``.

**Validações:** rejeitar iterável sem pontos, lotes fora da forma ``(N, 3)`` e
coordenadas ``NaN`` ou infinitas. Eixos degenerados (``min == max``) devem ser
preservados nesta etapa e tratados explicitamente apenas durante a
normalização.

**Verificação:** testar ao menos dois lotes, com número total de pontos que
não seja múltiplo do tamanho do lote, e conferir os seis extremos esperados.

**Inspeção concluída — Elaphes:** o arquivo externo
``/run/media/midnavi/Pablo/TCC/DATA/RAW/elaphes_cave.ply`` é PLY ASCII 1.0,
declara ``94_465_067`` vértices, traz ``vertex`` como primeiro elemento e
inclui as propriedades ``float64 x``, ``float64 y`` e ``float64 z``. As 16
propriedades adicionais são escalares e podem ser ignoradas pelo leitor XYZ.
Um lote real de 2.048 pontos foi lido como ``float32`` com coordenadas finitas.

**Concluído no dataset real:** em 2026-08-30, a função foi executada sobre os
``94_465_067`` vértices do PLY ASCII completo, em lotes de ``65_536`` pontos.
Os limites definitivos ``float32`` são:

```text
min_xyz = [-9.9391, -3.23727, -6.96334]
max_xyz = [73.7245, 12.9577, 69.7809]
```

Os metadados reproduzíveis, incluindo hash SHA-256 da fonte, estão em
``data/params/elaphes_xyz_bounds.json``. Esses limites devem ser usados na
normalização e não alteram a semântica dos pontos como superfície.

### Concluído — Normalizar e voxelizar uma referência PLY em lotes

**Estado:** ``normalize_xyz_to_zyx_indices`` em
``cavegen.core.normalization`` converte lotes ``float32`` de coordenadas XYZ
para índices ZYX válidos, com uma escala compartilhada, padding simétrico e
tratamento explícito de eixos degenerados. ``voxelize_surface_zyx`` em
``cavegen.core.voxelization`` marca os índices em uma grade booleana de
superfície. Ambos possuem testes unitários.

**Integração concluída:** ``cavegen.datastream.reference_preprocessing`` lê os
limites persistidos, transmite os lotes de ``iter_ply_xyz`` pela normalização e
os entrega diretamente ao voxelizador por ``voxelize_ply_surface``. O fluxo não
armazena a nuvem inteira: mantém somente o lote corrente, seus índices e a
grade final. Um teste de integração com PLY ASCII sintético verifica o fluxo.

**Decisão adotada:** uma única escala preserva as proporções espaciais; o espaço
remanescente é dividido como padding ao redor da nuvem. A conversão de XYZ para
ZYX torna o resultado compatível com volumes na forma ``(depth, height, width)``.

**Semântica:** ``True`` na grade retornada significa superfície observada, e não
espaço aberto de caverna. Portanto, essa grade ainda não deve ser usada como um
``Volume3D`` dos geradores nem comparada diretamente por IoU a eles.

**Persistência concluída:** ``cavegen.datastream.surface_io`` salva e carrega
grades de superfície em NPZ comprimido, sem usar ``Volume3D``. O arquivo inclui
metadados de fonte, limites XYZ, resolução e convenção de normalização. O
comando de voxelização exige o caminho de saída para não perder a inspeção.

**Verificação concluída — Elaphes em ``32³``:** o processamento completo dos
``94_465_067`` vértices gerou ``elaphes_surface_32.npz`` com grade booleana
``(32, 32, 32)``. Foram marcados 245 dos 32.768 voxels (0,75%). A estrutura do
arquivo e seus metadados de limites, origem e normalização foram validados após
a escrita.

**Interpretação atual:** a grade `32³` é um artefato diagnóstico de superfície.
Ela não é entrada suficiente para o Screened Poisson nem uma referência de
`VOID`. A próxima rota parte novamente da point cloud contínua e inclui
normais, reconstrução de malha, classificação e SDF/TSDF. Inspeções em
resoluções distintas continuam úteis para sensibilidade, mas não substituem a
validação da malha. As tarefas foram divididas entre
[`Pablo`](tarefas-pablo-reconstrucao-modelos.md) e
[`Felipe`](tarefas-felipe-sdf-ca.md).

## Fase 1 — Baselines clássicos (implementação básica concluída)

Random Walk 3D e Cellular Automata 3D já geram `Volume3D`. O CA básico será
preservado como controle para `CA+SDF` e, depois, `CA+SDF+GA`. Reexecutar esses
baselines após fixar o protocolo final.

## Fase 2 — Reconstrução de malha real

Estimar/orientar normais da point cloud, reconstruir com Screened Poisson e
validar malha, entradas, tampas sintéticas e regiões extrapoladas. Estudar Ball
Pivoting/Alpha Shapes como fallbacks quando os critérios não forem cumpridos.
A malha de Marching Cubes já existente é extraída de volumes gerados e não
substitui esta fase.

## Fase 3 — Interior/exterior, SDF e rótulos

Implementar flood fill e SDF/TSDF primeiro em geometria sintética, em paralelo
à reconstrução do Elaphes. Integrar depois a malha validada. Tratar entradas,
gaps e `UNKNOWN` explicitamente. Persistir campo físico, campo truncado,
`VOID/SURFACE/SOLID/UNKNOWN`, máscara de validade, escala e parâmetros.

## Fase 4 — CA condicionado e otimização genética

Usar um SDF simplificado independente do scan de teste para enviesar o CA;
comparar pesos e regras contra o CA básico. Quando `CA+SDF` estiver estável,
testar um algoritmo genético para otimizar parâmetros sob orçamento controlado,
com treino/validação/teste separados. Relatar custo de busca à parte.

## Fase 5 — Métricas e modelos neurais

Há implementações básicas de IoU, conectividade e morfologia. Adicionar
alinhamento/máscara válida e métricas de superfície antes da avaliação real.
Auditar dados para GAN/TSDF; especificar o MDP do PCGRL e validar ambiente
pequeno antes de PPO. As interfaces neurais atuais ainda não geram volumes.

## Fase 6 — Benchmark principal

Comparar Random Walk, CA, CA+SDF, CA+SDF+GA e modelos neurais quando prontos,
com geração repetida, domínio comum e dispersão. Separar custos de preparação
da referência, otimização por GA, treinamento neural, geração e exportação.
Controlar vazamento entre regiões vizinhas; limitar conclusões quando não
houver cavernas independentes suficientes.

## Fase 7 — Visualização e integração

Unity visualiza arquivos produzidos em Python. Adicionar gRPC somente após o
pipeline científico estar funcional.

## Fase 8 — Portabilidade AMD/ROCm

Executar amostra menor no ambiente AMD/ROCm, se houver tempo, tratando-a como contribuição técnica complementar.
