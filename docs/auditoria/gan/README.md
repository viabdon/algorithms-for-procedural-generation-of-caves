# Auditoria dos voxels de referência para a GAN

O relatório técnico explica a preparação dos recortes, os consertos e
o estado atual das referências para a GAN. O histórico reúne as
rodadas e indica onde conferir a evidência por recorte.
[Relatório de voxelização](relatorio-voxelizacao.md) ·
[Histórico das rodadas](historico-voxelizacao.md)

Auditoria executada em **15/11/2026**, sem treinamento. Código reprodutível:
[`reference_data.py`](../../../src/cavegen/training/reference_data.py).
O [manifesto completo](reference_audit.json) contém hashes SHA-256 dos nove
NPZ, hashes dos dados binários, metadados, origem, métricas e recibos laterais.
As [partições congeladas](splits.json) usam caminhos relativos, utilizáveis
também no Colab. Nenhum arquivo de referência foi modificado.

## Conclusão da auditoria

**Os interiores da voxelização global de 15/11 não são adequados para
investigar geração de cavernas.** São consistentes com o flood fill aplicado às
superfícies, mas praticamente todo o vazio esperado está ausente. Isso é um
problema dos alvos de aprendizado; trocar a função de perda não o resolve.

| Caverna / trecho | Superfície observada | Interior candidato | Ar na grade | Componentes 6 | Maior componente | EDT máxima |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Archamps / PreEtroiture | 1.002 | 2 | 0,000763% | 2 | 1 voxel (50%) | 1,000 |
| Cascade de Môtiers / MainGallery | 761 | 1 | 0,000381% | 1 | 1 voxel (100%) | 1,000 |
| Indian Tunnel / Full 1x | 1.147 | 98 | 0,037384% | 5 | 92 voxels (93,88%) | 1,414 |
| Markov Spodmol / MainGallery | 1.198 | 5 | 0,001907% | 5 | 1 voxel (20%) | 1,000 |

As contagens são de voxels, não de pontos da nuvem. Os quatro interiores têm
shape **64×64×64 = 262.144 voxels**. Bounding boxes do ar em ZYX:
Archamps `2×2×1`, Cascade `1×1×1`, Indian `3×19×10`, Markov `2×8×7`.
Não há interior inteiramente vazio, mas o contrato de degeneração de
`structural-v1` só sinaliza todo-ar/todo-sólido; não basta para detectar esse
problema. Uma componente de um voxel ter fração conectada de 100% não é
evidência de qualidade de uma caverna.

Um controle totalmente sólido acertaria **mais de 99,96%** dos voxels de
qualquer uma dessas referências. Por isso acurácia voxel a voxel, sozinha,
poderia sugerir sucesso para uma saída sem caverna.

![Projeções das superfícies e dos interiores](projections.png)

Azul = ao menos um voxel de superfície ao longo do eixo projetado;
laranja = ao menos um voxel de ar inferido. A imagem foi inspecionada nos três
planos: revela as superfícies alongadas e o interior residual. A projeção pode
ocultar falhas e sobreposições em profundidade; não certifica um volume fechado.

## O que foi confirmado

- Nove arquivos NPZ binários válidos, com metadados JSON, sem pickle: quatro
  pares superfície/interior em 64³ e a superfície Elaphes em 32³.
- Eixos ZYX; normalização das quatro nuvens por uma escala compartilhada e
  padding simétrico, preservando proporções, sem esticar cada eixo.
- Os quatro interiores têm semântica
  `true_means_enclosed_unobserved_voxel` e estado
  `candidate_requires_geometric_validation`. Não são rótulos de ar validados.
- A reconstrução `classify_surface_by_flood_fill(surface) == INTERIOR`
  reproduz **exatamente** cada interior. A interseção ar/superfície é zero e
  bounds/shapes correspondem entre cada par. Não houve fechamento automático.
- A identidade binária dos quatro interiores é distinta. Superfície e
  interior de uma mesma nuvem são dois produtos da mesma fonte, não duas
  cavernas independentes.
- Os quatro `.run.json` registram processamento concluído, parâmetros,
  fonte e versões históricas. `.command.json` e `.bounds.json` também foram
  preservados no manifesto, com hashes calculados nesta auditoria.
- O vínculo de origem com `origem_nuvens.csv` foi encontrado para os quatro
  pares. A superfície legada Elaphes não tem vínculo automático exato com a
  linha de origem pelo nome do arquivo; sua atribuição geral já existe na
  auditoria anterior. Está excluída do treino de ar por semântica.

## O que não foi confirmado

Os recibos identificam as nuvens por caminho/tamanho/mtime, sem hash integral.
As nuvens originais não foram relidas nesta etapa. Os hashes dos derivados
garantem a identidade do que foi auditado, não a identidade com o download nem
a correção física da reconstrução. Não foi medida cobertura de superfície
contra todos os pontos, nem erro nuvem-malha ou fechamento geométrico.

Não é possível distinguir, só com estes NPZ, quanto da perda resulta de
entradas abertas, lacunas/oclusões, resolução insuficiente ou sua combinação.
As projeções e a EDT são compatíveis com perda severa de espessura; a causa
exata continua uma hipótese a verificar. A cópia local do artigo do
KarstConduitCatalogue é o **preprint de 26/05/2025**, não o PDF final.
O [artigo final, §4.3.2](https://essd.copernicus.org/articles/17/4671/2025/)
também relata regiões sem observação e reconstruções incertas em Markov Spodmol.

As licenças e pendências são as registradas em `origem_nuvens.csv`: há
divergência documental nos produtos do KarstConduitCatalogue e termos
específicos NASA/CMU no Indian Tunnel. Esta auditoria não substitui a
verificação desses termos, nem redistribui nuvens ou PDFs. O ZIP para Colab é
um artefato de trabalho local a ser usado de forma privada.

## Resolução: reduzir não salva estes interiores

Diagnóstico por vizinho mais próximo, com retorno a 64³; não é treino nem
nova voxelização das nuvens. O manifesto inclui métricas e recall/IoU de
reconstrução **do mesmo volume alinhado**. Essa IoU é pertinente à redução de
resolução, não à comparação de duas cavernas geradas sem alinhamento.

| Caverna | Ar em 16³ | Ar em 32³ | Recall do ar após 32³ → 64³ |
| --- | ---: | ---: | ---: |
| Archamps | 0 | 1 | 50,00% |
| Cascade de Môtiers | 0 | 0 | 0,00% |
| Indian Tunnel | 0 | 14 | 74,49% |
| Markov Spodmol | 0 | 0 | 0,00% |

Os quatro desaparecem em 16³. Nearest neighbor pode também alargar um voxel
retido ao voltar a 64³; recall alto não demonstra preservação de geometria.
Os modelos aceitam 16/32/64 para testes de software, mas o dataset de treino
exige resolução nativa correspondente. Não há downsampling silencioso.

A escala compartilhada dos bounds implica aproximadamente 1,849; 4,115;
2,706; 3,919 unidades da nuvem por passo de grade em Archamps, Cascade,
Indian e Markov, respectivamente. Interpretá-las como metros depende das
unidades de origem documentadas no CSV. São resoluções físicas diferentes:
comparar EDT em voxels avalia a forma normalizada, não calibres equivalentes
em metros. É uma razão adicional para estudar trechos/escala física antes de
ampliar o conjunto. Não foi convertido nenhum voxel inferido em uma medida
física de vazio validada.

## Partições e bloqueio de treino

Quatro cavernas independentes com interiores candidatos; quatro folds
rotativos, cada um com duas cavernas para treino, uma para validação e uma
para teste. São **partições de identidade já prontas**, não uma aprovação
geométrica dos dados. O campo `data_status` é
`blocked_insufficient_interior_geometry`. A marca `eligible_proxy` significa
apenas candidato não degenerado reproduzível do flood fill; não significa
pronto para aprender cavernas.

Foi acrescentado um mínimo de engenharia: maior componente com pelo menos
64 voxels e EDT máxima de pelo menos 2 voxels. Nenhum interior atual passa.
São limiares para rejeitar resíduos e espessura mal resolvida; não são valores
publicados como condição suficiente de realismo. A verificação é refeita nos
dados pelo loader, mesmo que alguém altere o sinalizador do manifesto.
`allow_candidate_proxy=True` documenta a aceitação da inferência de ar e não
contorna essa checagem. Passar o mínimo ainda exige inspeção geométrica.

O fold inicial `holdout_indian_tunnel` reserva Markov Spodmol para validação e
Archamps/Cascade para treino. Indian é um tubo de lava; a transferência de
duas cavernas cársticas para ele também envolve mudança de domínio. Relatar
todos os folds separadamente e agregados, sem escolher só o mais favorável.

## Próxima ação com os dados

Foi escolhido um piloto de **recortes por seções transversais sucessivas, com
tampas computacionais nas extremidades**, para inferir o interior de uma
galeria delimitada e preservar seus detalhes. O
[plano detalhado](../../plano-reconstrucao-secoes.md) registra os passos,
as validações e a integração futura com a GAN; o
[resumo simplificado](../../resumo-gargalo-gan.md) explica o problema atual.
O piloto local já produziu os primeiros interiores candidatos em Archamps.
O 004 fechou com as tampas, enquanto o 003 exigiu diagnóstico por janelas
e um remendo de um voxel. Esses resultados ficam em
`data/processed/reference_sections/`, com revisão geométrica pendente,
fora dos manifests e partições desta auditoria. [Evolução do piloto](../../plano-reconstrucao-secoes.md#evolucao-do-piloto-em-archamps)

Em 17/11/2026, o [planejamento dos recortes](../../planejamento-recortes-voxelizacao.md)
detalhou a seleção incremental de pontos com contexto, as seções das tampas,
o domínio da grade e o manifesto por trecho. O menu local faz a seleção
antes de voxelizar. Os limites passados ao CLI global controlam o domínio
da voxelização global.

1. Inspecionar cortes das nuvens e/ou malhas oficiais nos gargalos e entradas.
   Confrontar a superfície voxelizada com a nuvem para verificar perda de
   espessura, lacunas e oclusões.
2. Experimentar voxelização mais fina ou trechos com escala física comparável;
   manter o grupo da caverna ao gerar versões e recortes. Aumentar resolução
   sozinho não fecha uma entrada aberta.
3. Reconstruir uma superfície interna com fechamento de entradas explicitado e
   validado, por exemplo a partir de malha apropriada. Registrar regiões
   inferidas e erro nuvem-malha. Não aplicar dilatação arbitrária aos quatro
   interiores atuais para transformá-los em alvos de cavernas.
4. Gerar novos NPZ, repetir a auditoria e congelar novos hashes/partições.
   Inspecionar a geometria antes de habilitar treino. A arquitetura 64³ só é
   pertinente se o vazio for resolvido nessa escala; caso contrário usar
   recortes válidos ou revisar a resolução/arquitetura.

```powershell
$env:PYTHONPATH='src'
.\.venv-gan\Scripts\python.exe -m cavegen.training.reference_data
.\.venv-gan\Scripts\python.exe -m cavegen.training.plot_reference_audit
```

O ambiente `.venv` existente aponta para Linux e não executa no Windows.
A verificação do ambiente persistente de documentos também falhou: não existe
a distribuição WSL Ubuntu nem o caminho `/home/midnavi/...` nesta máquina.
Foi criado `.venv-gan`, ignorado pelo Git, usando Python 3.12; a extração dos
PDFs usou `pypdf` nesse ambiente disponível, sem reinstalar/modificar o
ambiente persistente ausente. O inventário dos artigos consultados está em
[`papers.json`](papers.json). Textos extraídos ficam apenas em `tmp/`, ignorado.

## Voxelização por recortes no fold inicial

Os lotes de preparação usam voxels de 16 cm e mantêm as partições de
`holdout_indian_tunnel`. Cascade de Môtiers usa o LAS MainGallery de
5 cm para treino. Markov Spodmol usa o LAS MainGallery de 5 cm para
validação. Indian Tunnel é reservado para teste. O plano Full 10x usa
uma linha central estimada. A comparação Full 1x reaproveita esse
grafo para testar a nuvem de maior densidade com a mesma divisão inicial.

Os planos em `data/processed/crop_plans/` registram as fontes, os
cortes e os alertas. Em `data/processed/reference_sections/`, o
`lote.csv` de cada plano inclui cada recorte tentado, o volume salvo ou
o motivo do bloqueio. Nos planos revisados, a busca tentou estações
próximas com suporte angular e contorno conectado, mantendo a escala e
os cortes compartilhados. Cada configuração permite tampas auxiliares
com raio de até quatro voxels, conforme o piloto de Archamps.

| Levantamento | Recortes por plano | Volumes no plano inicial | Volumes no plano revisado | 64³ com triagem mínima no revisado |
| --- | ---: | ---: | ---: | ---: |
| Cascade de Môtiers, MainGallery 5 cm | 63 | 12 | 14 | 14 |
| Markov Spodmol, MainGallery 5 cm | 65 | 10 | 11 | 8 |
| Indian Tunnel, Full 10x | 32 | 1 | 2 | 0 |
| Indian Tunnel, Full 1x | 32 | 1 | — | — |

Os planos inicial e revisado são versões da mesma nuvem. A tabela
compara os lotes individualmente. No plano revisado, os intervalos que
fecharam somam 108,2 m de linha central em Cascade, 75,3 m em Markov
e 11,0 m em Indian Tunnel. A soma é uma medida de cobertura dos
recortes que fecharam ao longo do grafo usado no plano.

A Full 1x fechou o mesmo recorte que a Full 10x no plano inicial,
`ramo_002_007`. A grade Full 1x é 72×64×100 e usou 11 voxels de
tampa sintética. As duas variantes iniciais deixaram 25 recortes sem
contorno completo. O aumento da densidade preservou o resultado nesse
trecho e deixou a cobertura geral do plano inicial pendente.

Os volumes mantêm a grade nativa. Os que excedem 64³ precisam de uma
decisão sobre a entrada da GAN e continuam disponíveis como referência
geométrica para revisão. Os lotes ainda incluem intervalos com tampas
ausentes, passagens próximas ou vazamentos sem fechamento verificado.
Os manifests de treino continuam vinculados à auditoria dos volumes
globais até a revisão dos recortes.

### Cortes e bifurcações em Cascade de Môtiers

O grafo da MainGallery tem 24 nós de bifurcação e 49 cadeias entre
bifurcações ou extremidades. O plano de 63 recortes deu prioridade
aos trechos mais longos e cobriu cerca de 410 m em 19 cadeias.
Pedir 63 recortes foi uma escolha operacional para seções de cerca de
8 m nas passagens mais longas. O grafo usado no piloto de Archamps
PostEtroiture representa uma única cadeia.

No plano revisado, 19 recortes ficaram sem contorno de extremidade,
3 tiveram semente bloqueada e 27 vazaram com alerta de passagem
próxima ou retorno. O bloqueio de fechamento automático nesses 27
protege conexões possivelmente reais. Todos vazaram mesmo com planos
temporários cobrindo as extremidades. Na rota principal registrada,
a distância mínima a um nó de bifurcação variou de 1,16 a 18,64 m.
Essas distâncias ajudam a localizar a inspeção. A origem física da
fuga depende da conferência com os pontos observados.

Para os cortes sem contorno, testar uma nova estação ou recentrar a
estimativa do raio no plano existente. Em Archamps, o percentil 75
calcula um raio por setor angular. A revisão da estação determina
onde fica o corte. Um corte interno deve manter a mesma posição e
o mesmo contorno nos dois recortes vizinhos.

Um ensaio de recentragem no mesmo plano recuperou 11 dos 19 contornos
testados em Cascade e fechou mais dois volumes a 16 cm, `ramo_016_002`
e `ramo_027_002`, ambos em 64³. Em Markov, recuperou 4 dos 18 contornos
testados e fechou `ramo_017_007` em 64×74×64. Em Indian Tunnel,
os 26 contornos testados permaneceram pendentes. Os candidatos do
ensaio ficam em `contornos_16cm`. Para revisão manual em Cascade,
`revisao_cortes.csv` lista as estações e os recortes vizinhos e
`revisao_fugas.csv` aponta para as provas dos 27 vazamentos.

### Comparação experimental com voxels de 28 cm

Uma busca numérica por orientações compactas em Indian Tunnel
encontrou caixas de 11,13 a 12,20 m considerando apenas os centros
dos voxels de ar dos volumes fechados a 16 cm. A maior dimensão
permaneceu acima dos 10,24 m disponíveis em 64³ a 16 cm nas
orientações testadas.

A condição experimental de 28 cm revoxelizou os mesmos PLYs e
preservou as posições e os contornos das extremidades. Ela usou
a mesma escala nas quatro cavernas e limitou a tampa auxiliar
a dois voxels de raio. Em `mesmos_cortes_28cm`, 5/6 recortes de
Archamps, 16/63 de Cascade, 13/65 de Markov e 2/32 de Indian
Tunnel fecharam. Passaram na triagem mínima em 64³ respectivamente
5, 14, 13 e 2 recortes. O ar dessas amostras alcança ambas as tampas.

Os dois trechos de Indian Tunnel comparáveis apresentaram IoU
de aproximadamente 0,91 com a grade de 16 cm, medida pela
interseção física dos voxels nas duas grades. Em Cascade e Markov
houve amostras comparáveis com IoU abaixo de 0,65. A resolução de
28 cm permite uma entrada cúbica comum neste ensaio. A escolha da
escala e a validação dos interiores continuam pendentes para o
conjunto de referência da GAN.

### Reextração de cortes pendentes e auditoria para a GAN

O ensaio `cortes_refitos_16cm` buscou contornos na nuvem de origem
até 2,56 m antes ou depois de cada estação pendente. Testou recentragem
de até 0,96 m no plano e exigiu pelo menos 14 setores com suporte.
Quando houve um contorno aceito, o mesmo plano foi usado nos dois
lados do corte e os recortes afetados foram reextraídos. Os alertas
de passagem próxima continuaram ativos.

| Caverna | Cortes com contorno aceito | Recortes reextraídos | Volume que fechou |
| --- | ---: | ---: | --- |
| Cascade de Môtiers | 19 de 19 | 19 | `ramo_027_002`, 64³ |
| Markov Spodmol | 12 de 18 | 13 | `ramo_017_007`, 64×73×64 |
| Indian Tunnel | 2 de 26 | 1 | Nenhum |

Os dois volumes fechados são novas versões de recortes já recuperados
no teste de recentragem. Os resultados reforçam a necessidade de
investigar as fugas e a semente após acertar as extremidades.

Para auditar um conjunto experimental, use
`python -m cavegen.training.gallery_reference_data` com os diretórios
dos planos relativos a `data/processed/reference_sections`. Defina
`--resolution` e `--voxel-size` para uma grade cúbica e uma escala
comuns. A auditoria refaz o flood fill com a superfície e as máscaras,
verifica o contato com as duas tampas e registra os hashes da evidência.
O loader exige `allow_candidate_proxy=True` para esses interiores.

A execução local em `data/processed/experiments/gan_piloto_28cm/`
auditou 36 volumes do ensaio de 28 cm e reteve 34 na triagem numérica
64³. No fold `holdout_indian_tunnel`, são 19 de treino, 13 de validação
e 2 de teste. Os hashes e a separação por caverna foram rechecados nos
quatro folds. O manifesto experimental mantém o status
`gallery_proxy_pending_review`. A cobertura parcial e a sensibilidade
à escala continuam pendentes para definir o conjunto de treino.
