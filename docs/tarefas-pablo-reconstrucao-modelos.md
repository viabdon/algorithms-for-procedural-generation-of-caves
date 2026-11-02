# Tarefas do Pablo — métricas, modelos neurais e parsing

**Responsabilidades atualizadas em 02/11/2026.** A frente de reconstrução do Elaphes permanece como registro histórico e não bloqueia o TCC. Pablo prioriza a coleta padronizada de métricas, depois os geradores neurais e, em terceiro, o parsing das novas cavernas. Ver o [resumo quinzenal](relatorios/resumo-quinzenal-tcc-2026-10-18.docx), o [roadmap](roadmap.md) e as [tarefas de Felipe](tarefas-felipe-sdf-ca.md).

## Divisão de trabalho deste plano

Pablo conduz a **implementação e a padronização das métricas**, a análise estatística, a frente GAN/PCGRL e o parsing incremental das novas cavernas. Felipe conduz **CA e Random Walk** e, depois, o algoritmo evolutivo usado para ajustar os dois geradores. Os dois fecham juntos orçamento, sementes, hardware e interpretação dos resultados. A padronização ampla da documentação fica para o fim do experimento; registros mínimos de proveniência, configuração e decisões de contrato continuam obrigatórios durante a execução.

## Já disponível e limites conhecidos

- [x] Leitura incremental do PLY/F32, limites, normalização XYZ→ZYX e voxelização diagnóstica. Os 245 voxels marcados em `32³` são parede observada, não ar.
- [x] Ensaios de amostragem, Screened Poisson, linha central, orientação de normais e espessamento documentados na branch `experiment/elaphes-meshing` e em artefatos locais. Nenhuma malha examinada validou o volume interno real.
- [x] Random Walk e CA básico geram `Volume3D`; GAN e PCGRL ainda são interfaces sem geração funcional no `main`.
- [x] Na branch `CA`, Felipe prototipou CA vetorizado com peso espacial, amostragem de recursos, flood fill/EDT da grade de parede do Elaphes e uma caminhada ponderada por waypoints. Esses resultados não validam o interior real nem estão integrados ao benchmark do `main`.

## Prioridade 1 — coleta e padronização de métricas

- [x] Registrar a configuração inicial `baseline_32.yaml`: volume ZYX `32³`, sementes `0` a `4` e parâmetros dos dois geradores clássicos.
- [x] Acordar `64³` em ZYX como grade das medições finais. `baseline_32.yaml` é configuração inicial, não o protocolo final.
- [ ] Inventariar as funções atuais de tempo, RSS, ocupação, conectividade e transformada de distância, incluindo contratos, unidades e comportamento em entradas degeneradas.
- [x] Implementar `evaluate_structure(Volume3D)` com resultado imutável; funções individuais exigem `bool[D,H,W]` validado.
- [x] Definir e validar conectividade, contagem de componentes, fração na maior componente, ocupação e EDT, com testes independentes.
- [ ] Especificar ramificação, tortuosidade e diversidade; reaproveitar a análise de grafos da linha central após validar a extração dos volumes gerados.
- [x] Explicitar unidades, regra de borda e limites interpretativos da EDT em [métricas estruturais](metricas-estruturais.md).
- [ ] Padronizar a coleta de tempo, CPU, RSS e, quando disponível, GPU/VRAM. Separar geração, busca evolutiva, treino, inferência, transferências e visualização; leitura ausente de GPU não equivale a zero.
- [x] Definir tratamento de volumes vazios, totalmente abertos, desconectados, com dtype ou shape inválido, e cobrir os contratos públicos com testes.
- [ ] Fixar o esquema de CSV e os metadados de eixos, resolução, seed, repetição, parâmetros, hardware, backend e versões. A escala física do voxel só será declarada quando houver conversão conhecida.
- [ ] Entregar a Felipe a interface estável de métricas para integração com CA, Random Walk e a função de aptidão evolutiva.
- [x] Definir o contrato público do SDF sintético: positivo no interior do vazio gerado, negativo no exterior sólido, zero na borda e distância euclidiana em voxels, na grade ZYX.
- [ ] Separar no relato o SDF experimental da **parede** do Elaphes do SDF de um vazio gerado. Os dois compartilham sinal e unidade, mas não a semântica do interior; a IoU 0,49 do diário é diagnóstica, sem `VOID` real validado. O guia por waypoints do projeto base também incorpora referência a cavernas reais.

## Protocolo compartilhado com Felipe

- [ ] Fixar com Felipe sementes independentes, repetições de medição, orçamento de busca, hardware e versões. Não tratar várias medições da mesma seed como diversidade geométrica.
- [ ] Definir como as métricas serão agregadas entre sementes e como casos inválidos entram na análise.
- [ ] Validar o esquema com saídas pequenas de CA e Random Walk antes da coleta final.
- [ ] Ajudar a fixar a aptidão e o critério de seleção antes de examinar sementes reservadas, sem assumir a implementação do algoritmo evolutivo.

### Hardware e apresentação dos custos

- [ ] Registrar máquina, CPU, memória, threads, GPU quando usada, backend, versão de software e ambiente (local/Colab) por execução. A branch `CA` já amostra CPU/RSS e GPU/VRAM quando disponíveis; ausência de leitura não equivale a consumo zero.
- [ ] Separar tabelas de **qualidade estrutural** dos volumes `64³` e de **custo por ambiente**. CA e Random Walk podem rodar na CPU, enquanto GAN/PCGRL podem usar GPU no Colab. Não ordenar tempos de CPU local e GPU do Colab como se fossem o mesmo hardware.
- [ ] Medir separadamente ajuste genético, treino neural, geração/inferência e exportação/visualização. Portar CA para GPU só se a pergunta experimental incluir aceleração por GPU; nesse caso, conferir equivalência e medir também transferências e sincronização.

## Prioridade 2 — geradores neurais

- [ ] Auditar a quantidade, independência e semântica dos volumes de treino antes de escolher GAN. Dados sintéticos podem testar infraestrutura, sem alegação de aprendizado de cavernas reais.
- [ ] Definir o MDP do PCGRL: estado, ações, transição, recompensa, término e orçamento. Começar em grade pequena, com conectividade e ocupação; não usar IoU com o scan.
- [ ] Implementar geração funcional de GAN e PCGRL sob o mesmo contrato `Volume3D` e comparação com os baselines, separando treino de inferência.
- [ ] Reutilizar a interface de métricas da prioridade 1; no PCGRL, selecionar para recompensa apenas medidas bem definidas e com custo adequado por passo.

Esta frente pode começar quando o contrato de métricas estiver estável; não depende do encerramento de toda a coleta dos geradores clássicos.

## Prioridade 3 — parsing das novas cavernas

- [ ] Usar o volume externo `D:` como origem preferencial das point clouds. Não copiar arquivos grandes para o repositório apenas para processá-los.
- [ ] Aguardar a conclusão da descompactação das três cavernas em andamento antes de calcular tamanho, hash, limites ou validar conteúdo.
- [ ] Inventariar nomes, caminhos, formatos, tamanhos, sistemas de eixos e unidades quando conhecidas. Registrar quais entradas pertencem ao conjunto de 16 associado à fonte do KarstConduitCatalogue.
- [ ] Reutilizar `iter_ply_xyz` e `iter_f32_xyz` quando os formatos forem compatíveis; criar parser novo somente após validar o formato real.
- [ ] Manter leitura incremental, `numpy.memmap` quando aplicável, coordenadas `float32`, mensagens de erro com o arquivo e testes sintéticos pequenos.
- [ ] Tratar cada point cloud como superfície observada até existir uma conversão metodologicamente documentada para outra representação.

O caminho exato dentro de `D:` ainda não foi fixado na documentação e deve ser confirmado quando os arquivos estiverem prontos. Essa confirmação é um pré-requisito operacional direto, sem mudar a divisão de responsabilidades.

## Padronização documental ao fim do experimento

- [ ] Após a coleta e a análise, consolidar o texto do TCC, contratos, tabelas, limitações, comandos e resultados confirmados.
- [ ] Registrar então, de forma uniforme, a retirada da IoU volumétrica contra o Elaphes e o limite de não haver `VOID` real validado.

Durante o experimento, atualizar somente registros necessários para reprodução, proveniência e mudanças de contrato. Evitar uma revisão editorial ampla antes de os resultados se estabilizarem.

## Registro da reconstrução

Preservar código, parâmetros, métricas e figuras dos ensaios do Elaphes. O espessamento bruto produziu malhas sem arestas de borda, mas com auto-interseções; não há referência interior validada nem SDF assinado confiável. Ball Pivoting, Alpha Shapes, winding numbers e fechos controlados podem ser estudados futuramente, sem tratá-los como soluções já comparadas. O rollback é de escopo, não de histórico.
