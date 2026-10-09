# Linha central de cavernas em Racine et al. e ensaio no Elaphes

## Fonte e finalidade

[Racine et al. (2025), seção 2.7](https://essd.copernicus.org/articles/17/4671/2025/)
descrevem uma *linha central* como grafo métrico não dirigido, extraído da
nuvem das paredes de uma caverna. Ela resume o percurso e as ramificações e
permite relacionar observações à posição ao longo da passagem. A linha não é
uma malha, nem classifica por si só o interior. No nosso projeto ela é uma
hipótese de trajetória interior para inspecionar ramos, propor posições
interiores locais e investigar orientação das normais da reconstrução Poisson.

O [código publicado pelos autores, versão 1.0.0](https://github.com/ERC-Karst/pc-processing/blob/v1.0.0/base/process_centreline.py)
é a referência operacional. A contração usada ali deriva do método de
[Cao et al. (2010)](https://www.cs.jhu.edu/~misha/ReadingSeminar/Papers/Cao10.pdf).

## Como a sequência funciona

1. **Reduzir a nuvem das paredes.** Pontos demais tornam a contração cara e
   muitos pontos da mesma área pouco acrescentam ao eixo estimado. A escolha
   da amostra afeta trechos finos e regiões incompletas.
2. **Contrair por Laplaciano.** O `LBC` do `pc-skeletor` desloca os pontos em
   direção a uma estrutura mais fina, penalizando diferenças locais entre
   vizinhos. Um termo de atração os mantém ligados à geometria de entrada.
   Os pesos de contração e atração controlam o equilíbrio: contração excessiva
   encurta extremidades e pode deslocar nós para fora em curvas acentuadas;
   contração insuficiente deixa uma faixa larga de pontos.
3. **Reduzir os pontos contraídos.** Agrupar pontos próximos produz um conjunto
   menor de nós representativos. Essa operação não é a octree adaptativa do
   Screened Poisson: ela atua **depois** da contração e influencia a resolução
   longitudinal da linha.
4. **Separar componentes e ligar os nós.** No procedimento dos autores, uma
   etapa espacial identifica a maior componente; uma árvore geradora mínima
   (MST) liga os nós com comprimento total baixo, produzindo um grafo sem
   ciclos. A árvore pode criar uma ligação indevida entre passagens próximas
   ou uma ponta curta artificial; suas arestas exigem conferência geométrica.

O script dos autores chama `extract_topology()` no `pc-skeletor`, mas constrói
o grafo final a partir dos pontos contraídos reduzidos e da MST. Os valores
relatados no código são pesos iniciais de contração/atração `0,5/0,5`, redução
inicial `0,4`, distância mínima entre nós `0,5` e `k=12` para a MST. Esses
números não são parâmetros universais de cavernas.

## O que foi reproduzido no Elaphes

| Etapa | Artigo/código de Racine | Ensaio deste projeto |
| --- | --- | --- |
| Entrada | Nuvem de parede da caverna | PLY Elaphes, amostra `first` por bin no recorte X `[12,45]` |
| Contração | `pc-skeletor` LBC, teste de pesos | `pc-skeletor` LBC, até 5 iterações; `0,05/0,5` após comparar pesos |
| Redução inicial | `down_sample=0,4` | `down_sample=0,4` |
| Nós reduzidos | Distância mínima `0,5` via CloudComPy | `voxel_down_sample(0,5)` no Open3D; algoritmo diferente |
| Componentes | Maior componente por análise espacial | Ainda não implementado |
| Conexões | `mistree_pp`, MST com `k=12` | `mistree`, MST com `k=12` |
| Poda | Revisão ligada à geometria da caverna | Poda **exploratória** por ramo terminal e proteção manual do ramo X≈30 |

O recorte ampliado contém 20.274 representantes. Antes da poda, o grafo tinha
129 nós, 128 arestas, 9 folhas e 6 nós de bifurcação. A inspeção 3D mostrou a
linha aparente dentro da nuvem; o pesquisador reconheceu um ramo curto real
para cima em X≈30 e uma bifurcação maior em X≈42. Uma ponta em X≈33 do recorte
mais curto não persistiu ao ampliar a janela. A poda diagnóstica removeu
quatro terminais com menos de `1,3` unidade perto de X≈42 e protegeu o ramo
real de `0,382` unidade em X≈30: restaram 120 nós, 119 arestas e 5 folhas.
O limiar `1,3` **não pode ser generalizado** sem examinar outras regiões.

Os valores, arquivos e limites da inspeção estão em
[extração exploratória no Elaphes](../metodologia/linha-central-elaphes-exploracao.md).
As dependências desse ensaio foram instaladas apenas em um ambiente temporário;
não existe ainda um comando de produção para gerar o grafo a partir do PLY.
Existe um comando para **visualizar** os NPZ já gerados.

## Adaptações e decisões ainda necessárias

- Verificar as quatro pontas removidas e os três braços conservados em X≈42
  contra cortes dos pontos originais. Definir uma poda que preserve ramos
  protegidos por evidência, sem depender somente de comprimento.
- Medir estabilidade dos nós e arestas ao mudar densidade da amostra, janela,
  pesos, redução espacial e `k` da MST. Testar preservação de extremidades e
  detecção de ligações que atravessam paredes.
- Localizar eventuais poses do scanner. Se não houver, discutir como validar
  múltiplas posições interiores ao longo da linha para orientar normais por
  trecho, inclusive em bifurcações. Conferir piso, teto e paredes conhecidos.
- Antes de usar qualquer nó como `interior_seed_xyz`, verificar sua posição
  em cortes e em uma malha revisada. A aparência dentro da nuvem não prova o
  sinal do SDF nem autoriza fechar entradas automaticamente.
- Comparar, se for útil, a redução por voxel com a distância mínima e a
  seleção de componentes dos autores. Chamar o resultado atual de adaptação
  exploratória, pois não é reprodução numérica exata do artigo.

Referências: [Racine et al. (2025)](https://essd.copernicus.org/articles/17/4671/2025/),
[implementação dos autores](https://github.com/ERC-Karst/pc-processing/blob/v1.0.0/base/process_centreline.py)
e [Cao et al. (2010)](https://www.cs.jhu.edu/~misha/ReadingSeminar/Papers/Cao10.pdf).
