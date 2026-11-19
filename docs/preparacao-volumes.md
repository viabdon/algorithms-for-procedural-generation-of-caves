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
sem ler os pontos. A opção **3** roda o processamento em CPU após digitar
`PROCESSAR`. A opção **4** abre três fatias ortogonais pela semente, usando
a pasta da execução.

### Propor e extrair recortes pela linha central

1. Copie o [modelo de planejamento](../configs/crops/plan.template.json) e
   informe a nuvem, a linha central no mesmo sistema de coordenadas, o número
   desejado em `count` e o lado físico do voxel em `voxel_size`. Para Racine,
   indique o arquivo `*_nodes_from_LBC.txt` com o `*_links_from_LBC.txt`
   correspondente na mesma pasta. O NPZ experimental do Elaphes também é
   aceito, com os campos `nodes_xyz` e `edges`. Os caminhos são absolutos
   ou relativos ao JSON.
2. Use a opção **5** e indique uma pasta nova. O planejador roda em CPU e
   lê a nuvem em dois passes, compartilhados entre todos os trechos. A saída
   contém `plan.json` e um subdiretório por proposta, com `cloud.ply` e
   `crop.json` quando há pontos para extrair.
3. Quando quiser visualizar, use a opção **6** sobre o `cloud.ply`. Ela
   salva um HTML interativo do Plotly com até 60.000 pontos espaçados
   uniformemente pelos registros do arquivo. Abra o HTML no navegador.
   A plotagem é independente e funciona com o PLY sozinho.
4. Revise o PLY, os alertas, os contornos e a semente do `crop.json`.
   Use a opção **2** para validar a configuração e, após a revisão, a
   opção **3** para voxelizar e aplicar o flood fill ao PLY. No caso de Elaphes,
   a etapa de recorte pode usar o grafo experimental no seu domínio de
   validade. A voxelização pelo menu exige que a caverna e o fold constem na
   auditoria.

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
  parte do exterior, com seis vizinhos por face. O ar candidato é a
  componente confinada que contém a semente. Vazamento até a semente,
  barreira na borda e tampas sem contato com a parede interrompem a execução.
- `batch_size` limita o lote de leitura. `progress_every` define a
  frequência do aviso em pontos lidos, com `0` para desativar.
  A nuvem é percorrida uma vez por recorte.

As saídas ficam em
`data/processed/reference_sections/<caverna>/<levantamento>/<recorte>/<resolucao>/`.
`surface.npz` contém a parede observada, `masks.npz` as duas tampas,
`interior.npz` o ar candidato em ZYX, e `run.json` a configuração,
partição, contagens e status `pending_review`. Revise se o interior se
mantém contínuo e estável frente a pequenas mudanças de corte e resolução.
O [planejamento dos recortes](planejamento-recortes-voxelizacao.md) descreve
a metodologia e os critérios ainda pendentes antes de usar os volumes no treino.

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
7. Execução em primeiro plano, em background ou cancelamento.

O menu mostra o comando equivalente antes de executar. Para preservar ensaios
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
