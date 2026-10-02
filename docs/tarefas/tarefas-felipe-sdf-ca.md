# Tarefas do Felipe — flood fill, SDF e Cellular Automata

**Metas indicativas a partir de 30/09/2026.** Felipe é o responsável principal
pela implementação e pelos testes de flood fill, SDF/TSDF e do CA enviesado
por um campo de controle. O algoritmo genético é a etapa final da evolução do
CA. Pablo prepara e valida a malha Screened Poisson e a semântica da referência;
ver [`tarefas-pablo-reconstrucao-modelos.md`](tarefas-pablo-reconstrucao-modelos.md).

O trabalho começa com geometrias sintéticas e um campo tubular simples.
Assim, a urgência do SDF para o CA não fica bloqueada pelos 94.465.067 pontos
do Elaphes nem pela reconstrução da malha real.

## Até 02/10 — Contrato comum e casos conhecidos

- [ ] Acordar com Pablo shape ZYX, origem, espaçamento físico, sinal
  `SDF < 0 = VOID`, banda `ε` para `SURFACE`, truncamento `τ` para TSDF,
  rótulos `VOID/SURFACE/SOLID/UNKNOWN` e comportamento em células inválidas.
- [ ] Criar fixtures pequenas: cubo/esfera fechados, tubo com entrada, fenda
  acidental, duas componentes e superfície com orientação invertida. Registrar
  interior conhecido para testar sinal e distância.
- [ ] Definir interfaces para receber malha ou barreira voxelizada, tampas
  sintéticas e máscaras de validade; não presumir que o `.npz` de superfície
  direta do Elaphes já delimita uma caverna.

## Até 06/10 — Flood fill e SDF sintético

- [ ] Implementar flood fill exterior a partir das faces da grade sobre uma
  barreira voxelizada, com conectividade explícita. Derivar componentes
  internas candidatas e detectar vazamento por entradas/gaps; exigir ou
  registrar tampas quando necessárias.
- [ ] Calcular distâncias à **malha ou à superfície de referência definida** e
  atribuir o sinal pela classificação interior/exterior. Para malha aberta ou
  região ambígua, marcar `UNKNOWN` em vez de inventar um sinal.
- [ ] Persistir SDF físico `float32`, TSDF truncado/normalizado e rótulos
  derivados com `|SDF| ≤ ε` para `SURFACE`. Testar centro, parede, exterior,
  anisotropia, bordas, fenda e inversão de sinal.
- [ ] Criar um gerador de SDF de controle simples, por exemplo tubo ou
  esqueleto procedural independente de cavernas reais. Este campo já pode
  alimentar o CA antes da malha Poisson.

## Até 10/10 — CA condicionado por campo de controle

- [ ] Preservar `generate_cellular_automata` como baseline e especificar a
  nova regra com influência espacial do SDF/TSDF de controle. Comparar viés
  na probabilidade inicial, no limiar local ou na transição; escolher uma
  formulação mensurável e registrar o peso do campo.
- [ ] Garantir que peso zero reproduz o CA básico sob a mesma seed. Definir
  tratamento de bordas, `UNKNOWN`, shape divergente e `τ`/escala incompatível.
- [ ] Gerar volumes com pesos distintos e medir aderência ao controle,
  conectividade, ocupação, diversidade e tempo. O SDF exato da caverna de
  **teste** não deve ser o controle do experimento principal; se usado, criar
  experimento separado de reconstrução condicionada.

## Até 16/10 — Integrar o Elaphes e validar

- [ ] Receber de Pablo uma malha candidata com orientação, coordenadas,
  entradas, tampas sintéticas e regiões incertas documentadas. Voxelizar a
  barreira no mesmo domínio do SDF e comparar flood fill com testes de
  ocupação da malha ou outro método de classificação quando necessário.
- [ ] Inspecionar o artefato antigo `elaphes_surface_32.npz` apenas como
  diagnóstico; comparar a superfície original e a malha reconstruída em
  resoluções escolhidas após o teste inicial. Registrar extrapolações,
  vazamentos, componentes e sensibilidade a `ε`, `τ` e resolução.
- [ ] Entregar artefatos e relatório reproduzíveis. Células ambíguas devem
  permanecer `UNKNOWN`; qualquer mudança de fechamento ou sinal deve ser
  discutida com Pablo antes de usar a referência em métricas ou aprendizagem.

## Etapa final — Algoritmo genético para otimizar o CA (meta 30/10)

- [ ] Discutir e pesquisar qual será o cromossomo: probabilidade inicial,
  limiar de vizinhos, iterações, peso/escala do SDF, parâmetros do campo de
  controle e, se justificável, regras locais. Fixar limites válidos e custo de
  cada avaliação antes de implementar.
- [ ] Definir aptidão com conectividade, coerência da forma, aderência ao
  **controle independente**, diversidade e custo, evitando que uma métrica
  domine as demais ou que o GA aprenda a resposta da caverna de teste.
- [ ] Comparar estratégia simples de busca e algoritmo genético com orçamento
  equivalente; especificar população, seleção, cruzamento, mutação, elitismo,
  parada e seeds. Se custo ou ganho não justificar GA, registrar a conclusão.
- [ ] Implementar e testar GA só após estabilizar CA+SDF. Comparar CA básico,
  CA+SDF e CA+SDF+GA em dados de validação; reservar teste para avaliação
  final. Reportar separadamente custo de otimização e tempo de geração.

Para cada mudança Python com contrato observável, adicionar testes em
`tests/`; antes de concluir, executar a suíte e uma checagem de importação ou
exemplo pequeno, conforme `AGENTS.md`.
