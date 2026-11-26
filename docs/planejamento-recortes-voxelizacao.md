# Planejamento dos recortes para voxelizar galerias separadamente

O [piloto local](preparacao-volumes.md#piloto-local-de-recortes-por-galeria)
propõe e extrai recortes pela linha central, com conformação das tampas e
revisão dos trechos antes de voxelizar e aplicar flood fill em CPU. O menu
também oferece configuração manual e prévia Plotly independente a partir do
PLY. Quando o levantamento não fornece grafo, o menu pode estimá-lo no
mesmo plano pela sequência de contração laplaciana e árvore geradora mínima
do ensaio exploratório do Elaphes. O piloto agora diagnostica fugas com duas
tampas móveis e valida remendos locais em uma máscara separada. Os primeiros
resultados reais estão registrados na
[evolução do piloto em Archamps](plano-reconstrucao-secoes.md#evolução-do-piloto-em-archamps).
A reconstrução mais ampla por interpolação e a validação geométrica
sistemática continuam em aberto.

O *Karst Conduit Catalogue* (DOI `10.5194/essd-2025-194`, §§2.3, 2.7 e 3.3)
documenta limpeza, linhas centrais e identificação de ramos. O estudo
*Speleogenesis geometry and topology of caves* (§3) descreve revisão manual da
conectividade de levantamentos. O fechamento com tampas e a inferência de ar
no piloto são adaptações experimentais do projeto.

## Busca de cortes com melhor cobertura

O piloto de Archamps ampliou a busca pela posição dos cortes quando a
seção original e os ajustes locais de um voxel deixaram o contorno sem
suporte suficiente. A tabela registra o ponto de partida no plano de
PostEtroiture a 2 mm, com voxels de 16 cm.

| Posição ao longo da linha central | Extremidades afetadas | Cobertura registrada |
| --- | --- | --- |
| 8,76 m | Final do 001 e início do 002 | 11 de 16 faixas |
| 42,34 m | Final do 005 e início do 006 | 11 de 16 faixas |

A inspeção do 001 acrescentou um segundo caso de teste. Sua tampa inicial,
a **0,16 m**, tem **16 de 16 faixas** e mesmo assim se estende da galeria
principal até a região de uma provável ramificação lateral. A hipótese é
que o ajuste radial reuniu pontos de superfícies diferentes numa só
volta. A extensão foi observada na prévia dos pontos do PLY, antes da
voxelização. [Registro da inspeção do 001](plano-reconstrucao-secoes.md#contorno-da-tampa-inicial-do-001)

No limite **005/006**, a inspeção confirmou a ausência da tampa final
do 005 e da inicial do 006. Os dois JSONs originais registravam a mesma
posição e deixavam o contorno em branco por cobertura insuficiente.
Antes de deslocar esse limite, comparar a cobertura angular na faixa do LAS original e
nos pontos selecionados para ajustar o contorno. A comparação deve usar
o mesmo plano para investigar se a cobertura já era baixa na faixa
observada ou se diminuiu durante a seleção. [Registro da inspeção do 005/006](plano-reconstrucao-secoes.md#limite-005006-sem-tampas)

### Busca proposta

1. **Explorar os dois sentidos.** Em um corte sem contorno válido, testar
   posições a cada **quatro voxels** de distância ao longo da linha central.
   Para o piloto atual, o passo equivale a **64 cm**. Limitar a busca ao
   intervalo do ramo que mantém a ordem dos cortes e o comprimento mínimo
   dos dois trechos. Registrar a distância máxima testada. O alcance ainda
   será definido no ensaio.
2. **Reestimar o contorno da abertura de interesse.** Calcular a direção
   local da linha central, formar o plano e projetar os pontos na sua
   vizinhança. Usar a interseção da linha central como referência para
   identificar a abertura que continua o trecho. Como hipótese a testar,
   agrupar os pontos na seção e nas fatias imediatamente vizinhas para
   distinguir um contorno local de um prolongamento lateral ou de outra
   abertura. Verificar se o contorno se mantém nas fatias vizinhas antes de
   preencher setores angulares faltantes. Se duas interpretações continuarem
   plausíveis, marcar a seção para inspeção ou buscar outra posição.
   Aplicar a triagem de pelo menos **14 de 16 faixas angulares** com
   suporte e lacunas isoladas ao contorno da abertura selecionada.
3. **Refinar o deslocamento.** Quando uma posição passar na triagem,
   testar as posições intermediárias no intervalo vizinho em passos de
   **um voxel**, ou **16 cm** no piloto. Entre as posições aprovadas,
   escolher a mais próxima do corte original. Se nenhuma atender ao critério
   dentro da faixa permitida, registrar as sondagens e manter o corte
   pendente de revisão.
4. **Aplicar o mesmo corte aos dois vizinhos.** Reextrair ambos do LAS
   com o mesmo plano e contorno, usando normais voltadas para o interior
   de cada trecho. Se o corte B mudar para B′, os intervalos A–B e B–C
   passam a ser A–B′ e B′–C. A e C ficam nas mesmas estações. Um ajuste
   explícito deve manter a ordem dos cortes e pelo menos oito voxels
   entre eles, ou 1,28 m a 16 cm. Recalcular a caixa, a margem e a grade
   de cada vizinho na mesma escala. Preservar o plano inicial como
   controle e salvar a variante em um novo plano dentro do mesmo fold.
5. **Confirmar o fechamento.** Voxelizar os vizinhos e verificar o resultado
   pelo flood fill e pelos relatórios da pipeline. Registrar separadamente
   a qualidade do contorno e a conectividade do interior. O 003 passou na
   triagem angular e apresentou uma fuga lateral, enquanto o 004 fechou no
   ensaio original. Ambos servem de controle para preservar as seções
   consistentes. Usar a tampa inicial do 001 para conferir se o critério
   geométrico detecta a extensão lateral mesmo com 16 faixas cobertas.

Para cada corte deslocado, guardar a posição original, os offsets testados,
a cobertura, a continuidade angular, possíveis grupos laterais e o
motivo da escolha. Antes do ensaio real, testar um caso sintético que
melhora com o deslocamento, um em que todas as posições permanecem
insuficientes e outro em que duas aberturas na faixa da seção aparentam
boa cobertura. Conferir a fronteira compartilhada e a ordem dos cortes.
O objetivo é medir quantos limites ganham um contorno sustentado
e quantos trechos fecham depois, incluindo os casos que seguem pendentes.
O ensaio termina quando os dois limites compartilhados e a tampa inicial
do 001 tiverem uma decisão registrada. Nas seções aprovadas, anexar
o resultado da voxelização dos recortes afetados. Nas seções pendentes,
registrar a faixa explorada e a razão da rejeição.

No plano revisado de Archamps, o corte 001/002 passou de 8,76 m para
9,24 m e o corte 005/006 passou de 42,34 m para 43,62 m. Os PLYs foram
reextraídos e as duas tampas de cada corte passaram a ter contorno.
O histórico detalha o fechamento posterior e os lotes dos demais
levantamentos.
[Ajustes aplicados em Archamps](plano-reconstrucao-secoes.md#como-os-ajustes-foram-aplicados-no-planejador) ·
[Histórico dos lotes](auditoria/gan/historico-voxelizacao.md)

### Revisão de contornos no planejador

A opção **5** da Datastream executa a revisão quando
`section_search_radius_voxels` é maior que zero. O modelo de plano
usa **8 voxels**. Configurações antigas sem esse campo e configurações
com valor zero usam o planejamento inicial. A revisão acrescenta uma
leitura da nuvem original antes de extrair os PLYs.

1. Em cada estação candidata, projetar a faixa de dois voxels de
   cada lado do plano. O alcance transversal `section_search_context`
   usa as unidades da nuvem e tem como padrão o maior valor entre
   cinco unidades e quatro voxels.
2. Contar os pontos nos 16 setores antes e depois de aplicar a
   atribuição ao ramo e a proximidade de quatro voxels ao longo
   da linha central. Em ambas as contagens, registrar quantos
   pontos restam após exigir raio maior que um voxel. Essa comparação
   distingue falta de observação de perda de suporte nos filtros,
   como ocorreu no 005/006.
3. Ajustar o contorno pelo percentil 75 por setor em uma amostra
   dos pontos filtrados, com o modo de componentes conectados.
   A estação precisa ter um único componente com pelo menos
   14 setores sustentados e lacunas angulares isoladas. A revisão
   tenta a estação atual primeiro e depois deslocamentos crescentes,
   um voxel por vez em ambas as direções. Entre estações válidas,
   usa a de menor deslocamento compatível com o espaçamento dos vizinhos.
4. Registrar em `plan.json`, campo `section_reviews`, a estação
   inicial, a adotada, as contagens e o desfecho de cada tentativa.
   Cortes fixados em `section_overrides` entram na comparação na
   estação indicada e preservam a configuração manual. Se a busca
   ficar sem um contorno aceito, o corte segue pendente. Os dois
   recortes de um corte recuperado recebem a mesma seção e são
   extraídos com o novo limite.

## Separação dos dados antes dos recortes

A unidade independente continua sendo a **caverna**, não o trecho, a densidade
da nuvem ou a resolução. Primeiro atribuir cada caverna a treino, validação ou
teste no fold escolhido. Depois extrair seus recortes, mantendo a atribuição
em todas as versões e aumentos. Trechos vizinhos ou sobrepostos não poderão
ser distribuídos entre partições diferentes.

Usar uma galeria de treino para o piloto. Escolher ali os parâmetros de
seleção, seções, margens, resolução e aceitação; registrá-los antes de aplicar
o procedimento aos dados reservados. A inspeção do teste poderá aprovar ou
rejeitar recortes segundo os critérios congelados, sem ajustar o método para
melhorar o resultado da GAN.

Mais recortes oferecem observações locais, sem transformar quatro cavernas
em dezenas de fontes independentes. Registrar quantidade, comprimento e
sobreposição por fonte. No loader futuro, definir amostragem por caverna e
depois por trecho, para uma fonte não dominar só por ter mais arquivos.

## Limites com funções diferentes

| Limite | Função | O que não significa |
| --- | --- | --- |
| Bounds da nuvem original | Identificar a extensão do levantamento | Não delimitam o interior de um trecho |
| Região de seleção dos pontos | Separar uma passagem com contexto ao redor dos cortes | Sua caixa não é uma parede da galeria |
| Seções inicial e final | Definir início/fim do trecho e posição das tampas | Não são necessariamente fins naturais |
| Bounds da grade de saída | Acomodar paredes, ar, tampas e margem exterior | Não devem cortar a geometria ou substituir tampas |

O argumento `--bounds` da voxelização global define os limites para
normalização da nuvem inteira. Use a opção **Preparar recortes por galeria**
do menu para filtrar os pontos antes de voxelizar.

## 1. Definir o trecho pela galeria

1. Identificar a passagem e sua linha central, usando o produto do dataset ou
   uma marcação revisada. Evitar inicialmente bifurcações, retornos acentuados
   e passagens vizinhas difíceis de separar.
2. Marcar início/fim por distância ao longo da linha, com identificadores de
   ramo e seção. Guardar também as posições nas coordenadas originais.
3. Posicionar os planos aproximadamente perpendiculares à direção local da
   galeria. Escolher extremidades com piso, teto e paredes suficientemente
   observados para delimitar um contorno completo.
4. Conferir o trecho entre os planos, inclusive gargalos. Encurtar ou rejeitar
   o recorte se ele cortar outra passagem ou terminar em uma bifurcação.

Uma caixa XYZ ajuda a buscar candidatos, mas não basta para separar galerias
próximas. A seleção final deve respeitar ramo, progressão ao longo da galeria
e seções revisadas. Associar cada ponto apenas à linha central mais próxima
pode misturar passagens; associações ambíguas exigem revisão ou rejeição.
Não preencher o espaço entre ramos como se fosse ar.

## 2. Separar pontos com contexto suficiente

Ler a nuvem original em lotes e selecionar os pontos de cada trecho sem
carregar todo o levantamento na RAM. Uma primeira passagem poderá levantar
estatísticas e revisar limites; outra fará a extração/voxelização com a
configuração congelada. Cache por passagem é uma otimização futura; não é
obrigatório copiar toda a nuvem para cada recorte.

Preservar três regiões distintas:

- **Núcleo:** trecho entre as seções inicial/final que produzirá o exemplo.
- **Contexto:** faixa antes/depois dos cortes e ao redor das paredes para
  ajustar seções e conferir continuidade. Não entra automaticamente no
  interior final.
- **Exterior da grade:** margem ao redor da geometria reconstruída para que
  o limite do array não participe do fechamento.

Calibrar no piloto os tamanhos das faixas de contexto e da margem, registrando
unidades físicas e voxels. Conferir se nenhuma parede foi truncada lateralmente.
Não confundir faixa de seleção, espessura da seção e margem exterior sob um
mesmo parâmetro genérico de padding.

## 3. Coordenadas locais e grade explícita

No LAS, o piloto decodifica coordenadas relativas à origem da grade em
`float64`, preservando o detalhe local. Guardar origem e eventual
rotação rígida invertível, sem esticar eixos. O recorte deve poder ser
recolocado sobre a nuvem original; posições e normais dos planos usam a
mesma transformação.

O piloto especifica a grade por origem local, shape ZYX e tamanho físico de
voxel. Usa células com mínimo inclusivo, máximo exclusivo,
centro a meio voxel e índice por
`floor((ponto - origem_da_grade) / tamanho_do_voxel)`, antes de trocar XYZ
por ZYX. A voxelização global continua usando o encaixe por arredondamento
e spans `N-1` do normalizador.

A extração usa os dois planos para filtrar os pontos. Os vizinhos
usam lados opostos do plano compartilhado, com uma pequena tolerância
numérica que pode preservar pontos sobre o limite em ambos os PLYs.
Para ajustar o contorno, é possível consultar uma faixa de pontos nos
dois lados do plano. Essa faixa serve de contexto para o ajuste. O
plano continua sendo a fronteira do volume de cada vizinho.

### Como a grade cresce ao mover um corte

Para cada eixo, a caixa do recorte abrange os pontos retidos, os
vértices das tampas e a semente. O planejador acrescenta a margem
`padding_voxels` de cada lado, divide a extensão resultante pelo
tamanho do voxel e arredonda para cima. A grade tem pelo menos
**64 células por eixo**. A margem padrão é de **dois voxels por lado**.
Um ponto mais externo ou um contorno mais largo pode aumentar a
dimensão se a geometria com margem ultrapassar o espaço disponível.

Em Archamps PostEtroiture, o `ramo_001_005` tinha aproximadamente
**9,18 m** de extensão em X e cabia em `64×64×64`. Quando o corte
005/006 foi de 42,34 m para 43,62 m, a nova tampa final passou a
definir o limite inferior em X. A extensão nesse eixo chegou a
**10,12 m**. Com os **0,64 m** de margem total, foram necessários
**68 voxels de 16 cm**. A dimensão maior aparece por último em
`64×64×68` porque a ordem da grade é **ZYX**.

Esse cálculo ocorre durante o planejamento. Ao voxelizar um
`crop.json` com grade já definida, a Datastream verifica a margem
e registra erro se a parede ou uma tampa tocar a borda.
[Cálculo da grade no planejador](../src/cavegen/datastream/crop_planner.py)

Ao comparar 64³/128³/256³, manter domínio físico, seções e tampas e mudar a
amostragem da grade. Para o treino, preferir tamanho físico de voxel e domínio
comparáveis, em vez de comprimir cada trecho independentemente até ocupar
64³. Se não couber, rever o trecho ou declarar outra condição de escala.
Não normalizar cada eixo separadamente para fazê-lo caber.

## 4. Posicionar e conferir as tampas

Salvar para cada extremidade: posição e normal do plano, orientação da seção
e contorno interno revisado. A tampa acompanha esse contorno, não o retângulo
da caixa de seleção. No piloto simples, as meias-regiões dos dois planos
ajudam a cortar as extremidades; a superfície lateral continua definida pelas
seções. Se a curvatura fizer os planos cortarem outra parte do trecho,
subdividi-lo.

Unir as tampas às paredes sem vazamentos nem invasão do núcleo. Colocá-las
dentro da grade, com margem exterior além delas, sem usar a face do array
para fechar o flood fill. Registrar a espessura de rasterização e verificá-la
em cada resolução, sem alargar a passagem ou bloquear uma seção interna.

Mostrar separadamente parede observada, tampas, reparo local e ar inferido.
O teste com os planos completos distingue uma rota lateral de uma que
depende dos cortes. As tampas móveis restringem a região a investigar
quando a semente ainda se conecta ao exterior. Para reparos, exigir
evidência nos bins e revalidar o recorte inteiro com as tampas originais.
Áreas sem suporte permanecem para revisão. O exterior da galeria
delimitada pode conter cavidades além do trecho estudado.

### Busca automática quando a semente cai na barreira

A opção **3** procura voxels livres dentro da seleção e dos dois
planos do recorte. O raio `seed_search_radius_voxels` é medido a
partir do voxel da semente original e vale quatro voxels por padrão,
ou 64 cm a 16 cm. O valor zero desativa a busca.

A primeira busca usa o flood fill a partir da borda para identificar
um componente interno único na vizinhança, em contato com as duas
tampas. A pipeline escolhe a posição mais próxima elegível e usa a
distância à barreira para desempatar. Se o trecho estiver aberto,
ela pode escolher uma semente provisória em um componente que fecha
entre dois planos temporários de uma janela local. A semente
provisória aciona o diagnóstico e as mesmas regras de reparo do
recorte inteiro, incluindo o bloqueio de fechamento automático em
passagens ambíguas.

Para salvar um volume com semente reposicionada, a reclassificação
pelo exterior precisa reproduzir a máscara de ar a partir da nova
posição e confirmar contato com as duas tampas originais. O
`crop.json` conserva a semente pedida. O `run.json` e o
`summary.csv` registram a busca, as posições e o deslocamento
quando há uma candidata. O resultado permanece pendente de revisão
geométrica. O ensaio anterior olhava apenas para interiores já
fechados e ficou sem candidata nos 14 casos avaliados.
[Ensaio anterior com as sementes](auditoria/gan/historico-voxelizacao.md#sementes-cortes-compartilhados-e-junções)

## 5. Manifesto e organização

O piloto identifica cada recorte pela caverna, levantamento, ID e resolução.
Uma execução manual bem-sucedida apresenta esta estrutura:

```text
data/processed/reference_sections/<caverna>/<levantamento>/<recorte>/
    <resolucao>/
        surface.npz
        interior.npz
        masks.npz
        run.json
        relatorio_volume/
            summary.csv
            checks.csv
    <resolucao>_sem_volume/
        <tentativa>/
            summary.csv
            checks.csv
```

Para recortes propostos, o caminho dos volumes também inclui o fold e o ID
do plano entre o levantamento e o recorte. A nuvem extraída e o grafo gerado
ficam no diretório do plano descrito no [guia do piloto](preparacao-volumes.md#propor-e-extrair-recortes-pela-linha-central).
Uma tentativa rejeitada guarda CSVs em `<resolucao>_sem_volume/<tentativa>/`
ao lado da pasta esperada para o volume. A opção 4 monta a visualização a
partir do NPZ local comprimido quando há busca por vazamento. As janelas
da busca ficam em memória. Ver o [guia de reprodução](preparacao-volumes.md#relatório-por-recorte-e-reprodução).

Para integrar o piloto ao treino, estender o manifesto para registrar:

- Fonte/hash disponível, caverna/grupo de independência, levantamento, ramo,
  recorte e atribuição ao fold. Hash ausente permanece pendente.
- Intervalo na linha central, limites de seleção, contexto, sobreposição com
  outros recortes e contagens de pontos lidos/retidos.
- Unidade, CRS, origem/rotação locais, bounds da grade, shape ZYX, tamanho do
  voxel e regra de inclusão dos pontos nos limites.
- Seções/contornos inicial e final, posições/normais/espessuras das tampas,
  máscaras, parâmetros de interpolação e regiões sem suporte.
- Método/versão de inferência, qualidade, revisão manual, aceitação/rejeição
  e motivo, com hashes das saídas.

Não reutilizar diretórios ou hashes dos volumes globais atuais. Adaptar
auditoria e loader ao novo método, sem rotulá-lo como o flood fill anterior.

## 6. Verificações antes de preparar dados de treino

Os testes sintéticos verificam a seleção por limites, a estabilidade entre
lotes, a precisão local do LAS, o fechamento pelas tampas, a busca por
janelas e o reparo de lacunas pequenas. Um vão largo deve manter o resultado
pendente, com o diagnóstico disponível. Nos próximos ensaios, conferir
associação em galerias próximas e a reconstrução nas regiões que exigirem
interpolação.

Nos trechos reais, conferir contornos contra a nuvem, continuidade, gargalos,
margem exterior e ausência de vazamentos nas tampas. Comparar pequenas
perturbações dos cortes e resoluções: mudanças grandes no interior indicam
fragilidade. Inspecionar também entre as seções, em unidades físicas, sem
considerar apenas contagem de voxels de ar ou conclusão do processamento.

Concluir o piloto com decisão documentada: aceito, precisa de revisão ou
rejeitado. Depois integrar máscaras e limites artificiais ao dataset da GAN e
gerar novos manifestos/partições, mantendo o grupo da caverna. A política de
bordas deve ser consistente entre referências e geração; tampas não são
evidência de fins naturais. Treino e medição de memória no Colab ficam para
depois da validação dos recortes.
