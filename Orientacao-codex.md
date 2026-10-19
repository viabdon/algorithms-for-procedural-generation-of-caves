# Próximos passos do TCC — reconstrução, SDF e geração

**Estado em 15/10/2026.** Leitura PLY/F32, limites XYZ, grade diagnóstica de
superfície em `32³`, `Volume3D`, Random Walk, CA básico e métricas iniciais
existem. O protótipo de Screened Poisson já produziu malhas candidatas do
Elaphes, mas nenhuma foi aceita como referência: a amostra global densa ainda
gera aberturas e extrapolação. A linha central exploratória inspirada em
Racine foi extraída e inspecionada; ela **ainda não prova interior/exterior**.
Há um protótipo de orientação por trechos que registra exatamente os pontos
com sentido incerto, permite destacá-los no HTML e aplicar decisões manuais
`keep`/`flip`. Como faltam posições interiores validadas em cortes, o
diagnóstico inicial marcou os 20.274 pontos do recorte como incertos.
Uma comparação posterior por cossenos não produziu malha fechada nem melhora
global comprovada. A reconstrução por orientação baseada na linha central
foi encerrada no escopo atual e documentada como pesquisa futura.
Não há no repositório flood fill/SDF de referência, CA condicionado, algoritmo
genético, GAN ou PCGRL funcional.

## Sequência da referência real

```text
point cloud XYZ
  → amostragem e normais estimadas/orientadas
  → Screened Poisson (ou fallback de reconstrução justificado)
  → malha revisada, aproximadamente watertight, com entradas/tampas marcadas
  → barreira voxelizada e classificação interior/exterior (flood fill inicial)
  → distância à superfície + sinal da classificação = SDF físico
  → TSDF truncado + VOID/SURFACE/SOLID/UNKNOWN + máscara válida em grade ZYX
```

A linha central LBC+MST foi uma trilha exploratória de **apoio à inspeção** das
normais e possíveis posições interiores; não seguirá como rota de reconstrução
da malha neste TCC. A [explicação teórica de
Racine](docs/resumos-teoricos/linha-central-racine.md) distingue o método
publicado da adaptação exploratória feita aqui. O [registro do
Elaphes](docs/metodologia/linha-central-elaphes-exploracao.md) contém os
parâmetros e resultados. O ramo curto real em X≈30 deve ser preservado em
eventual retomada; as pontas removidas perto da bifurcação real em X≈42
exigiriam revisão nos pontos brutos. A regra provisória de poda `<1,3` não é
critério geral.

## Contrato conjunto (Pablo + Felipe; meta 13/10)

- [ ] Fixar origem, espaçamento físico, eixos XYZ↔ZYX, shape e margem da
  grade **após aceitar a malha**. Documentar padding e a transformação para
  o eixo vertical da Unity sem alterar os índices ZYX internos.
- [ ] Fixar `SDF < 0 = VOID` e `SDF > 0 = SOLID/EXTERIOR`, `|SDF| ≤ ε =
  SURFACE`, `τ > 0`, `TSDF = clip(SDF,-τ,τ)/τ` e máscara separada para
  `UNKNOWN`. Um eventual canal navegável em `[0,1]` será uma transformação
  documentada do campo, não a classe categórica.
- [ ] Especificar formato de malha, faces sintéticas, entradas, máscara de
  suporte, arrays ZYX e metadados. Validar em cubo, esfera, tubo aberto e
  fenda antes da integração com o Elaphes.

## Trabalho paralelo imediato

| Responsável | Até 13/10 | Até 20/10 |
| --- | --- | --- |
| **Pablo** | Conferir os três pontos altos com a versão sanitizada oficial; comparar Poisson denso, segmentação e fallbacks contra suporte/topologia | Escolher e documentar candidata com entradas/tampas e regiões incertas; definir máscaras e protocolo de métricas/dados |
| **Felipe** | Implementar flood fill, sinal/SDF/TSDF e testes em geometrias sintéticas; gerar SDF tubular de controle independente | Integrar candidata aceita, verificar vazamentos/`UNKNOWN`, condicionar CA e comparar peso zero ao baseline |

Pablo pode entregar recortes e metadados para testes enquanto a malha global é
revista. Felipe não precisa esperar a referência real para construir o SDF de
controle. A malha atual **não deve** ser usada como verdade interior do Elaphes.
O [inventário do scanner](docs/metodologia/metadados-elaphes-scanner.md)
concluiu a busca nos materiais disponíveis: não há poses utilizáveis; cabeçalho
e `pointsourceid` foram revisados. O [fluxo de revisão de
normais](docs/metodologia/orientacao-normais-linha-central.md) e a comparação
controlada por cossenos estão documentados. Referências interiores verificadas
em cortes e a validação das associações com ramos permanecem questões para
pesquisas futuras, não tarefas da reconstrução atual.
Listas detalhadas: [Pablo](docs/tarefas/tarefas-pablo-reconstrucao-modelos.md),
[Felipe](docs/tarefas/tarefas-felipe-sdf-ca.md) e
[roadmap](docs/tarefas/roadmap.md).

## Depois da integração (metas indicativas)

- [ ] **Até 27/10:** avaliar referência apenas em células válidas, com IoU/
  Dice de `VOID`, distâncias de superfície sem contar tampas como observação,
  conectividade, ocupação e largura. Registrar sensibilidade à resolução,
  `ε`, `τ`, fechamento, amostragem e orientação.
- [ ] **Até 30/10:** comparar CA, CA+SDF e, após estabilizar os dois, discutir
  cromossomo/aptidão/orçamento e testar CA+SDF+algoritmo genético contra
  busca simples. Separar tempo de otimização e de geração.
- [ ] **Após referência validada:** auditar número de cavernas independentes e
  divisão espacial sem vazamento. Discutir se GAN deve gerar `VOID`, TSDF ou
  ambos; validar um `Dataset` `(B,1,D,H,W)` e treino pequeno antes de uma
  arquitetura maior. Autoencoder de reconstrução não demonstra geração nova.
- [ ] **Após definição do problema de RL:** especificar estado, ação,
  transição, recompensa e término do PCGRL; testar ambiente 3D pequeno antes
  de PPO/Conv3D. Metas vêm apenas do treino; o SDF exato do scan de teste
  pertence somente a experimento separado de reconstrução condicionada.
- [ ] Reexecutar baselines sob domínio, seeds, hardware e orçamento comuns.
  Unity renderiza as malhas finais; gráficos Python servem ao diagnóstico e
  gRPC vem após o pipeline científico.

Mudanças Python com contrato observável exigem testes em `tests/`, execução da
suíte e uma checagem de importação/exemplo pertinente, conforme `AGENTS.md`.
