# Preparação de volumes de cavernas

Este guia descreve o fluxo integrado para ler nuvens XYZ, PLY, F32 ou LAS, calcular
limites globais, voxelizar a superfície observada e, opcionalmente, inferir
interior por flood fill. Os arquivos brutos são lidos diretamente, inclusive de
um HD externo. O processamento é determinístico para uma mesma entrada,
configuração e implementação; não há seed aleatória nesta preparação.

## Piloto local de recortes por galeria

Na raiz do repositório, abra `.venv/bin/python -m cavegen.datastream` e
escolha **2 — Preparar recortes por galeria**. A opção **1** do submenu lista
as nuvens do HD (a pasta pode ser alterada). Copie o
[modelo JSON](../configs/crops/gallery.template.json) para um arquivo por
trecho. A opção **2** confere a configuração e mostra o destino e a partição
sem ler os pontos. A opção **3 — Voxelizar recortes** oferece
dois modos de entrada.

- **1 — Um recorte (crop.json)** recebe o arquivo do
  trecho, como `ramo_001_001/crop.json`.
- **2 — Recortes em lote (pasta ou plan.json)** recebe a pasta do
  plano ou seu `plan.json`. O menu procura `crop.json` nas subpastas
  imediatas e percorre os recortes em ordem de nome da pasta. Os avisos
  mostram a posição no conjunto, o identificador do recorte e a
  contagem de pontos. Ao final, o menu resume os recortes processados,
  os pulados por terem uma saída existente e os que tiveram erro.

Digite `PROCESSAR` para confirmar a execução. O processamento testa
o fechamento original e inicia o
[diagnóstico de vazamento](#quando-o-flood-fill-encontra-o-exterior)
se alcançar a borda pela semente. Na opção **4**, informe a pasta da execução para salvar
`fatias.html` com as três fatias ortogonais pela semente e
`volume.html` com a vista 3D dos voxels. Na vista 3D, clique na
legenda para alternar superfície observada, ar candidato e tampas. A
superfície e o ar aparecem ao abrir, e as tampas começam ocultas.

Para autorizar tampas sintéticas em um recorte, defina
`auxiliary_cap_radius_voxels` no seu JSON. O valor padrão 0 desativa a
etapa. Valores inteiros de 1 a 8 limitam o raio do fechamento morfológico
em voxels. O ensaio de Archamps usou 4, ou 64 cm na grade de 16 cm.
O algoritmo só tenta essa etapa quando o reparo local falha e a passagem
não está marcada como ambígua. Ele testa raios crescentes e retém células
da borda sintética em contato com o ar da semente. O ar deve alcançar
ambas as tampas das extremidades e incluir as sementes das janelas que
fecharam no diagnóstico. O flood fill a partir do exterior verifica o
resultado salvo.

A opção 4 mostra as tampas auxiliares em vermelho. Em `masks.npz`,
`auxiliary_caps` marca a hipótese de fechamento, `repair` marca o reparo
local e `caps` guarda as duas extremidades. O relatório `summary.csv`
registra as contagens e o raio usado. A revisão geométrica deve verificar
se alguma abertura correspondia à continuação de uma passagem.

### Propor e extrair recortes pela linha central

1. Copie o [modelo de planejamento](../configs/crops/plan.template.json) e
   informe a nuvem, o número desejado em `count` e o lado físico do voxel
   em `voxel_size`. Para usar a linha de Racine, indique o arquivo
   `*_nodes_from_LBC.txt` com o `*_links_from_LBC.txt` correspondente na
   mesma pasta. O NPZ experimental do Elaphes também é aceito, com os campos
   `nodes_xyz` e `edges`. O grafo deve estar no mesmo sistema da nuvem.
   Os caminhos no JSON são absolutos ou relativos ao próprio JSON.
2. Use a opção **5**. O menu aceita um caminho de linha central para esta
   execução. Se o campo e a resposta estiverem vazios, estima a linha em
   CPU e salva `centreline.npz` no plano. Para esse modo, instale o extra
   com `uv sync --locked --extra centreline`. Com grafo pronto, o planejador
   percorre a nuvem duas vezes para estimar seções e extrair pontos. A
   geração da linha central acrescenta uma leitura em lotes. Com
   `section_search_radius_voxels` maior que zero, há uma leitura
   adicional para comparar a nuvem original com o filtro por ramo e
   testar outras estações. O modelo de plano usa oito voxels.
   [Revisão de contornos](planejamento-recortes-voxelizacao.md#revisão-de-contornos-no-planejador)
3. Quando quiser visualizar, use a opção **6** e informe a pasta do plano,
   seu `plan.json` ou o `cloud.ply` de um dos recortes. Escolha **1** para
   agrupar os recortes com pontos em um único `recortes.html`, com
   uma cor por trecho e até 60.000 pontos distribuídos entre eles. Na
   legenda, clique no nome para mostrar ou ocultar o trecho. Escolha **2**
   para salvar um `recorte.html` ao lado de cada PLY em uma só
   execução, com até 60.000 pontos por recorte. Abra os HTMLs no navegador.
   Use **Mostrar tampas** para sobrepor todos os contornos disponíveis ou
   alterne uma extremidade pela legenda. Os contornos vêm do `crop.json` e
   ficam ocultos ao abrir o HTML. Extremidades sem polígono ficam sem contorno.
   Um PLY avulso ainda pode ser visualizado individualmente.
4. Revise o PLY, os alertas, os contornos e a semente do `crop.json`.
   Use a opção **2** para validar a configuração e, após a revisão, a
   opção **3** para voxelizar e aplicar o flood fill a um recorte ou ao
   conjunto do plano. No caso de Elaphes,
   a etapa de recorte pode usar o grafo experimental no seu domínio de
   validade. A voxelização pelo menu exige que a caverna e o fold constem na
   auditoria.

Por padrão, as propostas ficam em
`data/processed/crop_plans/<caverna>/<levantamento>/<fold>/<plano>/`.
O nome do JSON é usado como identificador do plano, ou pode ser substituído
por `plan_id`. O diretório guarda `plan.json`, o grafo gerado quando
aplicável e uma pasta por recorte com `crop.json` e o PLY quando há pontos.
Os volumes gerados a partir desse plano ficam em
`data/processed/reference_sections/<caverna>/<levantamento>/<fold>/<plano>/<recorte>/<resolucao>/`.
Isso permite comparar planos ou folds sem sobrescrever recortes numerados
da mesma forma.

Os parâmetros em `centreline_extraction` vêm do ensaio exploratório do
Elaphes. A contração usa o laplaciano robusto e uma solução esparsa em
SciPy. O amostrador mantém o primeiro ponto por célula e dobra
`sample_spacing` quando o total passa de `max_samples`. Depois da
contração, `node_spacing` reduz os nós e uma árvore geradora mínima no
grafo de vizinhos os conecta. O `plan.json` registra a escala amostral
efetiva, versões e componentes. A geometria estimada continua candidata
à revisão, especialmente se houver conexões longas ou contração excessiva.

O planejamento distribui N por comprimento ao longo dos caminhos entre
pontas e junções, evitando colocar planos no nó de bifurcação. Cada ponto é
associado aproximadamente à linha central por uma busca espacial e uma
projeção na aresta candidata. O recorte usa posição ao longo do percurso,
distância transversal e os dois planos. A estimativa do raio de seleção
usa o percentil 99 das distâncias observadas mais um voxel, com espaço
para o contorno proposto. A proximidade de outra passagem ou de uma parte
distante do mesmo caminho gera um alerta. É possível obter menos que N
quando os caminhos são curtos para a escala escolhida.

Para as tampas, o código compara três candidatos por posição de corte e
mede a cobertura dos pontos projetados em faixas angulares. Lacunas
relevantes deixam o contorno em branco para revisão. A margem
`padding_voxels` se aplica à grade, separada do raio que seleciona pontos.
Trechos que excedem 64 células em algum eixo na escala escolhida recebem
um alerta. Revise todos os candidatos antes do flood fill.

Para planejar uma lista explícita de ramos, use `passages` com os
índices originais do grafo, a partir de 1. Por exemplo, use
`"passages": [3, 7]` e `"count": 2` para produzir um recorte de cada
ramo. Use um `count` maior para dividir os ramos selecionados, respeitando
o mínimo de oito voxels úteis por trecho após as margens. Cada ramo
solicitado precisa comportar ao menos um recorte. Omitir `passages`
mantém a priorização automática dos intervalos mais longos.

Em uma cópia do plano, use `section_overrides` para fixar cortes examinados
na nuvem original. `passage` começa em 1, como em `passagem_001`. `cut`
começa em 0 na extremidade inicial. O corte 1 é compartilhado pelo
primeiro e pelo segundo recorte da passagem. `station` é a distância
ao longo da linha central nas unidades do plano. Para manter os recortes
em ordem, a separação entre cortes tem de ser de pelo menos oito voxels.

```json
{
  "section_overrides": [
    {"passage": 1, "cut": 0, "station": 0.16, "contour": "connected"},
    {"passage": 1, "cut": 5, "station": 43.620740923070285}
  ]
}
```

Nos cortes fixados, a estimativa usa o plano da estação informada.
O modo `radial`, padrão, usa os pontos projetados em conjunto.
O modo `connected` agrupa os pontos em células vizinhas no plano, com
lado de dois voxels. A tampa usa o único componente que sustenta um
contorno com pelo menos 14 de 16 faixas angulares e lacunas isoladas.
Se houver dois contornos aptos, a seção fica pendente com o alerta
`tampa_com_contornos_concorrentes`. O mesmo plano e polígono são usados
pelos dois recortes vizinhos, com normais opostas.

Os PLYs contêm apenas XYZ dos pontos retidos, em coordenadas locais, com
24 bytes por ponto no corpo do arquivo.
Some `source_origin_xyz` (gravado no plano e nos JSONs) para recuperar as
coordenadas da fonte. A prévia usa uma amostra. A voxelização usa todos os
pontos do PLY. Alterar os limites no JSON permite filtrar esse arquivo,
enquanto recuperar pontos excluídos exige uma nova extração.

### Configuração de um recorte

- `source` aceita XYZ, PLY, F32 e LAS, com caminho absoluto ou relativo ao
  JSON. `cave` e `fold` são os IDs da
  [auditoria GAN](auditoria/gan/splits.json) e determinam a partição.
  `survey`, `branch` e `crop_id` identificam o levantamento, o ramo
  revisado e o trecho. Comece com uma passagem simples de treino. Por exemplo,
  `archamps` é treino em `holdout_indian_tunnel`.
- `selection_min_xyz` e `selection_max_xyz` delimitam a caixa candidata,
  com mínimos inclusivos e máximos exclusivos. Inclua contexto além dos
  planos. A seleção efetiva é a interseção da caixa com o lado interno de
  cada plano. Revise se a caixa contém uma só passagem e se preserva paredes,
  piso e teto. Os bounds globais em `data/params/` descrevem os levantamentos.
- `sections` contém os dois cortes. `point_xyz` é a origem de cada plano,
  `inward_normal_xyz` aponta para dentro do trecho e `u_xyz` orienta o
  primeiro eixo do plano. O código projeta U no plano e o normaliza, depois
  calcula **V = N × U** com a normal unitária N. Assim, U e V são
  perpendiculares e dão dois eixos no próprio plano. Para um ponto P com
  origem O, `u = (P − O) · U` e `v = (P − O) · V` dão as coordenadas
  usadas para testar se o centro do voxel cai no `polygon_uv` revisado.
  Informe os vértices do contorno em ordem. Se inverter N e conservar U,
  V também inverte. Confira o sinal nas duas extremidades.
- `origin_xyz`, `shape_zyx` e `voxel_size` definem a grade, com voxels
  cúbicos e margem livre ao redor da barreira. Use o mesmo sistema de
  coordenadas da fonte e registre a unidade em `units`. Para comparar
  resoluções no mesmo domínio físico, dobre o shape e reduza o lado do
  voxel à metade. A `plane_tolerance` deve ser pequena frente ao voxel.
- `seed_xyz` marca um ponto revisado dentro da passagem. O flood fill
  percorre voxels livres por seis vizinhos de face. No recorte, o código
  parte da semente e verifica se a componente alcança a borda. Se a
  semente estiver ocupada, `seed_search_radius_voxels` limita a busca
  automática por outra posição (padrão 4, zero desativa). O volume
  com semente reposicionada exige confirmação pelo exterior e contato
  com as duas tampas. Barreira na borda, tampas sem contato com a parede
  e busca sem candidata exigem revisão. Para uma semente livre
  conectada ao exterior, o menu inicia o diagnóstico automático.
  [Busca automática da semente](planejamento-recortes-voxelizacao.md#busca-automática-quando-a-semente-cai-na-barreira)
- `batch_size` limita o lote de leitura. `progress_every` define a
  frequência do aviso em pontos lidos, com `0` para desativar.
  A nuvem é percorrida uma vez por recorte.

Para a configuração manual, as saídas ficam em
`data/processed/reference_sections/<caverna>/<levantamento>/<recorte>/<resolucao>/`.
`surface.npz` contém a parede observada. `masks.npz` reúne as duas
tampas em `caps` e a máscara `repair`. `interior.npz` contém o ar
candidato em ZYX, e `run.json` guarda a configuração,
partição, contagens e status `pending_review`. Revise se o interior se
mantém contínuo e estável frente a pequenas mudanças de corte e resolução.
O [planejamento dos recortes](planejamento-recortes-voxelizacao.md) descreve
a metodologia e os critérios ainda pendentes antes de usar os volumes no treino.

### Quando o flood fill encontra o exterior

1. **Delimitar a falha.** O diagnóstico reutiliza a grade, testa se os planos
   de corte completos barram a fuga e percorre a galeria com duas tampas
   temporárias. A varredura usa janelas de oito voxels com avanço de quatro.
   Nas janelas que vazam, move um plano por vez em passos de um voxel.
   Cada tentativa fica registrada por intervalo e estado da semente.
2. **Investigar os bins.** Um caminho de fuga é rastreado na grade por
   vizinhança de face. O código conta os pontos do PLY e, se a fonte estiver
   disponível, da nuvem original nos mesmos bins próximos do caminho.
   O `plan.json` dá a proveniência. Se os caminhos tiverem mudado, use
   `leak_diagnostics.raw_source` e `leak_diagnostics.centreline` no
   `crop.json`, com caminhos absolutos ou relativos a esse JSON. Use a
   mesma nuvem e a mesma linha central do plano. O relatório identifica
   a projeção usada e a disponibilidade da comparação.
3. **Testar um reparo pequeno.** Os candidatos precisam de pontos da fonte
   dentro da seleção ou continuidade local da parede, inferida com apoio em
   direções opostas. O algoritmo testa voxels sobre rotas que efetivamente
   vazam. O orçamento é de até 12 voxels. A checagem final exige fechamento
   do recorte inteiro após retirar as tampas móveis e preserva as sementes
   das janelas que já fecharam. O resultado continua pendente de revisão.
4. **Verificar por inundação exterior.** A busca se propaga a partir da
   semente. Para conferir a conclusão, a pipeline reclassifica a grade
   partindo da borda, compara a componente à máscara de ar e retira cada
   voxel de reparo por vez. A semente deve voltar a ser alcançada pelo
   exterior sem cada voxel publicado. Remover cada tampa também é testado
   e documenta quanto o fechamento depende dos cortes.

### Relatório por recorte e reprodução

Cada execução concluída grava `<resolucao>/relatorio_volume/`. Se uma checagem
de superfície, margem, contato, semente ou fechamento impedir a publicação,
o menu aponta para `<resolucao>_sem_volume/<tentativa>/summary.csv`.
O nome curto `_sem_volume` identifica o histórico ao lado da pasta da
resolução. A opção 4 também reconhece as pastas antigas de relatórios e
tentativas. Quando há uma amostra da fuga, a visualização se chama
`vazamento.html`.

| Arquivo | O que registra |
| --- | --- |
| `summary.csv` | Uma linha por execução, com fonte, método, versões de bibliotecas, parâmetros, grade, busca da semente, estado da comparação e desfecho. |
| `checks.csv` | Checagens de superfície, margem, contato, semente, comparação do ar e retirada de tampas ou de voxels de reparo. |
| `probes.csv` | Planos completos, deslocamentos das tampas e janelas da busca com intervalo físico e estado da semente. |
| `bins.csv` | Bins suspeitos em ZYX, centro XYZ na origem da fonte, contagens do PLY e do original, apoio geométrico e remendo publicado. |
| `paths.csv` | Trajetórias de fuga com IDs e coordenadas dos voxels em ordem. |
| `preview_data.npz` | Máscaras locais pequenas e amostras de pontos necessárias à inspeção no Plotly. |

As duas primeiras tabelas bastam quando a geometria falha antes da busca
ou o recorte fecha sozinho. As demais saídas são gravadas quando há
busca por vazamento. Os CSVs usam UTF-8, vírgula como separador e ponto
decimal. Valor vazio significa que aquela informação não se aplica ou
não foi medida. Um `0` nas contagens significa que o bin foi checado e
nenhum ponto foi encontrado. Em `checks.csv`, `expected` e `passed`
ficam vazios nas ablações informativas das tampas.

Passe a pasta da execução, a da tentativa ou o `summary.csv` à opção **4**.
Quando existe uma amostra local, o menu gera três fatias com camadas
alternáveis de trajetória e pontos. O HTML amostra os pontos para
visualização. As contagens em `bins.csv` usam todos os pontos relevantes.
Os volumes das janelas temporárias ficam em memória. Os dados binários
da visualização ficam no NPZ comprimido, e o `run.json` continua sendo
o recibo de configuração da execução.

Para repetir só a reclassificação e as retiradas usando os NPZs já
salvos, sem reler a nuvem, execute na raiz do projeto:

```bash
.venv/bin/python -m cavegen.datastream.gallery_reports CAMINHO_DA_RESOLUCAO
```

O comando grava `relatorio_volume/checks_replay.csv`. Para repetir também a
localização da fuga e as contagens do PLY e do original, use uma cópia
do `crop.json` na mesma pasta, preservando o `crop_id` e usando um
`plan_id` diferente no modo **3 → 1**. Em Python, é possível reaproveitar o
mesmo `crop.json` e trocar apenas o destino com
`dataclasses.replace(prepare_crop(config), destination=novo_destino)`
antes de chamar `process_crop`. No caso de Archamps, a rechecagem usou a
configuração local `crop_rechecagem_original.json` com os caminhos
atualizados do LAS e da linha central.

O [histórico e os critérios do piloto](plano-reconstrucao-secoes.md#evolucao-do-piloto-em-archamps)
explicam por que o 003 motivou a varredura e como interpretar um reparo
verificado sem confundi-lo com uma observação da superfície.

## Ambiente e menu

Na raiz de uma cópia do projeto, prepare o ambiente conforme a seção de
instalação do [README](../README.md). Para usar a resolução versionada das
dependências, execute `uv sync --locked`. O comando curto do menu é:

```bash
.venv/bin/python -m cavegen.datastream
```

O menu da datastream funciona independentemente do menu de benchmark e da
integração dos geradores CA/Random Walk. A opção **1** voxeliza a nuvem
inteira e solicita:

1. Caminho da nuvem, aceitando espaços e caminhos entre aspas.
2. Resolução ZYX: um lado para grade cúbica, como `64`, ou três dimensões,
   como `32 64 64`.
3. Pasta de saída. O padrão separa fonte e resolução:
   `data/processed/references/<nome>/<D>x<H>x<W>/`.
4. JSON de limites existente ou Enter para calcular automaticamente.
5. Lote de leitura, padrão 65.536 pontos, e intervalo de progresso,
   padrão 1.000.000 de pontos; `0` desativa os avisos por pontos.
6. Uso do flood fill, habilitado por padrão no menu.
7. Execução em primeiro plano, em segundo plano ou cancelamento.

O menu mostra o comando equivalente antes de executar. Caminhos dentro
da pasta atual aparecem em formato relativo, e o registro do comando
inclui a pasta de trabalho para reprodução. Para preservar ensaios
anteriores, recusa uma pasta com arquivos de saída conflitantes: escolha outra
pasta para uma configuração ou execução diferente. As entradas numéricas e os
caminhos são conferidos antes do lançamento; o leitor valida o conteúdo durante
a leitura. Interromper o menu com EOF ou Ctrl+C encerra a interação. Durante um
trabalho em primeiro plano, Ctrl+C interrompe esse trabalho; os arquivos já
salvos podem permanecer, sem um registro de conclusão.

## Arquivos produzidos pelo menu

| Arquivo | Conteúdo |
| --- | --- |
| `surface.npz` | Grade booleana em ZYX; `True` é superfície observada. Metadados incluem fonte, formato, limites, normalização e parâmetros de processamento. |
| `surface.bounds.json` | Limites XYZ globais, se calculados nesta execução. Quando fornecidos, o arquivo existente é reutilizado. |
| `interior.npz` | Opcional. `Volume3D` em ZYX, com `True` nos voxels não observados isolados do exterior. É candidato a ar interno; a superfície fica excluída. |
| `surface.command.json` | Comando solicitado, diretório de trabalho e modo de execução. Salvo pelo menu antes do trabalho, inclusive para diagnosticar execuções interrompidas. |
| `surface.run.json` | Registro de conclusão, configuração efetiva e comando de reprodução, criado quando todo o processamento termina com sucesso. |
| `surface.log` e `surface.pid` | Log e PID do processo quando lançado pelo menu em background. |

No CLI direto, os nomes dos arquivos auxiliares derivam do caminho de
`--output`: por exemplo, `surface_64.npz` produz `surface_64.bounds.json` e
`surface_64.run.json`. O arquivo `.command.json` é específico do menu. Não
confundir superfície com interior, nem renomear um NPZ de superfície como se
fosse um volume de ar. Para ler os resultados, use `load_surface_npz` e
`load_volume_npz`, respectivamente, em `cavegen.datastream`.

## Progresso e execução em background

Os quatro leitores usam o mesmo mecanismo de progresso. Na primeira passagem,
`[Bounds]` informa os pontos lidos para calcular os limites; na segunda,
`[Voxelization]` informa os pontos consumidos para construir a grade. Os
contadores reiniciam em cada etapa: não são pontos diferentes. Com limites
fornecidos, só há a passagem de voxelização.

Cada marco de um milhão é anunciado, inclusive se um lote cruzar vários
marcos. As mensagens são emitidas ao terminar a leitura do lote correspondente;
um aviso de 1.000.000 significa que pelo menos esse número já foi lido. Os
avisos usam `flush=True`, de modo que aparecem também em logs redirecionados.
O flood fill opera sobre a grade já formada, não sobre pontos: anuncia seu
início e o total de voxels internos encontrado, sem contador artificial de pontos.

No modo background do menu, o processo inicia em uma nova sessão no Linux,
com entrada desconectada do terminal e saída direcionada ao log. Pode-se fechar
o menu e o terminal. Para acompanhar, use o caminho exibido, por exemplo:

```bash
tail -f data/processed/references/caverna/64x64x64/surface.log
```

Ctrl+C nesse `tail` encerra somente o acompanhamento. Para interromper o
trabalho, confira se o PID ainda corresponde à execução antes de sinalizá-lo:

```bash
ps -p "$(cat data/processed/references/caverna/64x64x64/surface.pid)" -o pid,args
kill "$(cat data/processed/references/caverna/64x64x64/surface.pid)"
```

O PID é apenas uma identificação de lançamento e pode ser reutilizado pelo
sistema depois que o processo termina. Um log com traceback indica falha;
consulte o aviso final e o registro `.run.json` para conferir a conclusão.
Suspender/desmontar o HD durante a execução pode interromper a leitura.

## Comandos diretos para os quatro formatos

A sintaxe é a mesma para todas as nuvens. Ajuste o caminho, o nome da pasta e a
extensão de entrada; o formato é selecionado automaticamente:

```bash
.venv/bin/python -u -m cavegen.datastream.run_reference_voxelization \
  --input "/caminho/no/HD/caverna.ply" \
  --shape 64 64 64 \
  --batch-size 65536 \
  --progress-every 1000000 \
  --output data/processed/references/caverna/64x64x64/surface.npz \
  --interior-output data/processed/references/caverna/64x64x64/interior.npz
```

Para F32, use `--input "/caminho/no/HD/caverna.f32"`; para XYZ, use
`--input "/caminho/no/HD/caverna.xyz"`; para LAS, use
`--input "/caminho/no/HD/caverna.las"`. O flood fill é aplicado após a
voxelização em todos os casos. Remova `--interior-output` para gerar apenas
superfície. `--ply` é um alias legado de `--input`.

Sem `--bounds`, o arquivo bruto é percorrido duas vezes, mantendo somente
lotes na memória. Para reutilizar os limites da mesma nuvem, acrescente:

```text
--bounds data/processed/references/caverna/64x64x64/surface.bounds.json
```

Ao trocar a resolução, escolha uma pasta de saída diferente. O CLI direto
pode sobrescrever saídas existentes; para evitar substituições acidentais,
prefira o menu ou use um destino novo. Os limites de outra nuvem não devem ser
reutilizados. O [README](../README.md#novas-nuvens-xyz-e-execução-em-segundo-plano)
também mostra lançamento direto com `nohup` e redirecionamento de log.

## Contrato de entrada e do preenchimento

- XYZ: texto UTF-8 com X Y Z nas três primeiras colunas, espaços/tabulações,
  sem cabeçalho de nomes ou contagem inicial. Linhas vazias, BOM e comentários
  `#` são aceitos; colunas adicionais são ignoradas. Valores inválidos geram
  erro com caminho e número da linha. Não é XYZ molecular nem CSV com vírgulas.
- PLY: cabeçalho com coordenadas dos vértices; o leitor existente aceita ASCII
  e binário nos formatos suportados por `cavegen.datastream.ply`.
- F32: binário sem cabeçalho, sete atributos float32 por ponto na ordem
  `x y z nir r g b`, conforme `cavegen.datastream.f32`. Apenas XYZ é usado.

- LAS: binário não comprimido, lido em lotes pelo `laspy` (dependência base
  `>=2.5,<3`, fixada no `uv.lock`). As coordenadas decodificadas são
  `inteiro * scale + offset`, não os inteiros crus X/Y/Z do registro. O leitor
  usa x/y/z escalados, rejeita cabeçalho inválido, escala não positiva,
  coordenadas não finitas, nuvens vazias e registros truncados. Intensidade,
  RGB, classificação e retornos adicionais não são usados para filtrar pontos.
  Os testes incluem formatos de pontos 0 e 3 em LAS 1.2 e formato 6 em LAS 1.4.
  LAS comprimido e extensão `.laz` não são aceitos neste fluxo; não há backend
  de descompressão instalado por esta mudança. Escalas, offsets, versão LAS,
  formato e contagem de pontos são gravados em `las_header` nos metadados.
  Não é aplicada reprojeção de CRS; registre a unidade e o sistema de referência
  da fonte na documentação do dataset. Consulte a documentação oficial de
  [leitura em lotes](https://laspy.readthedocs.io/en/latest/basic.html#chunked-reading)
  e de [coordenadas escaladas](https://laspy.readthedocs.io/en/latest/complete_tutorial.html).

O contrato de coordenadas é float32. Coordenadas georreferenciadas de grande
magnitude podem perder detalhes nessa precisão; definir origem local é uma
etapa explícita de preparação quando necessária. A normalização usa escala
compartilhada, preserva proporções e converte XYZ para índices ZYX com padding
simétrico; eixos degenerados ficam centralizados.

O flood fill usa vizinhança de seis faces e considera fora da grade como
exterior. Superfície observada é barreira; vazio não alcançado vira interior
candidato. A regra não faz dilatação, suavização ou fechamento de entradas.
Diferentemente do rótulo interno do protótipo da branch `CA`, voxels observados
em paredes espessas permanecem superfície e não entram como ar. Passagens
abertas podem deixar a máscara interna vazia, enquanto contatos diagonais podem
parecer fechados em conectividade 6. Os metadados registram
`candidate_requires_geometric_validation`; nenhuma dessas etapas calcula SDF
ou comprova que toda região fechada corresponde ao vazio real de uma caverna.
Inspecione cortes e sensibilidade à resolução antes do uso em treino.

## Como preservar e repetir uma execução

Guarde os brutos originais, o JSON de limites, os NPZ, o registro `.run.json` e
o log. Esse registro inclui comando com parâmetros efetivos e caminhos
absolutos, argumentos solicitados, diretório de trabalho, limites, shape ZYX,
lote, intervalo de progresso, opção de flood fill, versões de Python/NumPy/SciPy/laspy,
commit Git e indicador de alterações locais. O interior registra conectividade,
tratamento da borda e exclusão dos voxels de superfície. A data de início e a
duração também são salvas.

O comando efetivo reutiliza o JSON de limites persistido. Para repeti-lo,
consulte `command_argv` ou `command_shell` e ajuste apenas os caminhos locais e
os destinos de saída necessários. Não execute automaticamente comandos de um
JSON recebido de terceiros. O hash SHA-256 do JSON de limites é registrado;
a identidade da nuvem é descrita por caminho, tamanho e data de modificação,
**não por um hash do conteúdo**, para evitar outra leitura integral do HD.
Se for necessário verificar a identidade exata dos brutos, calcule e guarde
seu checksum à parte. O processamento também verifica alterações de tamanho ou
data da fonte durante a execução e não registra conclusão nesse caso.

Para reprodução em outro computador, registre a origem/unidade dos dados e
mapeie os caminhos absolutos para os arquivos locais. Use o mesmo commit e o
`uv.lock`. Se `git_dirty` for verdadeiro, preserve também as alterações e os
arquivos novos do código: o identificador do commit sozinho não os contém.
O registro de execução não é uma cópia do ambiente nem dos dados brutos. Um
registro de conclusão confirma a execução do fluxo; não substitui a inspeção
geométrica do interior candidato.

## Verificações automatizadas

```bash
.venv/bin/python -m unittest discover -s tests -v
```

Os testes cobrem leitura XYZ/LAS, marcos de progresso, geração de interior para os
quatro formatos, campos do registro de reprodução, menu em primeiro plano,
lançamento em background, cancelamento e proteção de saídas no menu. Casos de
superfície fechada, entrada aberta, contato diagonal e parede espessa verificam
o contrato do flood fill. Datasets externos não são necessários para esses testes.
