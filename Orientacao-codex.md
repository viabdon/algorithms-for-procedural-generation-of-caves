# Próximos passos do TCC — benchmark de geradores voxelizados

**Direção definida em 18/10/2026; branch `CA` verificada em 28/10/2026.** O [resumo quinzenal](docs/relatorios/resumo-quinzenal-tcc-2026-10-18.docx) estabelece que a comparação dos geradores volta a partir de matrizes voxelizadas. A reconstrução do Elaphes, o SDF real e a IoU volumétrica não condicionam mais o avanço do TCC. A branch `CA` avançou no CA com peso, recursos e protótipos geométricos; esses avanços ainda não estão integrados ao `main`.

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
| Protocolo, avaliação estrutural, relato e frente neural | Pablo | Configurações comparáveis e definições de métricas; auditoria dos dados da GAN e MDP pequeno do PCGRL |
| CA básico, reprodução e extensões de controle | Felipe | Integrar a API do CA da branch ao benchmark, reproduzir o baseline no protocolo comum e validar guia procedural |
| Benchmark clássico e interpretação | Ambos | Random Walk e CA executados no mesmo protocolo, CSVs conferidos e dispersão documentada |

Ver [tarefas de Pablo](docs/tarefas-pablo-reconstrucao-modelos.md) e [tarefas de Felipe](docs/tarefas-felipe-sdf-ca.md).

## Ordem de trabalho

1. Integrar a API do CA da branch `CA` ao benchmark, fechar o protocolo clássico e reexecutar Random Walk e CA básico. A branch traz contagem de vizinhos vetorizada, menu, resultados NPZ e amostragem de CPU/RSS e GPU/VRAM quando disponível; seus 53 testes passaram, mas a importação do benchmark falha pelo nome antigo `generate_cellular_automata`. Resultados finais comparáveis ainda precisam ser coletados.
2. Definir avaliação estrutural com conectividade, componentes e ocupação. Declarar resolução e unidade da transformada de distância; ramificação, tortuosidade e diversidade só entram após definição e validação. Completar CPU/GPU/VRAM se fizerem parte do protocolo.
3. Auditar dados para GAN e definir ambiente PCGRL pequeno, com recompensa de conectividade e ocupação. As interfaces atuais ainda não geram volumes. Dados sintéticos testam infraestrutura, sem demonstrar aprendizado de cavernas reais.
4. Definir otimização genética dos parâmetros de CA e Random Walk, com espaços de busca, aptidão, orçamento e sementes de avaliação reservadas. Comparar com busca simples de mesmo orçamento; separar custo de busca e tempo de geração. O peso espacial do CA já foi prototipado e peso zero reproduz o CA básico. Um guia procedural independente do scan de teste permanece extensão distinta; seu SDF deve seguir o contrato positivo no vazio. O SDF experimental do Elaphes classifica parede, não vazio real.
5. Inspecionar em Unity os volumes e malhas gerados. gRPC e portabilidade ROCm permanecem posteriores.

## Delimitação da referência real

Os pontos do Elaphes representam parede observada. A grade diagnóstica `32³` contém 245 voxels de superfície; o complemento mistura interior, exterior e áreas não observadas. As malhas experimentais não forneceram um interior validado: houve bordas, defeitos topológicos, auto-interseções ou extrapolação. A linha central serviu à inspeção, mas não estabeleceu o sinal do SDF. Não calcular IoU volumétrica contra o scan nem apresentar ocupação ou largura do vazio real como medidas observadas. Inspeção qualitativa e eventual comparação de superfície alinhada e toleranciada podem ser relatadas com limites explícitos.

Mudanças Python com contrato observável exigem testes em `tests/`; antes de concluí-las, executar a suíte e uma importação ou exemplo pertinente, conforme `AGENTS.md`.
