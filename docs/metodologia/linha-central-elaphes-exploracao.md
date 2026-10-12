# Extração exploratória de linha central no Elaphes

## Objetivo e limite

Reproduzir em pequena escala a sequência de [Racine et al. (2025)](https://essd.copernicus.org/articles/17/4671/2025/): amostra da nuvem, contração laplaciana de Cao et al. com `pc-skeletor`, redução espacial dos pontos contraídos, seleção de componente e árvore geradora mínima. O [código dos autores](https://github.com/ERC-Karst/pc-processing/blob/v1.0.0/base/process_centreline.py) usa CloudComPy e `mistree_pp`; o ensaio abaixo usa Open3D e `mistree` para as últimas operações. Portanto, é **adaptação exploratória**, não reprodução numérica exata.

A linha central é hipótese geométrica; nenhuma posição extraída deve ser tratada como semente interna ou usada para orientar normais antes de uma inspeção em cortes da nuvem e da malha. A malha Poisson atual tem aberturas e áreas interpoladas que ainda precisam de revisão.

## Origem e preparo

- Entrada: `/run/media/midnavi/Pablo/TCC/DATA/RAW/elaphes_cave.ply` (94.465.067 vértices, PLY ASCII, XYZ mais atributos LAS). A unidade física de XYZ ainda precisa de confirmação.
- Amostra global anterior: `data/processed/elaphes_poisson_sample.npz`, com 1.864 pontos. Com `LBC(init_contraction=0.5, init_attraction=0.5, down_sample=0.4)` ela gerou um grafo curto, sem bifurcações, de 114 nós. Esse resultado é **inadequado para validar a caverna inteira**.
- Novo ensaio: recorte exploratório XYZ `[12, -3.25, -6.5]` a `[35, 8, 2]`, escolhido sobre um trecho aparente de galeria; um ponto original por bin, capacidade de 250.000 bins. O recorte é só para teste e não representa limites semânticos da caverna. Os limites do recorte cortam a galeria e podem afetar as extremidades da linha.
- O leitor `cavegen.datastream.ply.iter_ply_xyz` percorre o PLY em lotes de 100.000; `cavegen.meshing.poisson.sample_spatial_bins` aplica a amostragem com `sampling_rule='first'`. A seleção ROI é feita antes da amostragem. Assim, a amostragem mantém pontos observados da superfície, em vez de criar centroides entre paredes próximas.

## Critérios para julgar o grafo

1. Sobrepor o grafo à nuvem nas projeções XY, XZ e YZ e em cortes perpendiculares ao percurso. Uma projeção plausível não prova que o nó esteja no interior em 3D.
2. Medir cobertura longitudinal, quantidade de componentes, nós e bifurcações; procurar saltos entre trechos fisicamente separados e retração excessiva dos extremos.
3. Inspecionar piso, teto, paredes, bifurcações e trechos sem captura. Confirmar a direção interior das normais em regiões conhecidas antes de propor orientação por trecho.
4. Repetir com pelo menos outra densidade/escala de redução e registrar a sensibilidade dos resultados. Parâmetros de Racine foram calibrados para outro conjunto de cavernas.

O artigo de [Feng e Crane](https://nzfeng.github.io/research/SignedHeatMethod/SignedDistance.pdf) apresenta distância assinada em malhas e volumes digitais; ele pode ser investigado depois que houver uma superfície ou volume binário confiável. A atual ocupação esparsa de pontos não equivale a esse volume.

## Resultados do ensaio no PLY original (08/10/2026)

A leitura integral levou cerca de 524 s. O recorte reteve 22.273.631 pontos originais e produziu 10.949 pontos amostrados nos 111 × 54 × 41 bins possíveis. A amostra observada abrangeu aproximadamente X `12,00–35,00`, Y `-2,00–4,26`, Z `-5,23–0,18`. Ela foi salva em `data/processed/elaphes_gallery_roi_x12_35.npz` e exportada para CloudCompare como `results/figures/elaphes_gallery_roi_x12_35.ply`.

Para a contração, o Open3D reduziu essa amostra com voxels de `0,4` unidade XYZ e o filtro estatístico padrão do `pc-skeletor`, deixando 2.250 pontos. Usamos `init_attraction=0.5`, `down_sample=0.4`, no máximo 5 iterações e pesos iniciais de contração `0.5`, `0.1`, `0.05`, `0.01` e `0.005`. Depois, agrupamos pontos contraídos em voxels Open3D de `0,5` unidade XYZ. Para os pesos `0.5` e `0.05`, construímos uma árvore geradora mínima com `mistree.GetMST`, `k_neighbours=12`. O agrupamento por voxels **não é idêntico** à regra de distância mínima do CloudCompare usada por Racine et al.; também não aplicamos a seleção de maior componente por octree dos autores.

| Peso de contração | Nós após redução | Intervalo X dos nós | Inspeção inicial |
| --- | ---: | --- | --- |
| `0.5` (autores) | 32 | `16,89–29,95` | Linha central aparente, mas perde as duas extremidades do recorte. |
| `0.1` | 48 | `13,82–32,60` | Recupera parte da extensão. |
| `0.05` | 55 | `13,39–33,20` | Segue mais o trecho, com ramificações que exigem revisão. |
| `0.01` | 110 | `12,72–34,12` | Recupera a extensão, mas diversos pontos permanecem espalhados na seção da galeria. |
| `0.005` | 233 | `12,58–34,40` | Ainda mais disperso; não é uma linha central limpa. |

Para `0.05`, a árvore tem 54 arestas, quatro folhas e dois nós de grau 3 próximos de X≈29,78 e X≈32,90. A maior aresta tem aproximadamente `0,58` unidade XYZ. A distância mediana dos nós à amostra da superfície é `0,79` unidade XYZ. Essas medidas descrevem a geometria do candidato; **não demonstram que os nós estejam no interior**. As bifurcações podem decorrer de forma real, amostragem ou conexões da árvore.

Em [três cortes de espessura 1 unidade XYZ](../../results/figures/elaphes_centreline_roi_x12_35_sections.png), centrados em X=20, 29,8 e 32,9, os nós `0.05` aparecem dentro do contorno projetado da nuvem. O corte agrega pontos de profundidades X diferentes; ele é uma verificação visual preliminar, sem classificar interior/exterior nem confirmar as bifurcações.

### Repetição com o trecho seguinte incluído

Após a inspeção 3D do primeiro grafo, ampliamos o recorte para XYZ
`[12,-3.25,-6.5]` a `[45,8,3.5]`, mantendo `first` por bin e capacidade
de 400.000 bins. A passagem pelo PLY reteve 35.560.683 pontos brutos e
20.274 representantes em `156×53×48` bins. Com LBC `0.05/0.5`,
`down_sample=0.4`, máximo de cinco iterações, redução Open3D `0.5` e MST
`k_neighbours=12`, surgiram 129 nós entre X≈13,42 e 43,84, nove folhas e
seis nós de grau ≥3. Ver [vista 3D ampliada](../../results/figures/elaphes_centreline_roi_x12_45_interactive.html)
e [projeções](../../results/figures/elaphes_centreline_roi_x12_45_weight_0.05.png).

O nó de grau 3 em X≈32,9 do recorte curto **não reapareceu** com a extensão
até X=45. Na inspeção visual 3D posterior, o pesquisador confirmou que a
linha vermelha está dentro do volume aparente da nuvem, que há uma pequena
ramificação real para cima perto de X≈30 e uma grande bifurcação real perto
de X≈42. A pequena ramificação em X≈29,38 tem só uma aresta de `0,382`
unidade XYZ; seu comprimento curto **não** a torna artefato. Ainda é preciso
separar os braços reais da bifurcação das pequenas pontas geradas pelo grafo.
Essa confirmação visual dá apoio geométrico à linha, mas não substitui uma
classificação assinada interior/exterior para SDF.

Para abrir a nuvem e os nós no CloudCompare, usar
`results/figures/elaphes_gallery_roi_x12_45.ply` e
`results/figures/elaphes_centreline_roi_x12_45_weight_0.05_nodes.ply`.

### Poda exploratória com ramo confirmado protegido

Medimos cada ramo terminal da folha até o primeiro nó de grau diferente de
dois. Perto de X≈42, quatro pontas mediram `0,395`, `0,677`, `1,134` e
`1,287` unidade XYZ; os três braços mais longos mediram `1,676`, `2,770`
e `6,879`. Fizemos uma poda exploratória dos terminais com comprimento
`<1,3`, **exceto** o ramo confirmado em X≈30 (`0,382`). O grafo passou de
129 nós/128 arestas para 120 nós/119 arestas, com cinco folhas: o início
do recorte, o ramo curto real e os três braços maiores em X≈42. Ver
[linha 3D com poda](../../results/figures/elaphes_centreline_roi_x12_45_pruned_interactive.html).
Os 120 nós também estão em `results/figures/elaphes_centreline_roi_x12_45_pruned_nodes.ply`
para sobreposição com a nuvem no CloudCompare; esse PLY não contém as arestas.

O limiar `1,3` foi escolhido para **este diagnóstico** após a inspeção dos
comprimentos; não é regra geral para cavernas. Uma implementação de poda
deve aceitar ramos protegidos por evidência geométrica/manual e comparar
cada ponta removida com os pontos originais. Caso contrário, ela apagaria
justamente a ramificação real em X≈30.

Em 12/10/2026, Pablo abriu a última plotagem 3D no navegador e confirmou
visualmente que todos os nós da linha podada aparentam estar dentro do volume
da nuvem e que as ramificações estão representadas corretamente. A inspeção
visual do **grafo exibido** está concluída. Ainda faltam cortes locais para
avaliar posições interiores candidatas, confirmação geométrica das pontas
podadas nos pontos originais e classificação assinada para o SDF.

Arquivos de inspeção: [comparação de pesos](../../results/figures/elaphes_lbc_roi_weight_comparison.png), [grafo com peso 0,5](../../results/figures/elaphes_centreline_roi_x12_35_exploratory.png) e [vista 3D interativa com peso 0,05](../../results/figures/elaphes_centreline_roi_x12_35_interactive.html). Para sobreposição no CloudCompare, abrir `results/figures/elaphes_gallery_roi_x12_35.ply` junto de `results/figures/elaphes_centreline_roi_x12_35_weight_0.05_nodes.ply` (nós vermelhos; as arestas não foram exportadas para esse PLY). Os dados intermediários em `data/processed/` e as figuras em `results/figures/` são ignorados pelo Git; quem reproduzir o teste precisa gerar os seus próprios artefatos a partir do PLY original.

Ambiente deste ensaio: Python 3.14.7, NumPy 2.5.0, Open3D 0.20.0, `pc-skeletor` 1.0.0, `robust-laplacian` 1.1.0 e `mistree` 2.0.0. As dependências adicionais foram instaladas apenas em `/tmp/tcc-centreline-deps`, fora do ambiente do projeto. Não houve amostragem aleatória neste recorte (`first` por bin), portanto nenhuma seed foi sorteada; a ordem dos pontos no PLY determina qual deles representa cada bin. Uma futura implementação oficial deve registrar versões, parâmetros e qualquer seed usada.

### Regeneração dos gráficos 3D

O comando `plots/plot_elaphes.py` usa o mesmo padrão `plotly_white` e a escala
`Viridis` por Z dos plots de CA, com maior opacidade para mostrar os pontos
observados sobre o fundo claro. Ele carrega NPZ/OBJ já gerados; **não refaz**
a contração nem a reconstrução. Na raiz do projeto:

```bash
uv run python plots/plot_elaphes.py line
uv run python plots/plot_elaphes.py mesh
uv run python plots/plot_elaphes.py line --cloud data/processed/elaphes_gallery_roi_x12_45.npz --graph data/processed/elaphes_centreline_roi_x12_45_weight_0.05_exploratory.npz --output results/figures/elaphes_centreline_roi_x12_45_interactive.html
```

`line` usa por padrão a versão podada X `[12,45]`; `mesh` alterna entre a
candidata global densa e os cortes de densidade q10/q20. Para outros recortes,
usar `--cloud`, `--graph`, `--mesh NOME=OBJ` repetido e `--output`; `--show`
abre o navegador. `--max-points` e `--seed` controlam apenas a amostra **da
visualização**, sem alterar a nuvem de análise. Os seis HTMLs de inspeção
existentes foram regenerados com esse padrão em 09/10/2026 e seguem ignorados
pelo Git.

### Próximo experimento

Em 12/10 foi executado o [protótipo de orientação por
trechos](orientacao-normais-linha-central.md) sobre os 20.274 representantes
do recorte X `[12,45]` e o grafo podado de 120 nós. O NPZ, o CSV com índices
exatos e o HTML de revisão foram gerados em `data/processed/` e
`results/figures/` (ignorados pelo Git). Sem referências interiores
verificadas em cortes, **20.274/20.274** sentidos ficaram incertos; essa
execução verifica os contratos de arquivos e visualização, não a eficácia da
orientação.

Conferir em cortes do CloudCompare as pontas podadas e os três braços de
X≈42 contra pontos originais e malhas candidatas. Testar preservação de
extremidades, seleção de componentes e associação de pontos da superfície
a trechos da linha, inclusive nas bifurcações, antes de orientar normais ou
usar nós como sementes interiores. A classificação interior/exterior deve
ser validada separadamente antes de entregar a linha ao SDF.
