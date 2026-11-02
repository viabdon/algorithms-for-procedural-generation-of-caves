# Próximos passos do TCC — benchmark de geradores voxelizados

**Direção definida em 18/10/2026; responsabilidades atualizadas em 02/11/2026.** O [resumo quinzenal](docs/relatorios/resumo-quinzenal-tcc-2026-10-18.docx) estabelece que a comparação dos geradores volta a partir de matrizes voxelizadas. A reconstrução do Elaphes, o SDF real e a IoU volumétrica não condicionam mais o avanço do TCC. A branch `CA` avançou no CA com peso, recursos e protótipos geométricos; Felipe também iniciou a frente de Random Walk. Esses avanços ainda não estão integrados ao `main`.

## Contrato comum

```text
gerador -> Volume3D booleano em ZYX -> NPZ -> métricas e CSV em Python
        -> malha opcional por Marching Cubes -> Unity
```

`True` significa ar; `False`, sólido. As medições finais usarão `64³` em ZYX. Cada comparação deve declarar parâmetros, sementes, repetições, hardware e orçamento; escala física só deve ser atribuída aos voxels se houver conversão conhecida. Marching Cubes visualiza volumes gerados e não reconstrói a point cloud.

O contrato para SDF **sintético de volume gerado** é positivo no interior do vazio, negativo no exterior sólido e zero na borda, com distância euclidiana em voxels ao voxel de borda mais próximo, na mesma grade ZYX. Registrar a regra de borda e a origem. O protótipo de `random_walk_temp/` já segue sinal e unidade; o campo de parede do Elaphes usa números semelhantes, sem validar a mesma classe de interior.

## Responsabilidades atuais

| Frente | Responsável principal | Próxima entrega verificável |
| --- | --- | --- |
| Métricas e protocolo de medição | Pablo | API e esquema padronizados para métricas estruturais e de custo, com validações e testes |
| Modelos neurais | Pablo | GAN e PCGRL funcionais sob o contrato `Volume3D`, com treino separado de geração |
| Parsing de novas cavernas | Pablo | Inventário e leitura incremental dos formatos disponíveis no volume `D:`, após o fim da descompactação |
| CA, Random Walk e extensões de controle | Felipe | Integrar os geradores ao protocolo comum e produzir volumes rastreáveis para avaliação |
| Algoritmo evolutivo para CA e Random Walk | Felipe | Espaços de busca, aptidão e orçamento definidos sobre a interface de métricas padronizada |
| Fechamento do protocolo e interpretação | Ambos | Sementes, orçamento e hardware acordados; CSVs conferidos e dispersão documentada |

Ver [tarefas de Pablo](docs/tarefas-pablo-reconstrucao-modelos.md) e [tarefas de Felipe](docs/tarefas-felipe-sdf-ca.md).

## Ordem de trabalho

1. Pablo implementa e padroniza a coleta de métricas. A primeira entrega deve fixar contratos de entrada e saída, conectividade, componentes, ocupação, transformada de distância e medidas de custo, com tratamento explícito de volumes degenerados, resolução, unidade, sementes, repetições e hardware. Essa interface é pré-requisito direto para comparar geradores e para a função de aptidão evolutiva.
2. Com o contrato de métricas estável, Pablo implementa as redes neurais de geração. A GAN exige auditoria dos volumes de treino; o PCGRL exige um MDP pequeno. Ambos devem retornar `Volume3D` e separar treino de geração/inferência. Não é necessário esperar o encerramento de todos os experimentos clássicos para iniciar essa infraestrutura.
3. Pablo inventaria e implementa o parsing das novas cavernas. As point clouds locais devem ser lidas preferencialmente no volume externo `D:`, sem cópia para o repositório. Três das 16 cavernas obtidas a partir da fonte associada ao KarstConduitCatalogue ainda estão em descompactação e não devem ser tratadas como entradas disponíveis. O formato e o caminho exato de cada conjunto precisam ser verificados antes de escolher ou estender um parser.
4. Em paralelo, Felipe continua o CA e o Random Walk, integra os dois ao contrato comum e, quando a interface de métricas estiver disponível, implementa o algoritmo evolutivo para ajustar seus parâmetros. Espaços de busca, aptidão, orçamento e sementes reservadas devem ser documentados; comparar com busca simples de mesmo orçamento e separar custo de busca do tempo de geração.
5. A padronização ampla da documentação e a redação consolidada dos resultados ocorrem somente ao fim do experimento. Durante a execução, manter apenas registros mínimos de configuração, proveniência, decisões metodológicas e mudanças de contrato necessários à reprodutibilidade.
6. Inspecionar em Unity os volumes e malhas gerados. gRPC e portabilidade ROCm permanecem posteriores.

## Dados externos locais

O volume `D:` é a fonte local preferencial para point clouds e outros dados grandes de cavernas. Não mover esses arquivos para `data/` apenas para executar o pipeline e não versionar caminhos absolutos específicos sem uma opção configurável. Como há extrações longas em andamento, conferir se cada arquivo terminou de ser descompactado antes de ler, calcular hash ou validar tamanho. O parsing continua incremental, preserva `float32` e distingue superfície observada de volume de vazio.

## Delimitação da referência real

Os pontos do Elaphes representam parede observada. A grade diagnóstica `32³` contém 245 voxels de superfície; o complemento mistura interior, exterior e áreas não observadas. As malhas experimentais não forneceram um interior validado: houve bordas, defeitos topológicos, auto-interseções ou extrapolação. A linha central serviu à inspeção, mas não estabeleceu o sinal do SDF. Não calcular IoU volumétrica contra o scan nem apresentar ocupação ou largura do vazio real como medidas observadas. Inspeção qualitativa e eventual comparação de superfície alinhada e toleranciada podem ser relatadas com limites explícitos.

Mudanças Python com contrato observável exigem testes em `tests/`; antes de concluí-las, executar a suíte e uma importação ou exemplo pertinente, conforme `AGENTS.md`.
