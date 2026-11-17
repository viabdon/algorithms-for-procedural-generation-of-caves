# Plano de reconstrução de interiores por seções sucessivas

Registro de 15/11/2026. Esta é a próxima abordagem escolhida para preparar
referências de galerias para a GAN. **O procedimento ainda será implementado
e validado; nenhum treinamento está autorizado nesta etapa.**

Detalhamento de 17/11/2026: o
[planejamento dos recortes e limites da voxelização](planejamento-recortes-voxelizacao.md)
define como separar os pontos de cada trecho, distinguir seleção/seções/grade,
preservar contexto e registrar os limites corretos. Essa especificação ainda
não é uma funcionalidade do menu de preparação.

O objetivo é obter interiores mais fiéis às paredes observadas e preservar
detalhes que se perdem ao colocar uma caverna inteira em uma grade pequena.
Referências melhores tornam o treinamento mais pertinente, mas sua qualidade
e o desempenho da GAN precisarão ser demonstrados separadamente.

Leitura complementar: [resumo simplificado do gargalo](resumo-gargalo-gan.md),
[auditoria dos dados atuais](auditoria/gan/README.md) e
[plano das redes](plano-redes-neurais.md).

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

O leitor LAS atual converte coordenadas georreferenciadas para `float32`
antes dessa translação. Na magnitude de uma coordenada de Archamps, cerca de
6,56 milhões, o espaçamento representável é de 0,5 unidade. A unidade desse
levantamento está registrada como metro. Isso pode eliminar detalhe antes
da grade; sua contribuição para os problemas observados ainda precisa ser
medida. Retirar a origem de coordenadas já arredondadas não recupera esse
detalhe: é necessário reler o arquivo original.

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
