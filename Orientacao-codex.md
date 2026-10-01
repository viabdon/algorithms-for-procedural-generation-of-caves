# Próximos passos do TCC — reconstrução, campos de distância e geração

**Estado em 30/09/2026.** Os leitores PLY/F32, limites XYZ do Elaphes,
voxelização direta de superfície em `32³`, `Volume3D`, Random Walk, Cellular
Automata básico e algumas métricas já existem. Ainda não há reconstrução de
malha a partir da point cloud, classificação interior/exterior, SDF/TSDF,
CA condicionado, GAN ou PCGRL funcional. A grade `elaphes_surface_32.npz`
contém 245 células com pontos observados; ela é um diagnóstico, não a referência
volumétrica final.

## Caminho metodológico adotado

```text
point cloud -> normais estimadas/orientadas -> Screened Poisson (principal)
            -> malha validada e aproximadamente watertight
            -> entradas tratadas e interior/exterior classificados
            -> SDF em grade -> TSDF para aprendizagem/controle
            -> VOID / SURFACE / SOLID / UNKNOWN
```

Ball Pivoting e Alpha Shapes são candidatos de fallback da **reconstrução de
malha**, caso o Poisson não produza uma geometria aceitável. Flood fill é uma
implementação da **classificação**; consultas de ocupação ou winding numbers
podem servir de comparação/fallback. O sinal do SDF depende da classificação:
`SDF < 0` para `VOID`, `SDF > 0` para `SOLID/EXTERIOR`; uma banda `|SDF| ≤ ε`
define `SURFACE`, e regiões sem evidência recebem `UNKNOWN`/máscara inválida.
SDF e rótulos categóricos são artefatos distintos. Ver
[`docs/architecture.md`](docs/architecture.md) e
[`docs/methodology-adjustments.md`](docs/methodology-adjustments.md).

## Responsabilidades e dependências

| Frente | Responsável principal | Entrega que libera a outra frente |
| --- | --- | --- |
| Preparação da point cloud, normais, Screened Poisson, fallback e validação da malha | Pablo | Malha com coordenadas, orientação, entradas/tampas e proveniência documentadas |
| Contrato semântico dos quatro rótulos, política de `UNKNOWN`, avaliação, GAN e PCGRL | Pablo | Especificação de sinal, grade, máscara de validade e protocolo de treino/teste |
| Flood fill interior/exterior, SDF/TSDF em grade e testes geométricos | Felipe | Campo assinado e rótulos verificáveis, integráveis à malha validada |
| CA com viés espacial por SDF de controle | Felipe | Baseline condicionado reproduzível, separado do CA original |
| Algoritmo genético para otimizar o CA, após CA+SDF | Felipe | Comparação sob orçamento de busca e teste reservado |

As listas executáveis e metas indicativas estão em
[`tarefas-pablo-reconstrucao-modelos.md`](docs/tarefas-pablo-reconstrucao-modelos.md)
e [`tarefas-felipe-sdf-ca.md`](docs/tarefas-felipe-sdf-ca.md). As duas frentes
podem avançar juntas: Felipe desenvolve flood fill e SDF com geometrias
sintéticas e um campo tubular de controle, sem aguardar o PLY completo; Pablo
entrega uma malha candidata para a integração posterior.

## Marcos conjuntos

- [ ] Acordar contrato XYZ↔ZYX, origem, espaçamento físico, sinal do SDF,
  `ε`, `τ`, máscaras de `UNKNOWN`, limites da região de interesse e formato dos
  artefatos. Uma mudança nesse contrato precisa ser refletida nas duas frentes.
- [ ] Validar, em formas fechadas conhecidas, malha → classificação → SDF →
  rótulos. Testar abertura legítima, gap acidental, orientação invertida e
  superfície não watertight antes do Elaphes real.
- [ ] Submeter a malha reconstruída a critérios de fechamento, orientação,
  manifoldness, interseções, componentes, distância aos pontos, área de tampas
  sintéticas e sensibilidade a parâmetros/resolução. `Watertight` isoladamente
  não garante `VOID` correto.
- [ ] Integrar a malha aceita ao flood fill/SDF. Se a incerteza impedir um
  sinal defensável em alguma região, preservá-la como `UNKNOWN`; não converter
  ausência de ponto em rocha ou ar por padrão.
- [ ] Derivar `VOID`, `SURFACE` e `SOLID` do SDF apenas em células válidas;
  persistir também SDF físico, TSDF normalizado, metadados e proveniência. Usar
  IoU volumétrica contra dados reais só onde `VOID` de referência for válido.
- [ ] Comparar CA clássico e CA condicionado sob seeds, forma, hardware e
  orçamento equivalentes; medir aderência ao controle, conectividade,
  diversidade, custo e sensibilidade ao peso do SDF.
- [ ] Depois de estabilizar CA+SDF, avaliar se o algoritmo genético melhora
  parâmetros da regra/controle contra uma busca simples de mesmo orçamento.
  Reservar o teste e separar custo de otimização do tempo de geração.
- [ ] Depois da referência validada, preparar divisões de dados sem vazamento
  espacial e decidir modelos GAN/PCGRL. O SDF exato da caverna de teste só pode
  alimentar um experimento separado de reconstrução condicionada, não o teste
  principal de geração.

## Ordem após a integração

1. Medir similaridade de superfície, volume e topologia em Python, com domínio
   e resolução comparáveis e `UNKNOWN` excluído ou explicitamente reportado.
2. Auditar quantidade de cavernas independentes antes de treinar GAN; estudar
   se TSDF/volume binário é a representação adequada. Um dataset sintético
   testa infraestrutura, sem demonstrar fidelidade às cavernas reais.
3. Especificar o MDP do PCGRL (`estado`, `ação`, `transição`, `recompensa`,
   `término`) e usar estatísticas apenas do treino. Validar ambiente pequeno
   antes de PPO/Conv3D; manter dados e métricas de teste fora da recompensa.
4. Reexecutar baselines, registrar custos de preparação, treinamento e geração
   separadamente, e atualizar o texto do TCC. Unity permanece visualizador e
   gRPC segue posterior ao pipeline científico.
5. Inspecionar o NASA Indian Tunnel `.f32`, seus atributos e limites completos
   antes de aplicar nele a mesma reconstrução; não pressupor que seus dados
   tenham cobertura ou normais equivalentes aos do Elaphes.

Mudanças Python com contrato observável exigem testes em `tests/`; antes de
concluí-las, executar a suíte disponível e uma importação ou exemplo pequeno,
conforme `AGENTS.md`.
