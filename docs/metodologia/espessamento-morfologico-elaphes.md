# Dilatação morfológica da nuvem densa do Elaphes

**Experimento diagnóstico em 15/10/2026.** O objetivo é verificar se
espessar pontos medidos em uma grade de voxels fornece uma superfície mais
útil para reconstrução e, sobretudo, um volume cujo interior possa receber
um SDF confiável. Um SDF assim ajudaria a representar exemplos para redes
neurais e a controlar o viés espacial do Cellular Automata. O teste não
presume que uma grade de pontos de parede já seja o volume de ar da caverna.

## Método e controles

Usamos o PLY bruto do Elaphes (94.465.067 vértices) no recorte X `[12,35]`,
Y `[-3,25,8]`, Z `[-6,5,2]`. Há **22.273.631 pontos brutos** nesse recorte.
Uma amostra estratificada por bins de **45.868 coordenadas realmente medidas**
serviu ao primeiro ensaio e à avaliação de distância. A regra `first` mantém
o primeiro ponto de cada bin, sem criar centroides. O recorte tem entradas
artificiais nas duas pontas; qualquer teste de conectividade deve considerar
esse fato.

O primeiro ensaio retirou 20% dessa amostra como *holdout* fixo (semente
`20261015`) e usou os 36.695 pontos restantes em todas as reconstruções.
Comparou o Poisson direto com a seguinte sequência: marcar voxels que contêm
pontos medidos, dilatar essa ocupação por uma bola discreta, extrair sua
borda com Marching Cubes, usar as normais dessa borda no Screened Poisson.
A resolução foi `0,10` unidade XYZ por voxel; os raios foram 1 e 2 voxels
(`0,10` e `0,20` unidades). O Poisson usou profundidade 8 e uma thread.
Quando a borda tinha mais de 100.000 vértices, a entrada era reduzida a
100.000 pares vértice/normal por seleção determinística. O mesmo conjunto
medido e os mesmos parâmetros de Poisson foram usados na comparação.

Também foi preparada uma grade de ocupação com **todos** os pontos brutos do
recorte, na mesma resolução `0,10`, para comparar raios 0, 1 e 2 voxels. A
grade XYZ tem forma `(239,122,94)` e **49.155 voxels ocupados** antes da
dilatação.
Nesse segundo ensaio, os 45.868 pontos avaliados fazem parte do PLY que
formou a grade; a distância deles à malha é **cheque de aderência na própria
entrada, não holdout**. O raio 0 controla o efeito de voxelizar sem dilatar.
O diagnóstico de espaço livre usa conectividade de seis vizinhos no
complemento da ocupação e 56 nós da linha central dentro do recorte como
sondas **não validadas**. Nenhum desses nós comprova interior da caverna.

## Primeiro resultado: amostra medida

| Entrada do Poisson | Vértices na entrada | Borda da malha | Arestas não manifold | Componentes | Auto-interseção | Distância p95 da malha aos pontos medidos | Distância p95 do holdout à malha |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| Pontos medidos, sem voxelizar | 36.695 | 26 | 2 | 9 | Sim | 0,084 | 0,080 |
| Ocupação dilatada 0,10 | 100.000 | 0 | 9 | 22 | Sim | 0,206 | 0,151 |
| Ocupação dilatada 0,20 | 96.268 | 0 | 9 | 2 | Sim | 0,295 | 0,260 |

Nenhuma malha foi `watertight`. Zero arestas de borda nas duas alternativas
dilatadas **não** significa volume válido: persistiram arestas não manifold
e auto-interseções. Nos cortes X=`20`, `29,8` e `32,9`, a dilatação cria
curvas em **ambos os lados da parede medida**, isto é, uma casca de parede,
e desloca a superfície que queríamos representar. O raio maior amplia esse
deslocamento. As 56 sondas não puderam receber SDF assinado pela malha,
porque a geometria não passou na checagem de validade.

Resultados locais: `results/meshes/elaphes_morphological_thickening_dense2m_fine_03_summary.json`.
Figura de cortes: `results/figures/05_comparacao_malhas/elaphes_morphological_thickening_dense2m_fine_03_sections.png`.
Inspeção 3D: `results/figures/05_comparacao_malhas/elaphes_morphological_thickening_dense2m_fine_03.html`.
Os arquivos de dados e figuras são locais e ignorados pelo Git; o código e
os parâmetros estão versionados.

## Resultado principal: todos os pontos brutos do recorte

| Raio de dilatação | Voxels ocupados após dilatação | Arestas não manifold da malha | Componentes da malha | Auto-interseção | Distância p95 dos pontos medidos à malha | Distância p95 dos vértices da malha aos pontos medidos |
| --- | ---: | ---: | ---: | --- | ---: | ---: |
| 0 (controle voxelizado) | 49.155 | 42 | 19 | Sim | 0,099 | 0,162 |
| 1 voxel = 0,10 | 102.000 | 5 | 12 | Sim | 0,197 | 0,241 |
| 2 voxels = 0,20 | 155.545 | 0 | 3 | Sim | 0,303 | 0,328 |

As três malhas tiveram **zero arestas de borda**, mas **nenhuma foi
`watertight`** na checagem do Open3D, porque todas se auto-intersectam. O
raio 2 ficou sem arestas não manifold, com vértices manifold e faces
orientáveis; mesmo assim as auto-interseções inviabilizam promovê-lo a
referência assinada. A dilatação melhora algumas contagens topológicas e
reduz a ocupação bruta a um componente no raio 2, porém o Poisson ainda
produz três componentes e se afasta progressivamente dos pontos medidos.
Estas distâncias são **da própria entrada**, não uma avaliação independente.
Os cortes X=`20`, `29,8` e `32,9` mostram que **até o controle de raio 0**
já possui dois contornos em torno de boa parte da parede medida: extrair a
borda de voxels de parede cria uma casca. Os raios 1 e 2 alargam essa casca;
o ganho em algumas contagens não corrige essa semântica.

Com conectividade de seis vizinhos na grade de espaço livre, os **56 nós
sondados** ficaram fora da parede ocupada e **todos ligados à borda** em
cada um dos três raios. Surgiram apenas 21, 28 e 19 voxels de espaço livre
encerrado, respectivamente; nenhum contém esses nós. Isso não prova que os
nós sejam exteriores à caverna: o recorte foi aberto artificialmente em X=12
e X=35, e os próprios nós não foram validados em cortes. Mostra que aplicar
flood fill a essa grade, sem fechos controlados e conferência de interior,
não separaria o túnel sondado do exterior do recorte.

Resumo local: `results/meshes/elaphes_morphological_thickening_raw_010_01_summary.json`.
Grade local: `data/processed/elaphes_gallery_roi_x12_35_raw_occupancy_010.npz`.
Cortes: `results/figures/05_comparacao_malhas/elaphes_morphological_thickening_raw_010_01_sections.png`.
Inspeção 3D: `results/figures/05_comparacao_malhas/elaphes_morphological_thickening_raw_010_01.html`.

## Leitura para o SDF

O alvo físico é o **ar transitável** da caverna. Dilatar voxels que contêm
pontos da parede trata temporariamente a *parede observada* como sólido e
engrossa esse conjunto nos dois sentidos. A borda resultante pode ser
fechada ou visualmente lisa e ainda representar a casca errada. Logo,
contagens topológicas, distância aos pontos e conectividade do espaço livre
precisam ser avaliadas juntas. Mesmo um SDF numérico calculável para uma
malha fechada pode ter sinal semanticamente invertido ou estar associado a
volumes espúrios. O complemento da grade também não pode ser rotulado
automaticamente como ar: inclui exterior, regiões ocultas pelo scanner e
as duas pontas abertas do recorte.

**Conclusão para o TCC:** a hipótese de espessar morfologicamente a nuvem
densa **não forneceu um volume validado para SDF** neste recorte e nestes
parâmetros. A maior densidade ajudou a examinar o efeito sem depender só de
representantes espaciais, mas não resolveu a semântica da casca nem as
auto-interseções. Como o objetivo é avançar na comparação dos algoritmos,
um SDF de controle sintético e documentado pode alimentar o CA; volumes
sintéticos conhecidos também permitem verificar a infraestrutura de SDF e
treino. Esse substituto não deve ser descrito como SDF real do Elaphes.

## Reproduzir pelo menu

```bash
.venv/bin/python menu_malhas.py
```

As opções `9` e `10` amostram o PLY e comparam o Poisson direto com a
dilatação dessa amostra. As opções `11` e `12` voxelizam **todos os pontos
brutos do recorte** e comparam raios 0, 1 e 2. Para executar sem perguntas
interativas:

```bash
.venv/bin/python menu_malhas.py voxelizar-roi --voxel 0.1 \
  --saida data/processed/elaphes_gallery_roi_x12_35_raw_occupancy_010_repeticao.npz
.venv/bin/python menu_malhas.py espessar-bruto \
  --ocupacao data/processed/elaphes_gallery_roi_x12_35_raw_occupancy_010_repeticao.npz \
  --prefixo results/meshes/elaphes_thickening_raw_010_repeticao --raios 0 1 2 \
  --grafo data/processed/elaphes_centreline_roi_x12_45_pruned_exploratory.npz
```

Cada execução exige novos nomes de saída; não sobrescreve resultados
existentes. O comando `inspecionar` do menu mostra as chaves dos NPZ e as
métricas dos JSON. O script `plots/plot_thickening_sections.py` gera cortes
YZ comparáveis com a nuvem medida.
