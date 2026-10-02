# Fundamentos: nuvem orientada, octree e Screened Poisson

Este resumo distingue os conceitos geométricos da implementação concreta em
[amostragem e reconstrução do Elaphes](../metodologia/amostragem-normais-screened-poisson.md).

## Da nuvem de pontos a pontos orientados

Uma nuvem XYZ informa onde houve observação, mas não qual lado de uma parede é
interior. Para estimar uma normal em um ponto, ajusta-se um plano à sua
vizinhança. A matriz de covariância dessa vizinhança tem três autovetores; o
associado ao menor autovalor aponta na direção de menor variação e é
perpendicular ao plano. Isso determina uma **linha normal**, com duas escolhas
de sentido, `n` e `−n`. A orientação precisa ser coordenada entre pontos
vizinhos antes de reconstruir uma superfície. [Open3D: estimação e orientação
de normais](https://www.open3d.org/docs/latest/tutorial/geometry/surface_reconstruction.html),
[Hoppe et al. (1992)](https://hhoppe.com/recon.pdf).

O número de vizinhos controla a escala local. Poucos vizinhos respondem mais
a detalhe e ruído; muitos podem misturar paredes próximas ou apagar curvatura.
Consistência entre vizinhos não determina, por si só, qual sentido significa
"para fora da caverna". Esse sentido exige informação geométrica adicional
ou validação semântica.

## A octree do reconstrutor

Uma octree divide recursivamente um cubo 3D em oito subcubos. O Screened
Poisson usa uma octree **adaptativa** para representar e resolver um campo
implícito a partir de pontos com normais orientadas. A profundidade `d` limita
a resolução máxima a `2^d` células em cada direção do cubo de reconstrução;
regiões sem suporte não precisam chegar a esse nível. O método busca uma
superfície compatível com o campo de normais e acrescenta restrições nas
posições dos pontos. [Kazhdan e Hoppe (2013)](https://www.cs.jhu.edu/~misha/MyPapers/ToG13.pdf),
[API do Open3D 0.20](https://www.open3d.org/docs/latest/python_api/open3d.geometry.TriangleMesh.html).

A grade regular usada **antes** do Poisson para reduzir o Elaphes é outra
estrutura. Seus bins têm tamanho fixo dentro da mesma passagem. Ela limita
quantos representantes chegam ao reconstrutor e não é a octree adaptativa
que o Poisson constrói internamente.

## Suporte e extrapolação

O Poisson pode criar triângulos em regiões com poucos pontos e extrapolar para
além do scan. O Open3D devolve uma densidade estimada por vértice da malha;
valores baixos sugerem menor suporte da nuvem. Remover vértices de baixa
densidade é uma opção de pós-processamento, mas pode abrir bordas e eliminar
partes reais pouco observadas. Uma malha candidata precisa de validação de
suporte, orientação, bordas, componentes e semântica das entradas da caverna.
[Tutorial de reconstrução do Open3D](https://www.open3d.org/docs/latest/tutorial/geometry/surface_reconstruction.html).

## Fontes primárias

- [Hoppe et al., *Surface Reconstruction from Unorganized Points* (1992)](https://hhoppe.com/recon.pdf).
- [Kazhdan e Hoppe, *Screened Poisson Surface Reconstruction* (2013)](https://www.cs.jhu.edu/~misha/MyPapers/ToG13.pdf).
- [Open3D 0.20: API de `TriangleMesh.create_from_point_cloud_poisson`](https://www.open3d.org/docs/latest/python_api/open3d.geometry.TriangleMesh.html).
- [PoissonRecon: parâmetros da implementação original](https://github.com/mkazhdan/PoissonRecon/blob/master/README.md).
