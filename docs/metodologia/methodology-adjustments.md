# Ajustes metodológicos da reconstrução e da geração

Este documento reflete a decisão descrita em
`Conclusao_Pipeline_Reconstrucao_Malha_SDF.docx` e preserva, para PCGRL, a
distinção entre dataset e recompensa de
`resumo_deep_rl_pcg_cavernas_tcc_formatado.docx`. Ambos são documentos locais
de apoio do TCC. A sequência abaixo é a **rota experimental adotada**, não
uma alegação de que a referência volumétrica já foi validada.

## 1. Da nuvem de pontos à malha

Os pontos do PLY representam superfície observada. A grade atual
`elaphes_surface_32.npz` (245 de 32.768 voxels) registra onde pontos caíram e
serve ao diagnóstico; converter seu complemento em vazio continuaria errado.
A nova rota reconstrói uma malha a partir de pontos contínuos e normais
estimadas/orientadas. Screened Poisson é o método principal; Ball Pivoting e
Alpha Shapes são fallbacks se a reconstrução principal falhar nos critérios
de aceitação, não alternativas independentes ao SDF. Amostragem, orientação de
normais, profundidade da octree, densidade, tempo e memória precisam constar
do relatório, sobretudo com 94.465.067 vértices do Elaphes.

Uma malha aproximadamente watertight deve ser avaliada quanto a arestas de
borda, manifoldness, auto-interseções, componentes, orientação, fidelidade aos
pontos e estabilidade paramétrica. O Screened Poisson pode extrapolar em
regiões pouco observadas. Entradas legítimas não são automaticamente falhas:
fechamentos necessários para uma classificação volumétrica devem ser
deliberados, localizados e marcados como **faces sintéticas**. Sua área e
efeito topológico precisam ser reportados. Faces sintéticas não equivalem a
superfície medida nas métricas de correspondência com o scan.

## 2. Classificação e campo de distância

Depois da malha, classificar interior/exterior. Flood fill da borda sobre uma
barreira voxelizada é a implementação inicial; cavidades abertas vazam por
entradas e gaps, então testar tampas controladas e registrar sensibilidade à
conectividade e resolução. Consultas de ocupação em malha válida e generalized
winding numbers em malhas imperfeitas são comparações/fallbacks possíveis.
Nenhum método torna automática a interpretação física do interior da caverna.
Regiões sem suporte confiável devem permanecer `UNKNOWN`.

A distância à malha fornece a magnitude do SDF; a classificação fornece o
sinal. A convenção do projeto será `SDF < 0` para `VOID` e `SDF > 0` para
`SOLID/EXTERIOR`. Em células válidas, uma banda `|SDF| ≤ ε` define
`SURFACE`; `ε` deve ser ligado ao espaçamento físico e submetido a análise
de sensibilidade. Não atribuir sinal a `UNKNOWN` como se houvesse evidência.
Persistir separadamente `sdf_float32`, rótulos categóricos e máscara de
validade, com origem, eixos XYZ/ZYX, escala, método e parâmetros.

Para aprendizagem e controle, derivar
`TSDF = clip(SDF, -τ, τ) / τ`, com `τ > 0` fixado por configuração.
TSDF concentra a faixa numérica perto das paredes; não é uma etapa que cria
interior/exterior nem dados independentes adicionais. O sinal e os rótulos
precisam ser validados em formas sintéticas conhecidas antes de usar o scan.

## 3. Cellular Automata guiado por SDF e algoritmo genético

O CA básico existente aplica uma regra local por vizinhança. O experimento
`CA+SDF` deve acrescentar um campo espacial de controle à inicialização,
limiar ou transição, mantendo a regra local reconhecível e um peso zero que
reproduza o baseline. A forma exata será escolhida e testada por Felipe; uma
possibilidade teórica é ponderar a informação de vizinhança com o TSDF de
controle, mais favorável à abertura onde o campo é negativo. Reportar peso,
seeds, ocupação, conectividade, aderência à forma e diversidade.

O controle principal deve vir de um SDF **simplificado e independente do scan
de teste** — por exemplo, tubo ou esqueleto procedural, pontos de entrada e
saída, ou grade de baixa resolução. Dar ao CA o SDF exato da referência que
será usada como resposta de teste transforma a tarefa em reconstrução
condicionada; isso pode ser estudado, mas em tabela separada. Para comparar
algoritmos condicionados, oferecer informação de controle equivalente.

Após estabilizar `CA+SDF`, testar se um algoritmo genético melhora parâmetros
da regra e do viés espacial. Definir cromossomo, limites, função de aptidão,
orçamento e população antes de rodar a busca. A aptidão pode equilibrar
conectividade, aderência ao **controle permitido**, diversidade e custo, com
escalas explícitas. Ajustar em treino/validação; reservar o teste. Comparar
`CA`, `CA+SDF` e `CA+SDF+GA` sob orçamento de geração comparável e relatar
também o custo adicional de otimização do GA. Incluir uma busca simples de
mesmo orçamento como controle metodológico para atribuir ganhos ao GA.

## 4. Avaliação das referências e dos geradores

IoU e Dice volumétricos voltam a ser apropriados quando `real_void` for
validado, no mesmo domínio do volume gerado e apenas nas células válidas.
Métricas de superfície (ASSD, Hausdorff95, Surface Dice com tolerância)
comparam fronteiras alinhadas, declaram unidade física/resolução e distinguem
superfície observada de tampas. Medir também componentes, maior componente,
ocupação, largura e, após definição, ramificação/tortuosidade. Uma única IoU
contra uma caverna específica não avalia sozinha a plausibilidade de um
gerador não condicionado.

Dividir treino/validação/teste por caverna ou região com separação espacial
entre patches. Quando houver poucos scans, relatar a limitação de
generalização. Volumes sintéticos de Random Walk/CA servem ao teste de
infraestrutura, mas não comprovam fidelidade à distribuição de cavernas
reais. Registrar versões da malha/SDF, `ε`, `τ`, máscaras, divisão dos dados,
hardware e custos separados de preparação, otimização/treinamento e geração.

## 5. Redes neurais após a referência válida

Auditar primeiro número e independência dos exemplos. Uma rede pode usar
`VOID` binário, TSDF ou ambos; a escolha de autoencoder, DCGAN ou WGAN exige
objetivo e critérios explícitos. Um autoencoder valida reconstrução, mas não
demonstra geração de novas cavernas. O SDF é representação, não substituto de
diversidade do dataset.

Para PCGRL, o dataset pode fornecer distribuições de ocupação, largura e
topologia ao problema/recompensa. Isso difere de treinar a política com pares
supervisionados. Formalizar estado, ações, transição, recompensa, desconto e
término antes de PPO; começar com grade pequena, representação Narrow 3D e
recompensa simples de conectividade/ocupação. Evitar IoU contra o conjunto de
teste na recompensa. Conv3D, controle condicional e Generator–Solver são
extensões posteriores; custo de treinamento e inferência devem ser separados.

## 6. Integração

As métricas e tabelas científicas ficam em Python. Unity renderiza as malhas
finais; arquivos OBJ intermediários podem ser inspecionados lá, e gRPC permanece
posterior. Comparações de tempo devem separar
CPU local, Colab/CUDA e eventual ROCm, com versões, backend e parâmetros
identificados. Seeds iguais tornam cada método reproduzível, mas não
emparelham geometrias equivalentes entre algoritmos.

Registrar em cada execução: hash da entrada, algoritmo, versão da biblioteca,
parâmetros, backend, número de threads e, quando houver sorteio, seed aleatória
e gerador utilizado. A `interior_seed_xyz` do protótipo Poisson é uma coordenada
sabidamente dentro da caverna para orientar normais, não uma seed de sorteio;
persisti-la separadamente. As regras atuais `first` e `centroid` não usam RNG;
`first` depende da ordem dos registros no PLY. Mesmo com parâmetros iguais, checar resultados
numéricos quando backend ou paralelismo mudar.

Na preparação para Poisson, os bins são células de uma grade XYZ regular e não
a octree adaptativa interna do reconstrutor. Comparar `first` com `centroid`
mantendo limites, número de bins, normais e profundidade iguais. Para o
centróide, registrar contagem e dispersão XYZ por bin. Média pode amortecer
ruído, mas mistura folhas de superfície diferentes quando dividem uma célula;
dispersão alta pede inspeção ou bins menores. Aceitar a malha com métricas de
suporte, bordas e topologia, não somente pela aparência de suavidade.
