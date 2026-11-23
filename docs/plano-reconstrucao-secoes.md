# Plano de reconstrução de interiores por seções sucessivas

Registro iniciado em 15/11/2026. O piloto local de recortes, tampas e
diagnóstico de vazamentos está implementado. A validação geométrica dos
resultados e a reconstrução por interpolação de seções continuam em aberto.
O uso no treinamento depende dessa validação.

Detalhamento de 17/11/2026: o
[planejamento dos recortes e limites da voxelização](planejamento-recortes-voxelizacao.md)
define como separar os pontos de cada trecho, distinguir seleção/seções/grade,
preservar contexto e registrar os limites corretos. As funções do menu e
os arquivos de inspeção estão no [guia de preparação](preparacao-volumes.md).

O objetivo é obter interiores mais fiéis às paredes observadas e preservar
detalhes que se perdem ao colocar uma caverna inteira em uma grade pequena.
Referências melhores tornam o treinamento mais pertinente, mas sua qualidade
e o desempenho da GAN precisarão ser demonstrados separadamente.

Leitura complementar: [resumo simplificado do gargalo](resumo-gargalo-gan.md),
[auditoria dos dados atuais](auditoria/gan/README.md) e
[plano das redes](plano-redes-neurais.md).

## Evolução do piloto em Archamps

As grades globais 64³ perderam quase todo o ar inferido. Era preciso
reduzir o domínio físico antes de aumentar a resolução e saber em que
etapa surgia a falha. O piloto passou a selecionar trechos pela linha
central e fechar cada extremidade no contorno de sua seção. O exemplo
Archamps / PostEtroiture usou o LAS amostrado a 2 mm, seis recortes e voxel
de 16 cm. Esses parâmetros descrevem o ensaio. A comparação entre escalas
e cavernas ainda precisa ser feita.

Quatro recortes apresentaram alerta de cobertura em uma extremidade.
Os quatro alertas se concentram em dois cortes compartilhados entre
vizinhos. Os casos 003 e 004 passaram pela estimativa de
contorno e seguiram para a mesma grade 64³. O 004 recuperou 8.132 voxels
de ar candidato, cerca de 33,31 m³. Retirar qualquer uma das duas tampas
no ensaio fez a semente alcançar o exterior. Isso confirmou que o
fechamento depende das duas seções no controle.

O 003 leu 20.652.469 pontos do PLY e reteve 20.652.467 na voxelização.
As duas tampas tocavam a superfície. Mesmo assim, a semente estava livre
e ligada à borda. A aparência contínua dos pontos e o contato com a
tampa permitiam formular a hipótese de fechamento. A conectividade em
seis faces foi a verificação que a invalidou.

A primeira hipótese era uma fresta na junção de uma das tampas. Ensaiamos
cópias deslocadas para dentro da galeria em passos de 16 cm, até 96 cm,
com as originais presentes e também por substituição temporária. Nenhuma
posição ensaiada isolou o 003. Mesmo bloquear os dois planos de corte
inteiros deixou a semente conectada à borda da grade. Havia, portanto,
pelo menos uma rota lateral na grade. O teste ainda deixava em aberto a
localização da rota e a causa física da descontinuidade.

### Da dupla tampa à varredura de janelas

Mover as tampas temporariamente permite fazer uma pergunta diferente para
cada trecho. A rotina mantém as paredes voxelizadas, insere dois planos
digitais transversais e lança a inundação a partir de uma semente local.
Cada passo usa a mesma grade e o mesmo tamanho de voxel. Com o grafo e as
estações do plano disponíveis, a posição e a direção seguem a linha
central. Quando essa informação não pode ser reproduzida, o código usa
uma poligonal pelos dois cortes e a semente e registra a aproximação.

As primeiras janelas medem até oito voxels, com avanço de quatro. Para
cada janela com fuga, o código fixa uma extremidade e move a outra um
voxel por vez até a janela deixar de vazar ou restarem quatro passos ou
menos. Repete a partir da outra extremidade. Uma janela pode fechar
quando um plano cruza e cobre a própria abertura. Outra janela
sobreposta pode revelar a fuga. Esse comportamento motiva os testes
nos dois sentidos e impede assumir que o resultado é monotônico. As
faixas obtidas são regiões de investigação. Uma semente ocupada ou um
plano que recorta novamente a linha central invalida aquela sondagem.

O controle com os planos originais completos continua sendo o primeiro
teste de localização. Se esse controle isola a semente, o código também
testa as cópias dos contornos originais nas duas extremidades, até seis
voxels para dentro. As máscaras das tampas móveis são descartadas a
cada tentativa. Cada estado fica no relatório sem persistir volumes de
janelas intermediárias.

### Do caminho de fuga ao remendo

O flood fill responde se existe conexão. Para investigar **por onde**,
o código rastreia uma rota de menor custo entre a semente e a borda,
com custo uniforme e seis vizinhos. Rastreia a fuga no recorte inteiro
e nas janelas refinadas. Uma rota pode atravessar mais de um bin livre;
seu comprimento mínimo esclarece por onde a conexão é possível e
outras rotas ainda podem existir. [SciPy, preenchimento por conectividade à borda](https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.binary_fill_holes.html) · [scikit-image, custo mínimo e rastreamento](https://scikit-image.org/docs/stable/api/skimage.graph.html#skimage.graph.MCP)

A comparação é local. O PLY e a nuvem de origem, quando disponível,
são lidos em lotes e projetados nos **mesmos bins**, com a origem e a
escala da execução. As contagens com e sem a seleção do recorte ajudam
a distinguir um ponto removido no preparo de uma célula sem registro
na fonte. A inspeção no Plotly sobrepõe uma pequena amostra da nuvem às
fatias voxelizadas perto da rota. É possível ampliar uma região
específica e alternar cada camada.

Para propor um remendo, a célula deve estar livre, perto do caminho e
da parede, dentro da seleção e longe da borda da grade. Duas medidas
originais no bin dentro da seleção podem apoiar a restauração. Sem
esse apoio direto, uma operação de fechamento de uma célula propõe
voxels e a continuidade precisa ser sustentada por pares de vizinhos
em lados opostos. Uma falha lateral exige dois pares de parede
observada. Na junção da tampa, exige-se um par observado e dois pares
na barreira composta de parede e tampa. Os pares podem incluir
diagonais, enquanto o flood fill continua por faces. O reparo fica
separado em `masks.npz`.

Com o candidato mais apoiado que esteja na rota, o código bloqueia um
voxel e verifica se a semente ainda alcança a borda. Se houver outra
rota, repete até o limite de 12 voxels. Depois retira sucessivamente
remendos redundantes. O resultado só é publicado quando o recorte
inteiro fecha com as tampas originais e o reparo, e as sementes de
janelas anteriormente isoladas continuam no interior recuperado.
O processo protege a linha central e os vazios já isolados. Um
retorno ou outra passagem próximos, quando sinalizados no plano,
deixam o reparo para revisão. O limite de 12 voxels é um orçamento
conservador do piloto e precisa ser avaliado em outras escalas.

Cada verificação elimina uma interpretação diferente. O contato
inicial evita testar uma tampa solta. Os planos completos separam
hipóteses sobre corte e paredes laterais. A varredura reduz a região
suspeita. A comparação dos bins verifica se existem pontos no local.
O último flood fill confirma que a barreira digital completa fechou
sem as tampas móveis. Nenhum desses testes determina sozinho se uma
abertura da nuvem é uma passagem real. Os casos com sucesso continuam
com status `pending_review`, e os casos sem reparo sustentado guardam
apenas o diagnóstico, sem publicar um interior.

### Resultado da rechecagem do 003 e controle 004

Com a linha central do plano e a origem preservada, a busca realizou
23 sondagens no 003. Treze isolaram a semente local e dez detectaram
fuga. Entre as janelas refinadas com fuga, a menor abrangeu o intervalo
de **3,20 a 3,84 m** a partir do primeiro corte. Um único voxel em
**ZYX `[22, 25, 30]`** interrompeu a rota na execução completa. O bin
tinha **zero pontos no PLY e zero no LAS original amostrado a 2 mm**,
com três pares opostos de vizinhos de parede. Portanto, o reparo desse
bin veio de continuidade inferida. A comparação nos mesmos bins não
encontrou evidência de que a filtragem tivesse removido um ponto que
preencheria a célula. A origem física do vão continua em aberto.

Com as tampas móveis retiradas, obtivemos **7.502 voxels de ar
candidato, cerca de 30,73 m³**, preservando as 13 sementes de janelas
isoladas. Uma reclassificação independente da grade confirmou que o
003 volta a vazar quando se remove esse único voxel de reparo. Essa
checagem agora roda na própria pipeline e pode ser repetida nos NPZs
salvos. O interior permanece pendente de revisão geométrica. O controle 004 foi
reexecutado com a mesma versão do fluxo e reproduziu, voxel a voxel, os
8.132 voxels do resultado anterior, sem acionar o reparo.

Para reproduzir a afirmação, compare as linhas `outside_fill_without_repair`,
`outside_fill_final` e `remove_repair_voxel` em `diagnostics/checks.csv`.
A primeira e a terceira registram `exterior`. A segunda registra `interior`.
O algoritmo das ablações usa a inundação a partir da borda e compara
a componente com o ar encontrado pela busca a partir da semente.
O `bins.csv` registra os dois zeros medidos, o apoio dos vizinhos e
o voxel publicado. `probes.csv` e `paths.csv` ligam essa decisão aos
testes por janela e à trajetória. A [reprodução em CLI](preparacao-volumes.md#relatorio-por-recorte-e-reproducao)
repete as ablações sem recontar pontos. Uma nova voxelização com o mesmo
recorte e a mesma fonte repete a investigação dos bins.

O ensaio sintético cobre uma abertura de um voxel, uma abertura maior
que exige revisão, uma falha no contorno de extremidade e uma leitura
LAS georreferenciada com dois pontos originais no bin ausente do PLY.
Esses casos testam a implementação. A comparação de resoluções, a
revisão da continuidade e a avaliação em outras galerias ainda são
necessárias para recomendar os parâmetros como metodologia geral.

### Contorno da tampa inicial do 001

Em três vistas do Plotly, o contorno laranja atravessa a região entre a
galeria principal e uma extensão lateral da nuvem. A extensão tem
aparência de ramificação e parece se fechar em pelo menos uma das vistas.
As imagens permitem identificar o contorno estendido, mas a conectividade
e o fechamento físico da extensão ainda precisam de verificação na nuvem.

O `crop.json` e a legenda do Plotly confirmam que esse contorno é a
**tampa inicial do 001**, na posição **0,16 m** ao longo da linha central.
Ela foi estimada com **16 de 16 faixas angulares**. A tampa final do
mesmo recorte continua sem contorno no corte **001/002**, a **8,76 m**,
com **11 de 16 faixas**. São dois problemas distintos no mesmo recorte.

A hipótese é que pontos da galeria e da extensão lateral foram reunidos
na faixa da mesma seção. O ajuste atual projeta esses pontos do LAS no
plano, usa o percentil 75 das distâncias em cada faixa angular e liga os
raios numa única volta. Quando há superfícies a diferentes distâncias na
mesma direção, pontos mais afastados podem alongar alguns raios e
estender o contorno até outra abertura. A cobertura angular mede presença
de pontos por direção. Falta verificar se esses pontos sustentam o
contorno da mesma passagem. A extensão do contorno já aparece antes da
voxelização.

### Limite 005/006 sem tampas

A inspeção visual confirmou que o 005 exibe apenas a tampa inicial e o
006 apenas a final. Os dois arquivos `crop.json` têm o mesmo corte a
**42,34 m** na linha central, com **11 de 16 faixas angulares** sustentadas.
O planejador deixou `polygon_uv` vazio no final do 005 e no início do 006,
as duas extremidades que usam esse corte. A prévia reflete os contornos
gerados no plano.

A extremidade fica sem a barreira prevista. Como a etapa de voxelização
exige os dois contornos, o flood fill e o reparo local ainda não foram
testados nesses trechos. A falha confirmada ocorreu na estimativa da
seção, antes de verificar o fechamento da grade.

A origem da baixa cobertura continua pendente. A faixa pode ter trechos
com poucos pontos no LAS, ou a escolha do plano e a seleção dos pontos
podem ter deixado parte da passagem fora da estimativa. O ensaio deverá
comparar as faixas angulares sustentadas na nuvem original e nos pontos
selecionados para a seção, usando a mesma posição e orientação. Isso
ajudará a distinguir falta de observações na faixa de efeitos da seleção
ou do corte. A evidência atual ainda não confirma a extensão lateral
observada na tampa inicial do 001.

### Arquivos de referência do piloto

A inspeção usou a execução local em
`data/processed/crop_plans/archamps/PostEtroiture/holdout_indian_tunnel/piloto_2mm_6_trechos/`.
O `plan.json` identifica a nuvem de 2 mm, a linha central, o fold e o
tamanho do voxel. Nas pastas `ramo_001_001`, `ramo_001_005` e
`ramo_001_006`, conferir `proposal.cut_stations` e
`proposal.section_bins_supported` nos `crop.json` e os contornos em
`preview_individual_tampas.html`. Esses artefatos permanecem locais.
Para recriar as vistas a partir dos PLYs, usar a opção 6 no
[menu de preparação](preparacao-volumes.md#propor-e-extrair-recortes-pela-linha-central).

### Próximo ensaio: selecionar a abertura e buscar posições melhores

O próximo ensaio prioriza as duas seções de PostEtroiture que ficaram com
11 de 16 faixas angulares sustentadas, entre os recortes 001/002 e 005/006.
Sem um contorno inicial nesses cortes, o reparo local de vazamentos ainda
não entra em ação. A busca planejada acontece antes da extração final da
nuvem. Ela desloca a seção ao longo da linha central em passos de quatro
voxels, recalcula o contorno a partir do LAS e refina em passos de um voxel
perto de um candidato aceitável. A triagem também deverá verificar se o
contorno acompanha a abertura da galeria de interesse. O 001 inicial
servirá como caso de controle para detectar uma extensão indevida mesmo
com cobertura angular completa.

Essa etapa é inspirada na varredura por janelas do 003. Lá, os planos são
barreiras temporárias usadas para localizar uma fuga na grade. Aqui, cada
posição serve para avaliar um contorno observado e escolher um novo
limite compartilhado. A evidência será registrada em duas etapas, com
cobertura angular na escolha da seção e conectividade após reextrair e
voxelizar os vizinhos. O lote de Archamps fica para depois desse ensaio.
[Detalhes da busca e critérios de escolha](planejamento-recortes-voxelizacao.md#busca-de-cortes-com-melhor-cobertura)

## Abordagem escolhida

Trabalhar com um trecho de galeria por vez. Percorrer o trecho com cortes
transversais sucessivos, identificar o contorno interno em cada corte e
construir o espaço entre esses contornos. Fechar as duas extremidades do
recorte com **tampas computacionais**, para definir um domínio finito e
permitir distinguir seu interior do exterior.

As tampas representam onde o estudo cortou a galeria. Não representam paredes
naturais, desabamentos ou fins de passagem. As entradas da caverna real podem
continuar abertas; o fechamento é um recurso de preparação do recorte.

O volume pode ser construído diretamente em voxels a partir das seções.
Uma malha pode auxiliar a inspeção, mas não será uma etapa global obrigatória.
Converter as grades atuais em malha não recuperaria o interior que elas perderam.

## 1. Piloto e escolha do trecho

- [ ] Escolher inicialmente um trecho curto com boa observação de piso, teto
  e paredes, evitando bifurcações e grandes regiões sem pontos.
- [ ] Usar um trecho da partição de treino para desenvolver os parâmetros do
  método. Manter o teste reservado para a avaliação posterior.
- [ ] Conferir os produtos disponíveis: nuvem, linha central, malha oficial e
  modelos de piso/teto. Usá-los como apoio, sem presumir fechamento ou exatidão
  nas regiões que os próprios autores reconstruíram ou removeram.
- [ ] Registrar caverna, levantamento, limites do recorte e justificativa da
  seleção, incluindo trechos rejeitados e motivo da rejeição.

Vários recortes, inclusive sobrepostos, de uma caverna permanecem no mesmo
grupo de treino, validação ou teste. Eles aumentam as observações locais, mas
não o número de cavernas independentes. Esse piloto estudará geometria local
de galerias; não validará a topologia de uma caverna inteira.

## 2. Preservar a precisão antes da voxelização

- [ ] Reler os dados originais e retirar uma origem local antes de converter
  coordenadas para `float32`. No LAS, manter precisão suficiente ao aplicar
  escala e offset e ao calcular essa translação.
- [ ] Preservar origem, unidade, sistema de coordenadas e transformação usada,
  permitindo recolocar o recorte na nuvem original.
- [ ] Conferir as dimensões do trecho antes e depois da transformação.

Na voxelização global, arredondar coordenadas georreferenciadas para
`float32` na ordem de 6,56 milhões reduz a precisão para um espaçamento
de 0,5 m em Archamps. O piloto de recortes lê o LAS em coordenadas locais
com `float64` antes de discretizar, tanto na extração como na comparação
local com a fonte. Isso preserva a resolução necessária para contar os
pontos nos mesmos bins. A contribuição desse arredondamento para os
resultados globais históricos continua sem medição isolada.

## 3. Extrair e revisar as seções sucessivas

- [ ] Definir uma linha de referência ao longo da galeria, aproveitando uma
  linha central disponível ou uma marcação revisada manualmente.
- [ ] Criar planos transversais aproximadamente perpendiculares à direção
  local, mantendo orientação consistente entre cortes consecutivos.
- [ ] Reunir os pontos próximos a cada plano e examinar o contorno de piso,
  teto e paredes na seção. Registrar distância entre seções e espessura da
  faixa de pontos usada em cada uma.
- [ ] Ajustar e revisar os contornos; aproximar os cortes onde a forma mudar
  rapidamente. Não há espaçamento universal já validado.
- [ ] Marcar lacunas, correções manuais e partes interpoladas. Rejeitar uma
  seção quando não houver suporte suficiente para delimitar seu interior.

O contorno precisa acompanhar a forma observada, incluindo estreitamentos.
Não usar um envoltório convexo global que una passagens distintas, nem
substituir automaticamente todas as seções por círculos. Uma simplificação
geométrica pode ser um controle separado, mas não deve ser apresentada como
detalhe medido. Bifurcações e seções com múltiplas passagens ficam para uma
extensão, após validar o piloto simples.

## 4. Construir o volume e aplicar as tampas

- [ ] Preencher o interior dos contornos e interpolar sua evolução entre
  seções, verificando se não surgem bloqueios, pontes ou alargamentos indevidos.
- [ ] Inserir as tampas nos planos inicial e final do recorte, respeitando
  os respectivos contornos.
- [ ] Verificar a separação entre interior e exterior no domínio recortado;
  o fechamento pode ser usado para conferir a classificação por preenchimento.
- [ ] Preservar separadamente as paredes apoiadas em observações, as tampas
  artificiais e as regiões reconstruídas com incerteza.

Tampar as extremidades não resolve uma grande falha no teto ou na parede
lateral. Essa região deve ser reconstruída de forma explícita e revisada,
permanecer desconhecida ou motivar a rejeição do recorte. Espaço não observado
não será automaticamente tratado como rocha ou como ar.

A classificação vale para a galeria delimitada nesse domínio; não prova que
todo espaço além dela seja rocha, nem exclui outras cavidades não observadas.
O resultado será uma **referência de interior inferido e revisado**, não uma
medição completa do vazio real.

## 5. Escolher a resolução pelo detalhe local

- [ ] Definir o tamanho físico do voxel com base na largura e na altura das
  passagens que se deseja preservar, mantendo proporções espaciais.
- [ ] Reconstruir o mesmo trecho diretamente dos pontos em 128³ e 256³,
  comparando cortes, estreitamentos, volume e conectividade.
- [ ] Verificar se 64³ ainda preserva a geometria desse recorte para o treino;
  reduzir o tamanho físico do recorte ou revisar a arquitetura se necessário.
- [ ] Registrar resolução, tamanho do voxel e perda de detalhe em cada opção.

A comparação de resoluções é um experimento proposto, não uma escolha ótima
demonstrada. Uma grade 256³ da caverna inteira pode preservar menos detalhe
local que uma grade 64³ de um trecho pequeno. Ampliar os NPZ atuais por
interpolação não recupera pontos ou espessuras perdidos.

A resolução de preparação e inspeção não obriga a GAN a treinar na mesma
resolução. Sua saída, entretanto, deve continuar resolvendo os detalhes que
serão avaliados. Não treinar em uma versão reduzida que apague as passagens.

## 6. Verificar a fidelidade e aceitar ou rejeitar o recorte

- [ ] Sobrepor as seções reconstruídas aos pontos originais e registrar
  desvios em unidades conhecidas, distinguindo regiões observadas e inferidas.
- [ ] Inspecionar cortes entre as seções usadas na construção, procurando
  distorções introduzidas pela interpolação.
- [ ] Conferir continuidade, largura/altura dos gargalos e ausência de
  passagens criadas ou fechadas sem suporte nos dados.
- [ ] Medir o efeito de pequenas mudanças no espaçamento dos cortes, na
  resolução e nos fechamentos. Mudanças grandes no interior indicam fragilidade.
- [ ] Quantificar e mostrar as regiões incertas e artificiais; registrar o
  responsável pela revisão e as razões para aceitar ou rejeitar cada recorte.

Os limites de tolerância serão definidos no piloto, com justificativa e antes
da avaliação dos recortes de teste. Passar a triagem mínima do loader atual
não basta para aprovar a fidelidade. Sem interior real completamente conhecido,
essa validação poderá demonstrar aderência às observações e estabilidade do
método, mas não exatidão em regiões sem dados.

## 7. Preparar a integração com a GAN

- [ ] Salvar o ar inferido em ZYX, mantendo `True = ar`, e metadados da origem,
  recorte, transformação, seções, resolução e decisões de fechamento.
- [ ] Salvar máscaras auxiliares de tampas e incerteza. O `Volume3D` booleano
  sozinho não representa uma terceira classe de espaço desconhecido.
- [ ] Adaptar manifesto, auditoria e loader para identificar corretamente o
  novo método de inferência. Não atribuir a ele a proveniência de flood fill
  das referências atuais se o interior foi construído pelas seções.
- [ ] Impedir que regiões desconhecidas entrem silenciosamente como alvos
  binários. Se forem necessárias máscaras durante o treino, implementar e
  testar um protocolo compatível com o discriminador antes de usar os recortes.
- [ ] Definir como limites artificiais serão tratados no treino e na avaliação,
  com política consistente para referências e saídas geradas. A rede não deve
  aprender que toda galeria real termina nas tampas do recorte.
- [ ] Gerar novos hashes e uma nova versão do conjunto, preservando a separação
  por caverna. Não reutilizar os manifestos antigos como se os dados fossem iguais.
- [ ] Repetir auditoria e preflight, medir memória de um passo completo no Colab
  e somente então planejar o primeiro experimento de treinamento.

## Entregáveis e condição para avançar

O piloto deverá entregar: recorte identificado, seções revisadas, referência
voxelizada, máscaras de tampas/incerteza, comparação de resoluções e um relato
curto de aderência às observações, estabilidade e limitações.

Avançar para montar o conjunto de treino quando o piloto preservar uma
galeria reconhecível e contínua, com detalhes resolvidos e regiões inferidas
documentadas. Depois, aplicar o procedimento às demais fontes com os critérios
já definidos. Se os trechos exigirem invenção extensa de paredes, revisar a
escolha dos dados ou restringir o objetivo à geometria observável.

A GAN incondicional já planejada aprenderá a gerar **novas galerias semelhantes
às referências**. Reconstruir uma galeria específica a partir de sua nuvem é
outra tarefa e exigiria rever a entrada e o objetivo da rede. A reconstrução
por seções pertence, neste plano, à preparação e validação dos dados.
