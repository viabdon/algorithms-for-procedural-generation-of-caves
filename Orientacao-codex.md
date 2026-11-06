# Próximos passos do TCC — benchmark de geradores voxelizados

**Direção definida em 18/10/2026; responsabilidades atualizadas em 02/11/2026.** O [resumo quinzenal](docs/relatorios/resumo-quinzenal-tcc-2026-10-18.docx) estabelece que a comparação dos geradores volta a partir de matrizes voxelizadas. A reconstrução do Elaphes, o SDF real e a IoU volumétrica não condicionam mais o avanço do TCC. A branch `CA` avançou no CA com peso, recursos e protótipos geométricos; Felipe também iniciou a frente de Random Walk. Esses avanços foram integrados à `main`; a conexão do CA ao benchmark permanece pendente.

## Contrato comum

```text
gerador -> Volume3D booleano em ZYX -> NPZ -> métricas e CSV em Python
        -> malha opcional por Marching Cubes -> Unity
```

`True` significa ar; `False`, sólido. As medições finais usarão `64³` em ZYX. Cada comparação deve declarar parâmetros, sementes, repetições, hardware e orçamento; escala física só deve ser atribuída aos voxels se houver conversão conhecida. Marching Cubes visualiza volumes gerados e não reconstrói a point cloud.

O contrato para SDF **sintético de volume gerado** é positivo no interior do vazio, negativo no exterior sólido e zero na borda, com distância euclidiana em voxels ao voxel de borda mais próximo, na mesma grade ZYX. Registrar a regra de borda e a origem. O protótipo de SDF do Random Walk seguia sinal e unidade, mas não foi migrado para o pacote e está só no histórico (`a58155e`); o campo de parede do Elaphes usa números semelhantes, sem validar a mesma classe de interior.

**Random Walk (02/11/2026, branch `CA`, commits `216f38d` a `e121f44`).** O gerador de Random Walk passou a ser o random walk ponderado por waypoints do projeto base 3D-Cave-Generation, em `src/cavegen/generators/random_walk/`, com os grafos em `configs/random_walk/`. O random walk de 6 direções (`steps`, `brush_radius`) foi apagado, assim como `random_walk_temp/`. Ver [Random Walk](docs/random-walk.md).

## Responsabilidades e ordem de trabalho — 06/11/2026

Felipe está finalizando CA e Random Walk; em seguida conduz a coleta de métricas
e a tabela comparativa. Pablo inicia em paralelo GAN, PCGRL e PCGARL. Ambos
acordam o protocolo de avaliação, sementes, hardware e versão do esquema.

1. Felipe integra a API do CA ao benchmark e confere uma execução pequena; o
   import falha na versão integrada `a7dd1e7`.
2. A dupla usa as métricas `structural-v1` existentes e completa o contrato de
   custo e metadados para consolidar registros brutos e sumários por condição.
3. Pablo especifica MDP e recompensa de RL, audita dados e limites da GAN e
   confirma a abordagem adversarial. Ver [plano neural](docs/plano-redes-neurais.md).
4. Busca evolutiva dos clássicos, parsing adicional e Unity seguem conforme
   disponibilidade e prioridade, com orçamento e sementes documentados.

Ver [tarefas de Pablo](docs/tarefas-pablo-reconstrucao-modelos.md),
[tarefas de Felipe](docs/tarefas-felipe-sdf-ca.md) e [roadmap](docs/roadmap.md).

## Delimitação da referência real

Os pontos do Elaphes representam parede observada. A grade diagnóstica `32³` contém 245 voxels de superfície; o complemento mistura interior, exterior e áreas não observadas. As malhas experimentais não forneceram um interior validado: houve bordas, defeitos topológicos, auto-interseções ou extrapolação. A linha central serviu à inspeção, mas não estabeleceu o sinal do SDF. Não calcular IoU volumétrica contra o scan nem apresentar ocupação ou largura do vazio real como medidas observadas. Inspeção qualitativa e eventual comparação de superfície alinhada e toleranciada podem ser relatadas com limites explícitos.

Mudanças Python com contrato observável exigem testes em `tests/`; antes de concluí-las, executar a suíte e uma importação ou exemplo pertinente.
