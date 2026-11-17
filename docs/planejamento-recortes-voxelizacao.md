# Planejamento dos recortes para voxelizar galerias separadamente

Atualizado em 17/11/2026. Este documento detalha a implementação futura do
[plano de seções sucessivas](plano-reconstrucao-secoes.md). **Não há extração
automática de recortes nem aplicação de tampas implementadas nesta revisão.**
O objetivo é preparar galerias com mais detalhe, limites reproduzíveis e
interior inferido revisável antes de treinar a GAN.

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

O JSON passado em `--bounds` ao CLI atual **não é um filtro de recorte**.
O fluxo ainda lê a nuvem inteira e o normalizador rejeita pontos fora dos
limites fornecidos. É necessário implementar a seleção antes da voxelização.
Fornecer bounds menores ou acumular índices na borda não separa corretamente
os dados. O menu atual não está pronto para executar este procedimento.

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

No LAS, decodificar coordenadas e retirar uma origem local mantendo precisão
suficiente, antes de converter para `float32`. Guardar origem e eventual
rotação rígida invertível, sem esticar eixos. O recorte deve poder ser
recolocado sobre a nuvem original; posições e normais dos planos usam a
mesma transformação.

Especificar a nova grade por origem local, shape ZYX e tamanho físico de
voxel. A proposta é usar células com mínimo inclusivo, máximo exclusivo,
centro a meio voxel e índice por
`floor((ponto - origem_da_grade) / tamanho_do_voxel)`, antes de trocar XYZ
por ZYX. Essa convenção futura difere do encaixe por arredondamento e spans
`N-1` do normalizador atual; não haverá troca silenciosa de contrato.

Pontos fora da região final serão filtrados, não acumulados artificialmente
nas faces da grade. Registrar uma tolerância numérica para os planos, conforme
precisão e escala, e testá-la. Para trechos adjacentes sem sobreposição,
atribuir o plano compartilhado a um deles por regra explícita; para janelas
sobrepostas, registrar a sobreposição e não contá-las como fontes independentes.

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

Mostrar separadamente parede observada, superfície interpolada, tampa e ar
inferido. Tampas nas extremidades não corrigem falhas laterais. Regiões sem
suporte suficiente permanecem incertas ou levam à rejeição. O exterior da
galeria delimitada não comprova rocha em toda a região: podem existir outras
cavidades não observadas.

## 5. Manifesto e organização propostos

Cada recorte terá identificador estável e configuração versionada. Estes
nomes descrevem saídas futuras, ainda não implementadas:

```text
data/processed/reference_sections/<caverna>/<levantamento>/<recorte>/<resolucao>/
    crop.json         # identidade, seleção, transformação e domínio da grade
    sections.json     # planos, contornos, contexto e decisões de revisão
    surface.npz       # superfície observada; True não significa ar
    interior.npz      # ar inferido e revisado; True = ar, ZYX
    masks.npz         # tampas, incerteza e suporte das observações
    run.json          # parâmetros efetivos, versões, hashes e conclusão
```

O manifesto deverá registrar:

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

No código futuro, testar seleção com pontos nas bordas, contexto e galerias
próximas; precisão após translação; ida e volta da transformação; XYZ/ZYX;
limites das células; e seleção idêntica para diferentes lotes de leitura.
Testar fechamento com máscaras artificiais conhecidas antes de interpretar
o interior de uma nuvem real.

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
