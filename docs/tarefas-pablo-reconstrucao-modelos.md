# Tarefas do Pablo — protocolo, avaliação e modelos neurais

**Replanejamento de 18/10/2026.** A frente de reconstrução do Elaphes passa ao registro histórico e não bloqueia o TCC. O foco é fechar a comparação de geradores voxelizados. Ver o [resumo quinzenal](relatorios/resumo-quinzenal-tcc-2026-10-18.docx), o [roadmap](roadmap.md) e as [tarefas de Felipe](tarefas-felipe-sdf-ca.md).

## Divisão de trabalho deste plano

Pablo conduz o **protocolo comparativo**, a configuração e o ajuste de parâmetros do **Random Walk**, a definição das métricas, a análise estatística, o texto do TCC e a frente GAN/PCGRL. Felipe conduz a implementação e o ajuste do **CA**, incluindo o peso espacial e a instrumentação iniciada na branch `CA`. Os dois fecham juntos orçamento, sementes, hardware e interpretação dos resultados. Essa divisão organiza as próximas entregas; não afirma que os experimentos já foram executados.

## Já disponível e limites conhecidos

- [x] Leitura incremental do PLY/F32, limites, normalização XYZ→ZYX e voxelização diagnóstica. Os 245 voxels marcados em `32³` são parede observada, não ar.
- [x] Ensaios de amostragem, Screened Poisson, linha central, orientação de normais e espessamento documentados na branch `experiment/elaphes-meshing` e em artefatos locais. Nenhuma malha examinada validou o volume interno real.
- [x] Random Walk e CA básico geram `Volume3D`; GAN e PCGRL ainda são interfaces sem geração funcional no `main`.
- [x] Na branch `CA`, Felipe prototipou CA vetorizado com peso espacial, amostragem de recursos, flood fill/EDT da grade de parede do Elaphes e uma caminhada ponderada por waypoints. Esses resultados não validam o interior real nem estão integrados ao benchmark do `main`.

## Prioridade imediata — protocolo e baselines

- [x] Registrar a configuração inicial `baseline_32.yaml`: volume ZYX `32³`, sementes `0` a `4` e parâmetros dos dois geradores clássicos.
- [x] Acordar `64³` em ZYX como grade das medições finais. `baseline_32.yaml` é configuração inicial, não o protocolo final.
- [ ] Fixar com Felipe sementes, repetições de medição, orçamento de ajuste, hardware e versões. A escala física do voxel só será declarada se houver conversão conhecida.
- [ ] Criar a configuração final `64³` em ZYX, separada de `baseline_32.yaml`. Registrar parâmetros fixos de cada gerador e a origem de cada configuração no CSV/NPZ.
- [ ] Definir o espaço de busca do **Random Walk** (por exemplo, passos e raio, conforme o gerador escolhido), limites válidos e função de aptidão com métricas estruturais. Definir com Felipe os critérios comuns usados também no CA, sem exigir parâmetros idênticos entre algoritmos.
- [ ] Reservar sementes distintas para ajuste e avaliação final. Fixar número de sementes por candidato, total de avaliações do GA, critério de parada e controle por busca simples. Registrar **número de avaliações e tempo total**: igual contagem de candidatos não garante igual tempo entre geradores.
- [ ] Conferir com Felipe a integração da nova API do CA ao benchmark. Em `a58155e`, 53 testes passaram, mas a importação do benchmark falhou porque `generate_cellular_automata` não é exportado pelo pacote reorganizado.
- [ ] Reexecutar o Random Walk básico e, depois do ajuste, sua versão com parâmetros escolhidos. Conferir NPZ e CSV, registrar dispersão por semente e manter os mesmos critérios de avaliação do CA.
- [ ] Interpretar tempo de geração, pico de RSS, proporção de vazio e fração da maior componente. Especificar contagem de componentes e casos degenerados antes do relato.
- [ ] Explicitar que as estatísticas atuais da transformada de distância são descritores do espaço livre em unidades da grade, e não largura validada de todos os túneis.
- [x] Definir o contrato público do SDF sintético: positivo no interior do vazio gerado, negativo no exterior sólido, zero na borda e distância euclidiana em voxels, na grade ZYX.
- [ ] Separar no relato o SDF experimental da **parede** do Elaphes do SDF de um vazio gerado. Os dois compartilham sinal e unidade, mas não a semântica do interior; a IoU 0,49 do diário é diagnóstica, sem `VOID` real validado. O guia por waypoints do projeto base também incorpora referência a cavernas reais.

## Avaliação e escrita

- [ ] Definir medidas de conectividade, ocupação e componentes, e validar como serão agregadas entre sementes. Definir ramificação, tortuosidade e diversidade antes de usá-las.
- [ ] Atualizar o texto do TCC: retirar IoU volumétrica contra o Elaphes da avaliação atual, registrar o limite de não haver `VOID` real validado e separar resultados confirmados de hipóteses.

### Orçamento e repetições a fechar com Felipe

- [ ] Definir quantas sementes independentes geram os volumes finais e quantas repetições de tempo medem a variação da máquina. Não tratar várias medições da **mesma** seed como diversidade geométrica.
- [ ] Fixar o mesmo orçamento de busca para GA e busca simples dentro de cada algoritmo; registrar avaliações realizadas, tempo total e eventuais execuções interrompidas. Relatar o custo de ajuste separado do custo de gerar um volume com parâmetros já fixados.
- [ ] Definir critério de seleção de candidatos antes de olhar as sementes reservadas. Aplicar a mesma regra de seleção e o mesmo conjunto de métricas a CA e Random Walk.

### Hardware e apresentação dos custos

- [ ] Registrar máquina, CPU, memória, threads, GPU quando usada, backend, versão de software e ambiente (local/Colab) por execução. A branch `CA` já amostra CPU/RSS e GPU/VRAM quando disponíveis; ausência de leitura não equivale a consumo zero.
- [ ] Separar tabelas de **qualidade estrutural** dos volumes `64³` e de **custo por ambiente**. CA e Random Walk podem rodar na CPU, enquanto GAN/PCGRL podem usar GPU no Colab. Não ordenar tempos de CPU local e GPU do Colab como se fossem o mesmo hardware.
- [ ] Medir separadamente ajuste genético, treino neural, geração/inferência e exportação/visualização. Portar CA para GPU só se a pergunta experimental incluir aceleração por GPU; nesse caso, conferir equivalência e medir também transferências e sincronização.

## Frente neural após o benchmark clássico

- [ ] Auditar a quantidade, independência e semântica dos volumes de treino antes de escolher GAN. Dados sintéticos podem testar infraestrutura, sem alegação de aprendizado de cavernas reais.
- [ ] Definir o MDP do PCGRL: estado, ações, transição, recompensa, término e orçamento. Começar em grade pequena, com conectividade e ocupação; não usar IoU com o scan.
- [ ] Planejar geração funcional de GAN e PCGRL sob o mesmo contrato `Volume3D` e comparação com os baselines, separando treino de inferência.

## Registro da reconstrução

Preservar código, parâmetros, métricas e figuras dos ensaios do Elaphes. O espessamento bruto produziu malhas sem arestas de borda, mas com auto-interseções; não há referência interior validada nem SDF assinado confiável. Ball Pivoting, Alpha Shapes, winding numbers e fechos controlados podem ser estudados futuramente, sem tratá-los como soluções já comparadas. O rollback é de escopo, não de histórico.
