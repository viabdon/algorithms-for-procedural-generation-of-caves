# Poisson e espessamento leve na extensão completa do Elaphes

**Ensaio diagnóstico de 18/10/2026.** O PLY ASCII completo de 94.465.067
pontos foi lido usando os limites XYZ persistidos em
`data/params/elaphes_xyz_bounds.json`, de `[-9,9391,-3,23727,-6,96334]`
até `[73,7245,12,9577,69,7809]`. Nenhum recorte espacial foi aplicado.
Os três pontos brutos com Z>8 continuaram elegíveis; um deles representa
o bin alto ocupado na amostra final.

## Amostra e reconstrução

Dividimos a caixa completa em `655×127×601` bins, no máximo 50 milhões de
células, com largura aproximada de 0,128 unidade XYZ. Guardamos o **primeiro
ponto medido de cada bin ocupado**, sem centroides ou sorteio. A passagem
pelo PLY levou 499 s e produziu 152.228 representantes. Todos entraram na
baseline: normais Open3D estimadas com 30 vizinhos e orientadas por planos
tangentes com 30 vizinhos, depois Screened Poisson com profundidade 8 e uma
thread. Não houve semente interior validada.

As alternativas espessadas usaram a **mesma amostra**, voxels de 0,05 e
dilatação esférica discreta de 1 ou 2 voxels, correspondentes aos raios
0,05 e 0,10. Marching Cubes extraiu a borda da ocupação dilatada e suas
normais, usadas como entrada do mesmo Poisson. O processamento por blocos
de 96 voxels com margem preserva a borda nas emendas sem criar a grade densa
de aproximadamente 869 milhões de voxels que a caixa completa exigiria.
Havia cerca de 2,5 milhões de vértices nessa borda; o ensaio final reteve
500 mil pares vértice/normal por seleção determinística. Também foram
registradas execuções com limites de 100 mil e 300 mil para medir a
sensibilidade a essa redução.

## Resultados com limite de 500 mil pontos de borda

| Entrada do Poisson | Pontos de entrada | Arestas abertas | Arestas não manifold | Componentes | Auto-interseção | p95 vértice→amostra | p95 amostra→malha |
| --- | ---: | ---: | ---: | ---: | --- | ---: | ---: |
| Baseline sem espessamento | 152.228 | 33 | 20 | 3 | Sim | 1,675 | 0,249 |
| Espessamento 0,05 | 500.000 | 159 | 134 | 26 | Sim | 5,385 | 0,276 |
| Espessamento 0,10 | 500.000 | 16 | 139 | 55 | Não detectada | 0,332 | 0,269 |

**Nenhuma malha passou na checagem `watertight`.** O raio 0,10 melhorou a
proximidade dos vértices aos pontos e eliminou auto-interseções detectáveis
nesta execução, mas ainda há aberturas, arestas não manifold e muitos
componentes. As distâncias são à **amostra que gerou as malhas**, não a um
holdout independente. A entrada sintética espessada representa uma casca
ao redor dos pontos de parede, sem interior/exterior validado.

O resultado também depende do teto de pontos de borda. Para o raio 0,10,
os limites de 100 mil, 300 mil e 500 mil produziram, respectivamente,
`160/176/29`, `14/154/34` e `16/139/55` para arestas abertas / arestas não
manifold / componentes. Auto-interseções foram detectadas com 100 mil, mas
não com 300 mil ou 500 mil. Essa sensibilidade impede tratar um único HTML
como confirmação de qualidade topológica. A amostra conservou um ponto em
Z≈69,78; a malha de raio 0,10 chega a Z≈77,51, fora do corpo principal.

## Hipótese para pesquisa futura: reconstrução por trechos

Uma alternativa ainda **não testada** é dividir a nuvem em trechos com
sobreposição, executar buscas locais de parâmetros e reconstruir a região de
cada bifurcação como uma unidade, incluindo parte de seus braços. Isso pode
reduzir a mistura de escalas geométricas no Poisson global, mas não garante
melhora topológica. As normais teriam de manter orientação compatível nas
sobreposições; a junção precisaria substituir as superfícies duplicadas por
uma superfície contínua. O critério decisivo seria a **malha unida**, com
aderência aos pontos, arestas abertas, componentes, auto-interseções e
entradas reais avaliados antes de qualquer SDF. Uma tampa artificial em cada
recorte não provaria que o interior global da caverna foi recuperado.

Pelo foco e tempo disponíveis, a segmentação, a busca por trecho e a união
de malhas ficam fora do escopo do TCC atual. Este registro é uma hipótese de
pesquisa futura, não um resultado experimental confirmado.

## Artefatos

- [Baseline 3D](../../results/figures/05_comparacao_malhas/elaphes_full_first_bins_50m_fine_500k_baseline.html)
- [Espessamento 0,05 3D](../../results/figures/05_comparacao_malhas/elaphes_full_first_bins_50m_fine_500k_radius_005.html)
- [Espessamento 0,10 3D](../../results/figures/05_comparacao_malhas/elaphes_full_first_bins_50m_fine_500k_radius_010.html)
- [Métricas finais](../../results/meshes/elaphes_full_first_bins_50m_fine_500k_summary.json)

Os OBJ e os ensaios de sensibilidade de 100 mil e 300 mil usam o mesmo
prefixo em `results/meshes/` e `results/figures/05_comparacao_malhas/`.
Esses artefatos e a amostra NPZ são locais e ignorados pelo Git.

Para reproduzir em um novo ambiente com acesso ao PLY original:

```bash
.venv/bin/python -m cavegen.meshing.poisson \
  --ply /caminho/para/elaphes_cave.ply \
  --bounds data/params/elaphes_xyz_bounds.json \
  --sample-only --sample-path data/processed/elaphes_full_first_bins_50m.npz \
  --max-points 50000000 --batch-size 100000
.venv/bin/python -m cavegen.meshing.full_extent_experiment \
  --sample data/processed/elaphes_full_first_bins_50m.npz \
  --output-prefix results/meshes/elaphes_full_first_bins_50m_fine_500k \
  --figure-dir results/figures/05_comparacao_malhas \
  --voxel-size 0.05 --max-boundary-points 500000 \
  --plot-points 50000 --depth 8 --threads 1
```

Usar novos nomes de saída ao repetir, pois o script protege os resultados
existentes contra sobrescrita.
