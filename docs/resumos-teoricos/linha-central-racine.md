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
Em 12/10, Pablo confirmou na última plotagem 3D que todos os nós aparentam
estar dentro do volume da nuvem e que as ramificações exibidas fazem sentido.
Essa validação visual não comprova o sinal interior nem a orientação local
das normais.
O limiar `1,3` **não pode ser generalizado** sem examinar outras regiões.

Os valores, arquivos e limites da inspeção estão em
[extração exploratória no Elaphes](../metodologia/linha-central-elaphes-exploracao.md).
As dependências desse ensaio foram instaladas apenas em um ambiente temporário;
não existe ainda um comando de produção para gerar o grafo a partir do PLY.
Existe um comando para **visualizar** os NPZ já gerados.

## Etapa nova: usar a linha para investigar as normais

A extração **LBC + redução + MST** é a parte inspirada em Racine. A orientação
local a seguir é uma **proposta experimental nossa**, posterior à extração;
ela não deve ser atribuída ao artigo. Imagine a linha como um mapa de
corredores. Um ponto na parede pode estar perto de um corredor, mas perto
de uma bifurcação pode ter **dois corredores plausíveis**. A proximidade
visual, sozinha, não diz de qual lado da parede está o vazio.

1. **Separar corredores.** Cortamos a árvore em caminhos entre pontas e
   bifurcações, preservando o ramo curto real em X≈30. Cada ponto da amostra
   recebe até dois candidatos. Comparamos a distância do ponto à linha em
   relação a uma escala local da passagem. Se os custos forem parecidos,
   conservamos as duas possibilidades em vez de escolher uma arbitrariamente.
2. **Escolher referências interiores.** Os nós exibidos pela linha são apenas
   *candidatos*. O pesquisador confere alguns em cortes locais da nuvem,
   observando piso, teto, paredes e ramificações. Só depois marca um nó como
   `validated_interior: true` em um JSON ligado ao hash do grafo.
3. **Pedir um voto a cada ramo.** Para um ponto de parede, seguimos seu ramo
   até a referência verificada mais próxima. O vetor da referência para o
   ponto sugere o lado exterior da passagem local. Compará-lo com a normal
   estimada diz se o sentido deve ser mantido ou invertido. Referências
   distantes, vetores quase tangentes ou votos opostos não dão uma resposta
   segura. **Não somamos ou promediamos normais de ramos diferentes**: uma
   média pode cancelar os vetores ou apontar para uma direção sem sentido
   geométrico.
4. **Conferir com vizinhos da mesma superfície.** Pontos próximos, com
   normais coerentes e deslocamento tangente, formam trechos locais. Um
   trecho só recebe um sentido quando há votos suficientes e acordo forte.
   Isso tenta impedir que a decisão de uma parede passe para outra parede
   próxima. A vizinhança ainda é euclidiana, portanto essa proteção precisa
   ser testada em passagens estreitas e na bifurcação X≈42. O consenso não
   decide um ponto sem seu próprio voto local válido; uma referência distante
   não orienta automaticamente a parede inteira.
5. **Guardar dúvidas para revisão.** O resultado salva `uncertain_indices`:
   a lista dos índices exatos dos pontos ainda sem sentido confiável, além
   dos motivos, ramos e normais. No HTML, marcadores rosa e setas permitem
   localizar o ponto; o hover mostra seu índice. O pesquisador pode escrever
   `keep` ou `flip` na linha correspondente do CSV. A correção produz outro
   artefato e mantém as dúvidas restantes. Corrigir o **sentido** não conserta
   uma normal geométrica mal estimada.

O [procedimento, os comandos e os formatos](../metodologia/orientacao-normais-linha-central.md)
estão no documento metodológico. No primeiro diagnóstico do Elaphes, **nenhum
nó foi promovido a interior verificado**: todos os 20.274 pontos ficaram
incertos, como deveria ocorrer sem a evidência necessária. Uma nova malha
Poisson poderá usar as normais revisadas para uma comparação controlada, mas
isso ainda não constitui validação do interior para flood fill ou SDF.

## Adaptações e decisões ainda necessárias

- Verificar as quatro pontas removidas e os três braços conservados em X≈42
  contra cortes dos pontos originais. Definir uma poda que preserve ramos
  protegidos por evidência, sem depender somente de comprimento.
- Medir estabilidade dos nós e arestas ao mudar densidade da amostra, janela,
  pesos, redução espacial e `k` da MST. Testar preservação de extremidades e
  detecção de ligações que atravessam paredes.
- O [inventário disponível](../metodologia/metadados-elaphes-scanner.md) não
  encontrou poses do scanner. Conferir posições candidatas em cortes locais,
  piso, teto e paredes conhecidos; definir a associação de pontos a trechos
  antes de orientar normais, sobretudo nas bifurcações.
- Antes de usar qualquer nó como `interior_seed_xyz`, verificar sua posição
  em cortes e em uma malha revisada. A aparência dentro da nuvem não prova o
  sinal do SDF nem autoriza fechar entradas automaticamente.
- Comparar, se for útil, a redução por voxel com a distância mínima e a
  seleção de componentes dos autores. Chamar o resultado atual de adaptação
  exploratória, pois não é reprodução numérica exata do artigo.
- Conferir o mapa de custos e os trechos de superfície com cortes locais,
  verificar cada referência interior e comparar malhas produzidas da mesma
  amostra com e sem a orientação por trecho. Registrar pontos ainda incertos,
  erros de associação e efeito sobre teto, bifurcações e entradas.

Referências: [Racine et al. (2025)](https://essd.copernicus.org/articles/17/4671/2025/),
[implementação dos autores](https://github.com/ERC-Karst/pc-processing/blob/v1.0.0/base/process_centreline.py)
e [Cao et al. (2010)](https://www.cs.jhu.edu/~misha/ReadingSeminar/Papers/Cao10.pdf).
