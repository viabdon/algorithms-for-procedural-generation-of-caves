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

Para uma caverna voxelizada com interior conhecido, o SDF é um campo `float32[D,H,W]` na mesma grade ZYX do volume. O sinal é **positivo no interior do vazio da caverna**, **negativo no exterior sólido** e **zero nos voxels classificados como borda**. A magnitude é a distância euclidiana até o voxel de borda mais próximo, expressa em **voxels**; o zero fica no centro do voxel de borda. O protótipo de `random_walk_temp/` classifica como borda o voxel vazio que toca sólido por uma das seis faces, tratando fora da grade como sólido. Guardar a convenção de sinal, a regra de borda, os eixos e a unidade nos metadados.

Este é o contrato escolhido para novos campos sintéticos; não afirma que já exista uma API pública de SDF integrada ao pacote `cavegen`. Se um futuro campo usar espaçamento físico ou outra regra de borda, a conversão e os metadados precisarão ser explícitos.

## Contratos e implementação no `main`

| Etapa | Contrato | Estado |
| --- | --- | --- |
| Random Walk e CA básico | `Volume3D` booleano em ZYX | Implementados |
| Persistência | Volume gerado em NPZ | Implementada |
| Benchmark inicial | Tempo, pico de RSS, proporção de vazio, fração da maior componente e estatísticas de distância ao sólido | Implementado para os dois geradores; reexecução comparável e resultados finais pendentes |
| Marching Cubes | Malha derivada do volume gerado | Disponível para visualização |
| GAN e PCGRL | Devem gerar `Volume3D` | Interfaces ainda lançam `NotImplementedError` |
| CPU/GPU/VRAM e descritores adicionais | Protocolo e instrumentação | Pendentes no `main`; há protótipo de rastreamento na branch `CA` |

A transformada de distância descreve o espaço livre em unidades da grade atual. Seus resumos não validam, por si sós, a largura de todos os túneis. Resolução, espaçamento e bordas precisam ser explicitados para interpretações físicas.

## Código experimental na branch `CA` (`a58155e`)

O CA foi reorganizado em um pacote com convolução 3D para contar a vizinhança, bordas configuráveis, sementes/resultados NPZ, menu e pesos espaciais opcionais. O peso é somado à contagem antes do limiar em cada passo. Testes da branch verificam equivalência com a versão em laço nas bordas determinísticas e igualdade entre CA sem peso e com peso zero. A borda aleatória não é reproduzível bit a bit.

O rastreador novo amostra tempo, CPU e RSS do processo, além de GPU/VRAM quando houver leitura; resultados ausentes não devem ser interpretados como zero. O benchmark da branch foi adaptado para esse rastreador, mas ainda importa `generate_cellular_automata`, nome ausente no novo pacote. Em revisão isolada, 53 testes passaram e a importação do benchmark falhou. Integrar a API e executar um caso pequeno são pré-requisitos para usar a branch no benchmark principal.

`random_walk_temp/` contém um porte experimental de caminhada ponderada por waypoints, voxelização tubular e campo de distância; não substitui o gerador público de Random Walk. Os waypoints vêm de modelos de cavernas reais do projeto base, portanto o guia não é independente dessa informação. O raio padrão de 1,5 voxel em `64³` engrossa os tubos em relação à escala original.

## Referência real como frente exploratória

O PLY do Elaphes contém pontos de parede observada. A grade diagnóstica `32³` marca 245 voxels de superfície em 32.768 células. Ela não representa ar; seu complemento mistura interior, exterior e regiões não observadas. Portanto, a grade não é uma referência para IoU com os volumes gerados.

Os experimentos de amostragem, Screened Poisson, linha central, orientação de normais e espessamento estão preservados na branch `experiment/elaphes-meshing` e em artefatos locais. Nenhuma malha avaliada validou conjuntamente fechamento, ausência de auto-interseções, conectividade e aderência à nuvem. Não há classificação interior/exterior nem SDF real confiável para o benchmark. A conclusão vale para os testes feitos no Elaphes, sem demonstrar impossibilidade geral. Ball Pivoting, Alpha Shapes, winding numbers e fechos controlados permanecem hipóteses sem comparação concluída nesse conjunto.

Na branch `CA`, `sdf_temp/` calcula flood fill e distância euclidiana à borda da grade de superfície `64³`. O campo também usa interior positivo, exterior negativo e distância em voxels, mas seu "interno" pode ser espessura de parede ou buracos fechados; entradas abertas tornam o ar do túnel alcançável pelo exterior. Compartilhar sinal e unidade com o contrato sintético não torna as classes semanticamente equivalentes. O campo serve ao ensaio de peso espacial, mas não valida `VOID` real, distância física ou IoU volumétrica.

O scan pode apoiar inspeção qualitativa e propriedades efetivamente observáveis. Métricas de superfície exigiriam regiões alinhadas e comparáveis, tolerância e distinção entre parede medida e geometria extrapolada. IoU de superfície não substitui automaticamente IoU volumétrica.

## Extensões

Uma variante de CA com peso espacial já existe na branch `CA`. O ensaio com o campo do Elaphes demonstra o efeito do peso na regra, sem fornecer avaliação de semelhança volumétrica real. A extensão guiada requer campo procedural com semântica e unidade documentadas, independente do scan de teste. Peso zero já foi verificado contra o CA básico; ainda falta comparar resultados sob protocolo comum. Está planejado ajustar geneticamente parâmetros de CA e Random Walk, com orçamento e sementes de avaliação reservadas, custo de busca separado e controle por busca simples de mesmo orçamento.

Uma GAN requer volumes de treino com semântica válida; dados sintéticos verificam a infraestrutura, mas não sustentam alegação de aprendizagem de cavernas reais. PCGRL deve começar com ambiente pequeno e recompensa de conectividade e ocupação, após definição do MDP. Ambos ainda não geram volumes no código atual.

Ver [ajustes metodológicos](methodology-adjustments.md) e [roadmap](roadmap.md).
