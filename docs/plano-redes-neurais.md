# Plano de redes neurais: GAN, PCGRL e PCGARL

## Revisão executável de 15/11/2026 — GAN de referências voxelizadas

**Pergunta:** uma GAN incondicional consegue gerar volumes voxelizados com
distribuição geométrica próxima das referências reconstruídas de nuvens de
cavernas, mantendo diversidade? A resposta experimental ainda não existe:
**não foi treinado nenhum modelo**. Foram implementados dados, redes, perdas,
treino, checkpoints, inferência, avaliação e notebook Colab. Os dados atuais
falham na auditoria geométrica mínima, descrita abaixo; o código bloqueia sua
utilização acidental como cavernas resolvidas.

Esta seção fixa o protocolo implementado. As seções de 07/11 abaixo são o
histórico e a discussão das alternativas. Onde diferem — início em 16³,
placeholders e perda sem regularização — prevalecem as decisões desta revisão.
A conclusão pode ser inviabilidade ou dados insuficientes; não foi adotada
uma obrigação de demonstrar superioridade da GAN.

**Próxima etapa definida em 15/11/2026:** reconstruir recortes de galerias por
seções transversais sucessivas, com tampas computacionais nas extremidades e
validação de detalhe, continuidade e regiões inferidas antes do treino.
O procedimento está no [plano de reconstrução por seções](plano-reconstrucao-secoes.md).
O [resumo simplificado](resumo-gargalo-gan.md) explica o gargalo atual e por que
treinar agora ensinaria a imitar referências inadequadas. O procedimento ainda
será implementado; referências melhores não garantem o desempenho da GAN.

Em 17/11/2026, o [planejamento dos recortes](planejamento-recortes-voxelizacao.md)
detalhou a seleção dos pontos por galeria, contexto além dos cortes, planos
das tampas, bounds da grade e metadados. O split continua por caverna antes
da extração. Esse piloto ainda será implementado; os bounds do CLI atual não
funcionam como filtro de trechos.

### 1. Resultado da auditoria e alcance científico

Foram percorridos todos os nove NPZ de `data/processed/references` e seus
recibos. São cinco cavernas com superfícies, mas **apenas quatro com
interiores candidatos**. Não são nove exemplos independentes. O resultado
detalhado, com imagem inspecionada e comandos para reprodução, está na
[auditoria GAN](auditoria/gan/README.md); os hashes, origens, licenças,
configurações, eixos e métricas estão no
[manifesto](auditoria/gan/reference_audit.json).

| Caverna | Superfície 64³: voxels observados | Interior 64³: voxels de ar | Componentes 6 | Maior componente | EDT máxima (voxels) |
| --- | ---: | ---: | ---: | ---: | ---: |
| Archamps / PreEtroiture | 1.002 | **2** | 2 | 1 voxel | 1 |
| Cascade de Môtiers / MainGallery | 761 | **1** | 1 | 1 voxel | 1 |
| Indian Tunnel / Full 1x | 1.147 | **98** | 5 | 92 voxels | √2 |
| Markov Spodmol / MainGallery | 1.198 | **5** | 5 | 1 voxel | 1 |

Os quatro interiores reproduzem exatamente o flood fill exterior de seis
vizinhos, sem interseção com a superfície. Isso confirma a consistência do
processamento, não a fidelidade do vazio inferido. Uma GAN que os imitasse
estaria aprendendo pontos/resíduos quase todo-sólidos. Mesmo Indian retém ar
em uma caixa de apenas `3×19×10` voxels. Todos perdem **100% do ar em 16³**
no diagnóstico por nearest neighbor. A superfície Elaphes de 32³ continua
fora do treino de ar; seus 245 voxels marcam superfície observada.

Não converter superfície em ar, não somar as duas máscaras como atalho e não
fabricar dados reais a partir de CA/Random Walk. O papel dos geradores
clássicos permanece o de controles/competidores. Há três cavernas cársticas
e um tubo de lava entre os interiores; mistura de domínios é uma decisão
experimental explícita, sem alegação de aprender speleogênese.

O loader exige maior componente ≥64 voxels e EDT máxima ≥2 voxels, além de
resolução nativa e semântica explícita. Esse mínimo de engenharia rejeita
resíduos e não substitui validação física. `allow_candidate_proxy=True`
autoriza estudar ar **inferido**, mas não ignora o mínimo. Nenhum dado atual
passa. O próximo passo experimental é revisar a reconstrução/espessura,
entradas e lacunas, gerar outros NPZ e congelar novos hashes. Não foi feita
essa reconstrução silenciosamente nesta implementação.

As grades preservam proporções, mas cada caverna foi escalada por seu próprio
maior eixo. A EDT em voxels compara formas normalizadas; não mede a mesma
espessura física nas quatro cavernas. Sem reconstrução e calibração adicionais,
o experimento se limita às representações obtidas, não a cavernas reais em
metros. A identidade integral das nuvens brutas continua não verificada.

### 2. Discriminador, rótulos e separação dos dados

O discriminador recebe **somente um tensor volumétrico**, sem nome do arquivo,
seed ou indicador de origem: classe positiva = volume derivado de nuvem de
referência, classe negativa = volume produzido por G. Os rótulos identificam
a origem no jogo adversarial; não são classes geológicas nem certificado de
realismo. O gradiente do discriminador orienta G a produzir saídas mais
semelhantes à distribuição positiva. Sua acurácia não responde, sozinha,
à pergunta de qualidade ou conectividade.

Usar treino/validação/teste por **caverna antes de recortes e aumentos**. O
[arquivo de partições](auditoria/gan/splits.json) congela quatro folds:

| Fold | Treino | Validação | Teste |
| --- | --- | --- | --- |
| `holdout_archamps` | Indian, Markov | Cascade | Archamps |
| `holdout_cascadedemotiers` | Archamps, Markov | Indian | Cascade |
| `holdout_indian_tunnel` (inicial) | Archamps, Cascade | Markov | Indian |
| `holdout_markovspodmol` | Cascade, Indian | Archamps | Markov |

Cada caverna é teste e validação uma vez. Todas as versões, densidades e
trechos de uma caverna devem permanecer no mesmo grupo. A implementação
confere fingerprint do manifesto, hashes de arquivo e voxels, paths seguros,
grupo da origem e ausência de compartilhamento entre partições. Duplicatas
idênticas de ar não podem inflar o inventário. Os folds já estão definidos,
mas seu estado é `blocked_insufficient_interior_geometry`: separar dados não
equivale a aprová-los.

Há só dois volumes de treino e um de validação/teste por fold. Isso permite
um estudo exploratório de transferência entre essas fontes, com altíssimo
risco de memorização; não estima generalização ampla. O fold inicial também
testa mudança karst → lava. Relatar todos os folds e todas as falhas; não
escolher um vencedor entre folds após observar o teste. Com dados futuros,
ampliar as cavernas independentes antes de ajustar muitos hiperparâmetros.

### 3. Seeds e a expressão “qualquer seed”

O conjunto de **dados** não é dividido pela seed latente da GAN. Essa seed
só escolhe uma amostra de ruído, não uma nova nuvem de referência. O loader
não acrescenta seeds ou rotações aos grupos independentes.

- Seeds de treino propostas: **17, 29, 43**, em execuções/pastas separadas.
  São repetições futuras, ainda não executadas.
- Validação de checkpoint: **1.000.000 a 1.000.015**, fixas desde o início.
- Teste inicial: **0 a 255**, mais **65.535, 4.294.967.295 e 2⁶³−1**: 259
  amostras por checkpoint/fold/seed de treino, sem escolher só boas saídas.
- A API e CLI aceitam qualquer inteiro em **[0, 2⁶³)**, listas explícitas ou
  intervalos. É possível avaliar mais seeds sem recomeçar o treino. Cobrir
  literalmente todo esse domínio é inviável; não se promete exaustividade.
- O latente é `N(0,I)` gerado por RNG torch **local em CPU**, com 128 valores
  por seed. A geração ocorre uma amostra por chamada; a seed não depende da
  ordem da lista nem do tamanho do lote. Há testes dos extremos e de ausência
  de alteração do RNG global durante inferência. Igualdade entre hardwares
  ou versões diferentes não é garantida; o ambiente fica registrado.

As mesmas seeds de inferência serão usadas nos métodos/ablações comparáveis.
Sobreposição com seeds fixas de validação é registrada, se solicitada pelo
usuário; as listas padrão são distintas. Muitas seeds melhoram a análise da
distribuição condicional ao checkpoint, não a quantidade de cavernas de teste.

### 4. Arquitetura implementada e revisão das propostas

Escolha inicial: **GAN densa 3D pequena, global, em 64³**, com dois modos
controlados de representação. O alvo 64³ é preservado porque reduzir os dados
atuais elimina o ar; isso não garante que 64³ resolva sua geometria. As versões
16³/32³ servem a testes de software ou a futuros dados nativos adequados.
O forward 64³ foi verificado em CPU; o custo de backward na GPU do Colab ainda
precisa ser medido. Não declarar viabilidade de VRAM a partir de um forward.

| Estágio de G (`base_channels=16`) | Saída por amostra | Operações |
| --- | --- | --- |
| Entrada | 128 | Latente gaussiano |
| Projeção linear | `128×4×4×4` | Linear e reshape |
| Bloco 1 | `64×8×8×8` | Upsample nearest ×2, Conv3D 3³/pad 1, GroupNorm, ReLU |
| Bloco 2 | `32×16×16×16` | Mesmas operações |
| Bloco 3 | `16×32×32×32` | Mesmas operações |
| Bloco 4 | `16×64×64×64` | Mesmas operações |
| Campo | `1×64×64×64` | Conv3D 3³/pad 1 e sigmoid (ocupação) ou tanh (SDF) |

D usa Conv3D 4³, stride 2, padding 1 e LeakyReLU(0,2), com canais
**16 → 32 → 64 → 128**, reduzindo 64³ a 4³. Uma Conv3D 4³ final produz **um
logit global por volume**, sem sigmoid no módulo. G tem **1.354.801** parâmetros
e D **697.585** nessa configuração. GroupNorm de G usa `gcd(8,canais)` grupos;
D não usa normalização dependente de lote. Pesos lineares/convolucionais são
inicializados em `N(0,0,02²)` e biases em zero. É uma adaptação do projeto,
não reprodução exata de DCGAN, 3D-GAN, World-GAN ou SDF-StyleGAN.

| Proposta / evidência | Decisão nesta revisão |
| --- | --- |
| 3D-GAN de Wu et al. (2016), §3.1: geração voxel 64³ com convoluções volumétricas. | Sustenta a escolha de uma baseline volumétrica global. Foram reduzidos canais/lote, usado latente gaussiano 128 em vez do uniforme 200 original e mudadas as operações de expansão/regularização. Não transportar seus resultados em objetos para cavernas. [Artigo primário](https://proceedings.neurips.cc/paper/2016/hash/44f683a84163b3523afe57c2e008bc8c-Abstract.html). |
| World-GAN [R3], §§III.B–E: cascata 3D local e um exemplar, WGAN-GP + reconstrução. | É alternativa mais compatível com poucas fontes, mas aprende estatísticas locais e não garante túneis globais. Mantida como etapa posterior, sem entregar uma implementação parcial como reprodução. Não há cascata nem block2vec nesta baseline. |
| SDF-StyleGAN [R4]: representação implícita e D global/local com valores/gradientes. | Implementado um controle **explícito em grade**, com G/D de mesma capacidade da ocupação. Não foram implementados StyleGAN2, consultas implícitas ou seus dois discriminadores; não atribuir à adaptação seus ganhos publicados. |
| Mescheder, Geiger e Nowozin (2018), §4: penalidade R1 e análise de estabilidade. | Adotar logística não saturante + R1 e instance noise simétrico. A análise local sob hipóteses não garante convergência nesta aplicação. A aplicação esparsa de R1 é escolha de custo do projeto. [Artigo primário](https://proceedings.mlr.press/v80/mescheder18a.html). |
| Odena, Dumoulin e Olah (2016): resize-convolution como alternativa a artefatos de convolução transposta em imagens. | G usa nearest + Conv3D. A extensão volumétrica é uma escolha a validar; não se afirma eliminação comprovada de artefatos 3D. [Estudo dos autores](https://distill.pub/2016/deconv-checkerboard/). |
| Zhao et al. (2020): aumento diferenciável aplicado a real e gerado. | Usar só rotações de yaw por múltiplos de 90°, diferenciáveis, sem interpolação; mesma distribuição para ambos. Preserva Z e evita ruído por cor/cutout sem sentido em cavernas. Não é reprodução completa de DiffAugment/ADA. [Artigo primário](https://arxiv.org/abs/2006.10738). |

As cópias locais de Liu [R1] e Summerville [R2] continuam fundamentando os
cuidados com representação, poucos dados e funcionalidade. Jouves et al.
(2017), no artigo local de *Speleogenesis*, diferencia descritores geométricos
e topológicos de redes de cavernas; isso motiva avaliar mais que aparência.
Não implementamos seus oito descritores de grafos como se fossem EDT voxel.
Withington, Cook e Tokarchuk (2024), no artigo local de avaliação de PCG,
reforça a necessidade de explicitar métricas, comparadores e alcance. A leitura
de *Compressing and Comparing the Generative Spaces* não sustenta usar um
embedding treinado em duas cavernas como medida universal de qualidade; essa
alternativa foi adiada. Identidades das sete cópias locais efetivamente
consultadas estão no [inventário bibliográfico](auditoria/gan/papers.json).

### 5. Representações, perdas e otimização

Contrato: booleanos em ZYX, `True=ar`; tensores `float32 (N,1,D,H,W)`.
Metadados de superfície não entram como exemplos positivos de ar.

**Ocupação:** dados em {0,1}, G contínuo em [0,1]. Durante treino D vê o campo
contínuo, sem limiarização. Para exportar/avaliar: `field >= 0.5`. O limiar é
fixo desde o protocolo; não será ajustado no teste. A diferença de suporte
binário/contínuo pode facilitar D; o ruído inicial mitiga esse atalho, sem
garantia de eliminá-lo ao final.

**SDF discreto (`gan_sdf`):** revisão explícita da proposta anterior de borda
zero. Usar `EDT(ar com padding sólido) - EDT(sólido)`, nos centros dos voxels,
depois `clip(-tau,+tau)/tau`, com **tau=4 voxels** comum. Interior positivo,
exterior negativo, fora da grade sólido. A interface está entre centros;
nenhum centro de ar é zero nos alvos, incluindo túneis de um voxel. `field > 0`
reconstrói a ocupação original, como verificado em cubos, linhas na borda,
todo-ar e todo-sólido. Todo-sólido é codificado como -1; todo-ar usa distância
até o padding sólido. É um surrogate discreto truncado, não distância exata
a uma superfície contínua nem o contrato histórico de borda zero do Felipe.
Não há normalização pelo máximo de cada volume. Nenhuma EDT ou threshold
interrompe o caminho diferenciável de G até D.

Para logit D e amostras real x/gerada G(z), minimizam-se:

```text
L_D = mean(softplus(-D(x))) + mean(softplus(D(G(z).detach())))
      + (gamma/2) * intervalo_R1 * mean(||grad_x D(x)||²) [nos passos R1]
L_G = mean(softplus(-D(G(z))))
```

R1 usa o gradiente em relação ao real antes das transformações diferenciáveis.
O D recebe aumentos/ruído durante as duas atualizações; não recebe batch
statistics de G. Uma atualização de D e uma de G por passo; D fica congelado
durante a atualização de G. Configuração efetiva inicial:

- Adam em ambos: **lr=1e−4, betas=(0, 0,99)**; sem scheduler.
- Lote **2**, amostragem com reposição das cavernas de treino. A repetição não
  é contada como nova referência. Sem balanceamento de classes de voxels.
- **gamma R1=10**, a cada **16** passos, multiplicado por 16 quando aplicado.
- Instance noise gaussiano **sigma=0,1**, decaimento linear até zero em
  **2.500** passos; mesma distribuição para real e gerado, sem clamp.
- Rotações yaw uniformes entre 0/90/180/270° por amostra, em real e gerado.
  Não há reflexão vertical, crop, estiramento ou reparo de componentes.
- Máximo **5.000 passos ou 60 minutos por execução**, o que ocorrer primeiro,
  incluindo validação. Um passo iniciado pode ultrapassar o prazo; não há
  timeout rígido no meio de kernels CUDA.
- Validação a cada **250** passos e no último passo planejado, com 16 seeds
  fixas. Sem AMP inicialmente: simplifica R1/gradientes de segunda ordem e
  diagnóstico de NaN. AMP e perdas estruturais são ablações futuras.

Esses números são propostas pré-experimento, não parâmetros ótimos derivados
dos artigos. Ocupação e SDF têm configurações JSON separadas em
[`configs/gan`](../configs/gan), com mesmo orçamento. Comparar capacidade e
custo real; o TSDF acrescenta pré-processamento e não contém informação
geométrica nova quando o interior de origem é ruim.

### 6. Seleção, avaliação e controles

Os modelos são selecionados **só em validação**. O score implementado soma:
média das distâncias Wasserstein 1D por descritor + JS dos padrões 2³ + fração
degenerada. Descritores: fração de ar, número de componentes, fração na maior
componente, EDT média e máxima. Cada distância é dividida pelo desvio padrão
do treino, com pisos **(0,01; 1; 0,1; 1; 1)** nessa ordem; não se estima a
escala no teste. EDT indefinida nos degenerados entra como zero no score,
com degeneração relatada separadamente. O score é uma heurística explícita
para checkpoint, não uma métrica validada de realismo nem meta de aprovação.

Para padrões 2³, enumerar todas as janelas válidas, sem wrap, 256 códigos de
bits em ordem ZYX. Normalizar histogramas, somar **1e−6 a cada probabilidade**,
renormalizar e calcular divergência JS com log natural, em [0,ln 2]. A suavização
é independente da quantidade de amostras; copiar uma referência repetidamente
não altera o histograma normalizado. É uma adaptação motivada pela análise
local do World-GAN, não a reprodução de sua TPKL 5³/10³.

No teste, preservar por seed todos os campos contínuos, volumes brutos,
`structural-v1`, quantis 5/50/95%, degeneração, duplicatas exatas, cópias exatas
do treino, distância Hamming ao treino e diversidade Hamming entre todos os
pares das primeiras 64 seeds solicitadas. Hamming é sensível à posição/eixos,
dominado pelo sólido em grades esparsas e não prova memorização; serve como
diagnóstico junto com hashes e inspeção visual. Não há IoU entre cavernas
desalinhadas, FID de fotografias ou acurácia de D como critério de sucesso.

Controles implementados com o mesmo número de amostras: **cópia cíclica do
treino** e **todo-sólido**. Comparação com CA/Random Walk e seus custos depende
da integração do benchmark clássico já pendente; não foi falsificada em CSV.
A variante SDF também relata MAE entre campo predito e recodificação de sua
própria ocupação. Um campo com valores contínuos plausíveis não é
automaticamente um campo de distância coerente.

Não há limiar quantitativo de “GAN capaz” validado ainda. Uma resposta favorável
precisará mostrar aproximação de várias propriedades das referências válidas,
diversidade, ausência de colapso/cópia trivial e falhas globais relatadas, em
repetições/folds pré-definidos. Um score menor que o controle de cópia é
informativo, mas não suficiente. Quantis de seeds não são intervalos de
confiança entre cavernas. Com quatro fontes, os resultados serão descritivos.

### 7. Código entregue, checkpoints e uso no Colab

| Artefato | Responsabilidade |
| --- | --- |
| `training/reference_data.py` | Auditoria, hashes, semântica, origem, resolução, folds e validação de integridade |
| `training/gan_data.py` | Loader por partição, bloqueio de resíduos, ocupação/TSDF e decodificação |
| `training/gan_models.py` | G/D 3D configuráveis e latente por seed |
| `training/gan_training.py` | Perdas, Adam, aumentos, R1, orçamento, validação, checkpoints e retomada |
| `training/train_gan.py` | CLI: apenas preflight por padrão; otimização exige `--train` |
| `generators/gan_3d.py` | Inferência de checkpoint para `Volume3D`, com seed, hash, backend e proveniência |
| `training/gan_evaluation.py` e `evaluate_gan.py` | Métricas, controles, avaliação em seeds arbitrárias e exportação de campo/NPZ |
| `training/prepare_colab.py` | ZIP privado com código, configurações e voxels pequenos, manifesto verificável |
| [Notebook Colab](../notebooks/colab/01_gan_reference_volumes.ipynb) | Instalação mínima, upload, Drive opcional, inspeção, preflight e execução explícita |

Checkpoints `latest.pt` e `best.pt` contêm redes, Adam, passo, configuração,
estado RNG torch CPU/CUDA, melhor score, tempo acumulado, hash do código,
hashes de dados/partições, fold e ambiente. `latest` inicial de passo zero
permite retomar se o primeiro passo falhar; a avaliação rejeita pesos de
passo zero. `best` só existe após validação. A retomada exige os mesmos dados,
código, fold e configuração; sessões/hardware são registrados e podem afetar
a reprodutibilidade. O loop usa apenas RNG torch para treinamento; não depende
de sorteios NumPy/Python nem de workers de DataLoader.

Falhas de NaN/gradiente não finito, OOM e interrupção param a execução e geram
`status.json`. Um passo pode ter atualizado D antes de falhar em G: não se
salva esse estado parcial como checkpoint concluído. Retomar do último
checkpoint completo, potencialmente repetindo trabalho desde a validação
anterior. Logs `losses.jsonl`, `validation.jsonl` e `resume_sessions.jsonl`
preservam os eventos. Pastas de experimento/avaliação existentes não são
sobrescritas silenciosamente. A queda abrupta de VM só preserva arquivos já
gravados; usar Drive para persistência. O notebook não executa treino nem
avaliação automaticamente (`RUN_TRAINING=False`, `RUN_EVALUATION=False`).

```powershell
$env:PYTHONPATH='src'
# Auditoria, figuras e pacote: nenhum treino.
.\.venv-gan\Scripts\python.exe -m cavegen.training.reference_data
.\.venv-gan\Scripts\python.exe -m cavegen.training.plot_reference_audit
.\.venv-gan\Scripts\python.exe -m cavegen.training.prepare_colab
# Preflight: deve rejeitar os interiores atuais.
.\.venv-gan\Scripts\python.exe -m cavegen.training.train_gan
```

No Colab, enviar `data/processed/gan_colab_bundle.zip` pela célula do notebook.
Os dados são ignorados pelo Git, por isso clonar só o repositório não recupera
os NPZ. O pacote dispensa as nuvens de vários GB e dependências clássicas
pesadas. Abrir o notebook com GPU não inicia otimização. Após futura correção
dos dados, o notebook já contém o caminho completo de treino, retomada,
seleção e teste. Ver [instruções do Colab](../notebooks/colab/README.md).

### 8. Verificação e pendências

- [x] Auditoria técnica dos nove NPZ, recibos e origens, com imagem inspecionada.
- [x] Partições por caverna, protocolo de seeds e proteção contra vazamento.
- [x] Código executável de ocupação e TSDF, perdas, checkpoints e avaliação.
- [x] Notebook Jupyter/Colab com execução desativada e empacotamento dos dados.
- [x] Testes automatizados novos de comportamento público; nenhum treino nas
  referências. O teste de atualização/retomada usa só dados artificiais pequenos.
- [ ] Reconstrução e validação geométrica de interiores utilizáveis.
- [ ] Medida de VRAM de um passo completo na GPU efetivamente disponível.
- [ ] Experimentos em Colab, 3 seeds de treino e 4 folds conforme orçamento;
  checkpoint, relatório e resposta experimental sobre capacidade da GAN.
- [ ] Cascata de exemplar único inspirada no World-GAN, caso a baseline e os
  dados justifiquem o custo. Seus passos históricos abaixo continuam propostas.

O relatório de verificações e limitações do ambiente fica em
[`verificacao.md`](auditoria/gan/verificacao.md). As referências adicionais desta
revisão estão registradas neste Markdown e em `papers.json`; não foi alterado
o DOCX bibliográfico externo durante uma tarefa de código/auditoria.

## Histórico e alternativas de 07/11/2026

Pablo conduz esta frente em paralelo à conclusão
dos clássicos e à coleta de métricas por Felipe. Os itens são propostas de
trabalho, não resultados experimentais. A especificação adversarial e os
limiares numéricos continuam abertos. A comparação final planejada usa 64³;
escalas menores são ensaios de desenvolvimento e não resultados comparáveis.

## Base e dependências

- O contrato comum é `Volume3D` em ZYX, booleano, `True = ar`; salvar NPZ com
  configuração e proveniência. `Volume3D` converte números para booleano:
  probabilidades devem ser limiarizadas explicitamente antes da conversão.
- `cavegen.metrics.evaluate_structure` fornece `structural-v1`: ocupação,
  componentes, fração na maior componente e EDT. Há testes e casos degenerados
  definidos em [métricas estruturais](metricas-estruturais.md). Não confundir
  conectividade por faces (6) com arestas/cantos (26).
- `benchmark/records.py` já cria linhas e acrescenta ao CSV, mas fixa backend
  CPU e repetição zero, exige cabeçalho idêntico e um escritor por vez. Antes
  de receber modelos, combinar evolução versionada do esquema com Felipe;
  não registrar execução GPU como CPU nem sobrescrever dados antigos.
- Benchmark/menu não importam em `a7dd1e7`: o CA não exporta
  `generate_cellular_automata`. Felipe cuidará da integração dos clássicos;
  ela não impede testar métricas e ambiente neural isoladamente.
- `gan_3d.py`, `pcgrl_3d.py` e `training/train_*.py` são placeholders; não há
  checkpoint neural treinado verificado. A IoU contra o Elaphes e seu SDF real
  não são critérios de avaliação, pois a superfície observada não fornece VOID.

## Primeiro ciclo: dados e prova de conceito de GAN 3D

Revisão baseada nas cópias locais de Liu et al. [R1], Summerville et al.
[R2] e Awiszus, Schubert e Rosenhahn [R3]. A prioridade anterior do ambiente PCGRL é substituída por uma auditoria
seguida de uma prova pequena de GAN. Esta é uma decisão de escopo para esta
frente do projeto: os artigos não prescrevem começar por GAN nem demonstram
que ela será superior aos clássicos ou ao PCGRL.

### O que as referências sustentam

| Evidência bibliográfica | Consequência proposta para o primeiro ciclo |
| --- | --- |
| [R1], §4.4, descreve DCGANs para níveis, terrenos via mapas de altura e TOAD-GAN a partir de um exemplo. | Distinguir geração de mapas 2D, relevo 2,5D e volumes 3D. Uma DCGAN volumétrica é uma adaptação a testar; mapas de altura não representam todas as passagens sobrepostas de uma caverna. |
| [R1], §6.5, discute escassez de dados e informa que a necessidade de dados varia com modelo, domínio e treino; cita MarioGAN treinada com segmentos de um nível. [R2], §IV.B–C, discute fonte, representação e pequenos conjuntos. | Contar fontes independentes e amostras derivadas separadamente. Não fixar um mínimo universal de volumes nem interpretar muitos recortes como muitas cavernas. |
| [R1], §4.4, distingue modelagem visual de restrições funcionais e apresenta CANs como alternativa; [R2], §IV.A, discute solucionabilidade. | Avaliar conectividade e degeneração fora do discriminador. Adiar perdas de restrição e reparos até medir o comportamento da GAN básica. |
| [R2], §IV.E, discute dados e benchmarks para comparar métodos. | Congelar dados, partições e avaliação antes de comparar GAN e geradores clássicos. As métricas 3D abaixo são escolhas deste projeto. |
| [R3], §III.B–E, usa uma cascata convolucional 3D por patches, com um exemplar e representação block2vec; §IV.B avalia frequências, padrões e variabilidade. | Acrescentar uma variante multiescala de exemplar único e medir fidelidade local separadamente de conectividade global. O ganho de memória dos embeddings em Minecraft não é automaticamente transferível ao caso binário. |

Essas revisões motivam o desenho experimental, mas não fornecem uma receita
validada para cavernas em 64³. Arquitetura, resolução inicial, função de perda,
limiar, orçamento e critérios quantitativos exigem especificação e ensaio.
O estudo primário World-GAN [R3], agora consultado, demonstra geração voxel
3D a partir de um exemplo em Minecraft. Ele fornece uma alternativa concreta
para poucos dados, mas não valida a geração de cavernas conectadas nem a
interpretação de superfícies de scans como volumes de vazio.

### Execução e entregáveis do ciclo

1. [ ] **Auditar os dados.** Produzir manifesto com origem, licença, semântica,
   eixos, resolução, configuração efetiva, seed, fonte/caverna/grafo e hash.
   Separar volumes de vazio conhecidos de nuvens, superfícies e grafos. Os
   arquivos em `data/processed/experiments/experiment_elaphes-meshing/` são
   intermediários históricos; não constituem automaticamente exemplos de ar
   interno. A referência de superfície do Elaphes continua fora do treino de VOID.
2. [ ] **Escolher a pergunta experimental.** Se houver apenas volumes de CA ou
   Random Walk, testar se a GAN reproduz a distribuição desse gerador, começando
   por uma fonte e configuração identificadas. Manter algoritmos/configurações
   separados no inventário; misturá-los exige uma hipótese explícita. Não alegar
   aprendizado de cavernas reais a partir dessa prova sintética. Se só existir
   uma fonte real válida, limitar o estudo a síntese a partir dessa fonte, sem
   alegar generalização entre cavernas.
3. [ ] **Congelar as partições.** Definir a unidade de independência antes de
   recortes e aumentos. Agrupar por caverna/grafo/volume de origem quando houver
   dependência; registrar separadamente seeds de geração, treino e avaliação.
   Para dados sintéticos, explicitar se o teste cobre novas seeds da mesma
   configuração ou configurações reservadas. Se faltarem grupos independentes,
   registrar a limitação em vez de fabricar um teste de generalização.
4. [ ] **Fixar a representação de ocupação e testar o fluxo.** Manter `True = ar`, ZYX e
   tensores `(N,1,D,H,W)`; converter booleanos para o domínio numérico escolhido.
   Proposta inicial: gerador com saída contínua em `[0,1]`, discriminador com
   logits e perda adversarial logística não saturante, documentada antes do
   treino. O discriminador recebe saídas contínuas durante o treino; limiarizar
   apenas para exportação/avaliação, sem cortar o gradiente. A diferença entre
   dados binários e saídas contínuas deve ser acompanhada como risco de treino.
   A escolha dessa perda é uma baseline do projeto, não uma reprodução de [R1].
5. [ ] **Implementar uma GAN convolucional 3D mínima.** Especificar distribuição
   e dimensão latente, camadas/canais, ativações, inicialização, otimizadores,
   taxas, lote, alternância entre gerador e discriminador e orçamento. Começar
   em 16³ como ensaio proposto, após conferir se os túneis sobrevivem à resolução
   escolhida e medir RAM/VRAM em um passo completo. Fazer testes de shape,
   gradientes finitos, atualização das duas redes, seed de inferência e
   exportação NPZ. Não assumir viabilidade de 64³ a partir do ensaio pequeno.
6. [ ] **Treinar e acompanhar falhas.** Salvar configuração efetiva, manifesto e
   partições, versões, hardware, checkpoints dos modelos/otimizadores e estados
   aleatórios para retomada. Usar latentes fixos para acompanhar amostras e
   latentes reservados para avaliar. Registrar perdas, tempo e memória, mas
   selecionar checkpoint/limiar por um protocolo de validação definido antes;
   perda adversarial baixa, isoladamente, não comprova qualidade.
7. [ ] **Avaliar distribuição e validade separadamente.** Aplicar `structural-v1`
   aos volumes brutos limiarizados: ocupação, componentes em 6 vizinhos, fração
   na maior componente, degeneração e EDT com suas ressalvas. Reportar
   distribuições, dispersão, duplicatas e vizinhos próximos ao treino para
   investigar colapso e memorização; semelhança isolada não prova memorização.
   Fixar representação/distância e tamanho das amostras antes da avaliação.
   Comparar com volumes reservados do gerador de origem e com reamostragem do
   treino como controle de cópia. Não usar IoU entre cavernas não alinhadas nem
   FID de imagens naturais sem justificar uma representação pertinente em 3D.
8. [ ] **Encerrar com um relatório de viabilidade.** Entregar manifesto,
   configuração, checkpoint, amostras NPZ e métricas, distinguindo custo de
   dados, treino e inferência. Definir antes da execução orçamento e regras de
   parada para NaN, falta de memória e ausência de progresso. Repetir com seeds
   de treino independentes conforme orçamento declarado. Só propor 32³ e depois
   64³ após avaliar perda de geometria, estabilidade, diversidade e custo. Se
   houver reparo ou filtragem, relatar também as saídas brutas e rejeitadas.

**Critério de conclusão:** fluxo dados → treino → checkpoint → inferência →
`Volume3D`/NPZ → métricas executável e rastreável, com falhas e limitações
registradas. Concluir esse ciclo pode resultar em GAN inviável ou dados
insuficientes; não exige declarar superioridade. Qualquer meta numérica de
qualidade deve ser fixada antes da comparação, após os testes de sanidade.

### Variante experimental de geração direta de SDF

A baseline permanece uma **GAN de ocupação**: o gerador emite valores
contínuos em `[0,1]`, convertidos em ar/sólido para avaliação. A proposta
adicional é uma **GAN que gera um campo contínuo de distância assinada**,
inspirada em SDF-StyleGAN [R4]. O discriminador aprende a distinguir campos
dos dados de referência e campos gerados; distância até a borda não é, por si
só, uma medida de realismo. Se os dados vierem de CA/Random Walk, o objetivo
continua sendo aprender uma distribuição sintética.

[R4] demonstra discriminadores globais e locais que usam valores e gradientes
de SDF para geração de formas 3D. Nossa primeira variante seria uma grade
explícita, não uma reprodução de sua arquitetura implícita baseada em StyleGAN.
A hipótese a testar é que a informação de distância favoreça a geometria dos
túneis em relação à ocupação. O resultado favorável do SDF no uso por CA/Random
Walk motiva a hipótese, mas não comprova benefício no treino adversarial.

- [ ] **Preparar pares ocupação/SDF.** Reutilizar o procedimento sintético do
  Felipe, após integrá-lo e testá-lo: distância euclidiana ao voxel de borda,
  interior positivo, exterior negativo, borda zero, `float32` em ZYX e unidades
  de voxel. Registrar versão do cálculo, conectividade de borda, política no
  limite da grade, spacing e procedência. Tratar explicitamente volumes sem
  borda e degenerados. Os scripts históricos na branch `CA` não equivalem a uma
  API já integrada. Não usar o SDF do scan como rótulo de vazio validado.
- [ ] **Fixar normalização e decodificação.** Usar a mesma transformação para
  referência e geração. Candidata: `clip(sdf, -tau, tau) / tau`, com `tau > 0`
  comum e escolhido em validação; chamá-la de distância truncada normalizada.
  Não normalizar pelo máximo individual. Manter máscara de ocupação original e
  classificação de borda: o zero ocupa voxels inteiros no contrato atual, e
  `sdf > 0` pode remover o contorno aberto de túneis finos. Definir e testar a
  regra de reconstrução para valores próximos de zero antes de treinar, com
  casos geométricos conhecidos. Se o contrato não permitir reconstrução fiel,
  revisar a convenção ou acrescentar um canal auxiliar de ocupação, registrando
  essa mudança como outra variante.
- [ ] **Preservar o gradiente.** Produzir diretamente um tensor contínuo
  `(N,1,D,H,W)` no domínio normalizado escolhido e passá-lo ao discriminador.
  Não colocar limiarização seguida de EDT do SciPy entre gerador e
  discriminador: esse caminho não fornece o gradiente necessário ao gerador.
  A EDT pode ser pré-calculada nos dados e usada fora do treino para avaliação.
  Começar com a mesma família de arquitetura e perda logística da baseline,
  ajustando o domínio da saída; fixar capacidade e orçamento comparáveis.
  Discriminadores adicionais locais/globais, canais de gradiente e outras
  perdas ficam para ablações posteriores, sem mudar tudo no primeiro teste.
- [ ] **Verificar se o campo tem coerência de distância.** Um tensor contínuo
  gerado não é automaticamente um SDF. Após decodificar ocupação, recalcular
  seu campo pelo mesmo procedimento e comparar com o campo predito, aplicando
  a mesma truncagem e escala. Reportar erro no volume e perto da borda, além
  de limitações da decodificação. Gradientes podem ser inspecionados como
  diagnóstico; não impor automaticamente norma unitária em bordas discretas,
  pontos de não diferenciabilidade ou faixas truncadas. Regularizações de
  distância, se necessárias, exigem protocolo e teste próprios.
- [ ] **Comparar ocupação e SDF sem confundir efeitos.** Usar as mesmas fontes,
  partições, resolução, seeds de avaliação e critérios de seleção. Identificar
  configurações como `gan_occupancy` e `gan_sdf`, salvar tanto o campo quanto
  o volume decodificado e registrar tempo de pré-processamento, treino,
  inferência, memória e falhas. Avaliar os volumes por `structural-v1`, padrões
  locais, diversidade e duplicatas. Verificar especialmente túneis finos,
  componentes isoladas e saturação do campo. Não minimizar distância voxel a
  voxel contra uma caverna arbitrária não alinhada como critério de geração
  incondicional. A exatidão da EDT dos dados não garante qualidade das amostras.

**Entregável adicional:** relatório de ablação ocupação versus SDF com
configurações, campos preditos, volumes, métricas estruturais e coerência de
distância. Esta variante e a multiescala são eixos experimentais distintos;
combiná-los somente após medir cada efeito e declarar o orçamento disponível.

### Variante de exemplar único inspirada no World-GAN

Esta variante complementa a baseline GAN do ciclo. Deve ter configuração e
resultados próprios, identificados como **adaptação inspirada em World-GAN**.
A baseline logística do item 4 não reproduz a função de perda de [R3]. Antes
de executar, escolher e registrar se o orçamento cobre apenas a baseline ou
esta variante também; não trocar silenciosamente um protocolo pelo outro.

- [ ] **Fixar um exemplar de vazio conhecido.** Treinar uma cascata por volume
  de origem, começando por um volume sintético auditado de CA ou Random Walk.
  Os patches extraídos dele são observações locais, não cavernas independentes.
  Reservar ruídos de inferência para avaliar variabilidade e, quando possível,
  outras fontes para avaliar transferência; novos ruídos não constituem teste
  de generalização entre cavernas. Sem validação independente, predefinir o
  orçamento/checkpoint e declarar as análises sobre o exemplar como descritivas.
- [ ] **Especificar a cascata.** [R3], §III.B–D, descreve geradores e
  discriminadores locais convolucionais, treino da escala grossa para a fina,
  refinamento residual do volume interpolado e ruído por escala. A perda é
  WGAN-GP mais reconstrução ponderada por `alpha`; a reconstrução mantém o
  exemplar acessível por uma realização de ruído específica. Registrar campo
  receptivo, política de borda, interpolação, ruído, transferência de pesos,
  pesos das perdas e orçamento por escala. Testar separadamente reconstrução
  e síntese aleatória: reconstruir o exemplar não demonstra diversidade.
- [ ] **Auditar a redução de resolução.** O artigo compara escalas relativas
  `(1.0, 0.5)`, `(1.0, 0.75, 0.5)` e `(1.0, 0.75, 0.5, 0.25)` e escolhe a
  última em seus exemplos (§IV.B.2). Esses valores são referência, não uma
  receita para 16³: sua menor escala seria 4³ e poderia eliminar passagens.
  Antes do treino, medir ocupação e conectividade em cada escala e após
  reconstrução da resolução original. Registrar se são usados valores contínuos
  ou rótulos discretos e como são obtidos. Só escolher a pirâmide após conferir
  gargalos/túneis; não aplicar uma hierarquia de raridade de blocos ao ar/sólido
  sem testar seu efeito geométrico.
- [ ] **Manter a representação binária como controle.** [R3] usa embeddings
  de 32 dimensões para reduzir o custo frente a dezenas de tipos de blocos,
  decodificando por vizinho mais próximo no espaço de embeddings. Para dois
  rótulos, começar com um canal contínuo ou dois canais categóricos e documentar
  a decodificação/limiar. Não incluir block2vec/BERT no primeiro ensaio sem uma
  pergunta específica: 32 canais superam um ou dois em custo de representação.
  Essa simplificação altera o método e deve constar no relatório.
- [ ] **Acrescentar fidelidade local às métricas estruturais.** Inspirar-se nos
  histogramas de blocos e na Tile Pattern KL-Divergence (TPKL-Div) de [R3],
  §IV.B: comparar frequências de ar/sólido e distribuições de padrões cúbicos.
  O artigo usa padrões 5³ e 10³ e reporta a média contra 20 níveis gerados
  (Tabela II); não adotar esses tamanhos/quantidades como requisito universal.
  Para a prova 16³, propor inicialmente padrões 2³ e 3³, reportados
  separadamente, após verificar suporte e custo. Fixar direção da KL,
  suavização para padrões ausentes, base do log, tratamento das bordas e
  amostragem de janelas; relatar fidelidade local junto de conectividade,
  degeneração e diversidade. A adaptação e esses parâmetros precisam de testes
  antes de entrar no pipeline. Não substituir conectividade por TPKL baixa.
- [ ] **Fazer comparações controladas e limitar a extrapolação.** Se o orçamento
  permitir, comparar uma escala com a cascata usando o mesmo exemplar,
  resolução final, representação e avaliação; registrar custo total e capacidade
  para não atribuir ganhos só ao número de escalas. Como controle adicional,
  considerar reamostragem de patches do exemplar para verificar se o modelo
  supera uma recombinação local simples. [R3] mede variabilidade por Levenshtein
  de fatias serializadas; para cavernas, fixar eixo/ordem e normalização se essa
  medida for usada, pois ela depende da serialização e pode ser cara. A análise
  de duplicatas/vizinhos próximos permanece necessária. A arquitetura permite
  saídas de outros tamanhos, mas isso não equivale a aumentar a resolução física
  nem garante túneis conectados em volumes maiores. Testar tamanhos adicionais
  apenas após o caso de mesmo tamanho e relatar falhas globais.

**Limite da hipótese:** [R3], §IV.A e §V, reconhece que coerência funcional e
correção semântica não são impostas pelo método. Para cavernas, preservar
padrões locais pode coexistir com passagens interrompidas e componentes
isoladas. Medir esse conflito é parte do experimento, sem presumir sua solução
pelo discriminador ou pela perda de reconstrução.

## Ciclo seguinte: ambiente PCGRL pequeno

Proposta mantida para a frente de RL, independente da arquitetura da GAN:

1. [ ] Definir MDP versionado: estado = grade de ar/sólido, posição do cursor e
   passos restantes; a observação deve conter toda informação que influencia
   a transição. Definir política de bordas e estado inicial com seed explícita.
2. [ ] Escolher ações discretas (mover em 6 direções, abrir, fechar e terminar)
   e o que acontece em borda, edição redundante e término antecipado. Alternativa:
   varredura automática do cursor; documentar o efeito sobre o espaço de ações.
3. [ ] Implementar ambiente pequeno, por exemplo 8³ ou 16³, com limite de passos;
   `reset(seed=...)` e `step` devem seguir a versão efetiva do Gymnasium,
   distinguindo término por objetivo de truncamento por orçamento.
4. [ ] Testar limites, reprodutibilidade, transições, espaços de observação e
   ação, término/truncamento e integração `Volume3D`/NPZ. Executar um episódio
   aleatório e um conjunto de exemplos geométricos conhecidos antes do PPO.
5. [ ] Medir custo por passo da avaliação estrutural; se for alto, usar medidas
   baratas ou avaliação periódica, validando equivalência. Não presumir que EDT
   completa a cada ação seja viável em 64³.
6. [ ] Treinar uma prova de conceito e comparar com política aleatória, mesmo
   estado inicial, ações, horizonte e conjunto de sementes de avaliação.
   Registrar curva de treino e avaliação em seeds separadas; salvar configuração,
   versão, checkpoint e estados aleatórios necessários para retomar.

### Métricas e recompensa de RL

Métricas de avaliação são descritivas; recompensa é uma escolha de projeto e
não deve ser confundida com qualidade independente. Compartilhar com Felipe
conectividade, unidade e casos degenerados antes de consolidar os resultados.

| Medida | Definição proposta | Uso e ressalvas |
| --- | --- | --- |
| Ocupação `p` | voxels abertos / total | Faixa alvo `[p_min,p_max]` ainda a escolher; registrar proporção, não só penalidade. |
| Maior componente `c` | voxels abertos da maior componente / abertos, conectividade 6 | `0` se sem ar; `1` também pode ocorrer com um único voxel ou tudo aberto. |
| Componentes `n` | número de componentes de ar | Reportar isolamentos e tamanho; não interpretar contagem isolada como qualidade. |
| Degeneração | todo sólido ou todo ar | `structural-v1` marca ambos; proibir que ganhem recompensa por conectividade isolada. |
| EDT | distância ao sólido, conforme `structural-v1` | Descritiva; `None` nos casos degenerados, não é largura validada. |
| Atingibilidade | caminho entre entrada e saída previamente definidas | Proposta opcional; testar por busca em 6 vizinhos, reportando critério e distâncias. |
| Diversidade | distribuição entre volumes e duplicatas, em seeds reservadas | Definir representação e medidas antes de comparar; diferenças por deslocamento também influenciam distâncias. |

Potencial inicial sugerido: `F(s) = w_c*c - w_p*d(p,[p_min,p_max]) -
w_d*I(degenerado)`, onde `d = max(p_min-p, 0, p-p_max)` e `I` é 1 no caso
degenerado. Testar `r_t = F(s_{t+1}) - F(s_t) - custo_acao` e recompensa
terminal explícita caso necessária. Pesos, intervalo, custo, desconto e escala
são hipóteses: fixar após testes de sanidade e registrar; com desconto menor
que 1 essa diferença simples não garante preservação da política ótima.
Verificar exploits: todo sólido, todo ar, um voxel, ilhas, repetição sem efeito,
abrir/fechar em ciclos e parada prematura. Não declarar sucesso apenas por
retorno alto. Na avaliação relatar ocupação, componentes, proporção de volumes
válidos, alcance, diversidade, custo e dispersão, inclusive falhas.

## GAN: limites do problema e dados

- [ ] Inventariar fontes, semântica de ar/sólido, licença, quantidade de volumes
  independentes, resolução, eixos, parâmetros, sementes e procedência. Não usar
  a grade de parede do scan como se fosse vazio. Random Walk por waypoints tem
  dependência das cavernas de origem; tratar essa relação na separação dos dados.
- [ ] Definir unidade de independência (caverna/grafo/volume de origem); separar
  treino, validação e teste **antes** de extrair recortes ou aumentos. Seeds ou
  recortes sobrepostos de um mesmo grafo não são cavernas independentes.
- [ ] Se não houver dados válidos suficientes, executar apenas prova sintética:
  avaliar se a GAN imita a distribuição do gerador clássico, sem alegar que
  aprendeu a distribuição de cavernas reais. Comparar diretamente com o gerador
  que produziu os dados, inclusive custo de criar o dataset.
- [ ] Escolher arquitetura e resolução experimental após medir RAM/VRAM:
  começar pequeno (ex. 16³), lote e representação explícitos; 64³ é objetivo
  experimental e não garantia de viabilidade. Registrar tempo, pico de memória,
  limites de hardware, falhas e critério de interrupção; não inventar orçamento.
- [ ] Especificar entrada latente e domínio de saída do gerador, normalização,
  shape `(N,C,D,H,W)`, distribuição, pós-processamento e limiar fixado em
  validação, sem ajuste no teste. Salvar checkpoint, arquitetura e versão do
  conjunto; suportar `Volume3D` e seed para inferência reproduzível no ambiente.
- [ ] Verificar estabilidade, colapso de modos, duplicatas e memorização com
  vizinhos próximos entre dados e amostras; acompanhar diversidade, ocupação,
  conectividade e casos degenerados. Sem dados independentes, não declarar
  generalização. Reportar geração bruta e qualquer correção pós-processamento.
- [ ] Comparar distribuições em teste reservado, não IoU célula a célula entre
  cavernas não alinhadas. Separar custo de dados, treino, inferência e avaliação.

Uma DCGAN 3D simples é candidata de infraestrutura; World-GAN é alternativa
baseada em um exemplo e arquitetura multiescala, com hipóteses diferentes.
Escolher após auditoria e teste de memória, não assumir equivalência das duas.
A variante de exemplar único acima explicita a adaptação proposta de [R3].

## PCGARL: definição a confirmar

O nome PCGARL precisa de referência e objetivo acordados. Uma hipótese é um
**gerador RL** que cria cavernas e um **solucionador** que tenta atravessá-las,
inspirado em ARLPCG; isso não é o mesmo que uma GAN. A adaptação abaixo é
proposta, não reprodução demonstrada do artigo.

- [ ] Definir entrada/saída, movimentos, colisões, limites de passos, observação
  e o que caracteriza navegação válida; usar busca em grafo como oráculo de
  viabilidade para um cenário sem física e comparar com o solver aprendido.
- [ ] Definir como equilibrar desafio e solucionabilidade: por exemplo, retorno
  que favoreça dificuldade apenas em cavernas verificadas alcançáveis. Falha do
  solver não prova impossibilidade; evitá-la como único sinal de dificuldade.
- [ ] Determinar alternância e orçamento de treino de gerador e solver, seeds,
  checkpoints e congelamento de versões para avaliação. Comparar PCGRL simples
  e adversarial com orçamento informado, política aleatória e solver fixo.
- [ ] Avaliar em seeds reservadas, com solver congelado e oráculo: taxa de
  mapas alcançáveis, sucesso do solver, comprimento de caminho, custo, diversidade
  e falhas. Relatar custos de ambos os agentes, inferência e teste separadamente.
- [ ] Só acoplar o adversário depois de o ambiente PCGRL, oráculo e métricas
  passarem nos testes; evoluir contrato e tabela em conjunto com Felipe.

## Integração experimental e sequência recomendada

1. [ ] Confirmar com Felipe o contrato do CSV, a identificação de algoritmo,
   checkpoint, dados/partições, seed de treino, seed de geração, repetição,
   resolução, backend, tempo por etapa e estado/causa de falha; preservar NPZ.
2. [ ] Avaliar volumes artificiais conhecidos usando `evaluate_structure`;
   documentar ocupação e conectividade comuns, sem duplicar métricas em RL.
3. [ ] Executar o primeiro ciclo de GAN: auditar dados, congelar partições,
   testar memória e realizar a prova pequena. Na sequência, fechar o MDP e
   testes do ambiente PCGRL; ele não depende de um checkpoint GAN aprovado.
4. [ ] Fazer provas pequenas, congelar protocolos de validação e depois escalar
   para 64³ somente quando viabilidade e custo estiverem medidos.
5. [ ] Entregar os registros brutos para a tabela de Felipe; documentar hardware,
   versões, número de seeds, seleção, incerteza e experimentos mal sucedidos.

## Referências locais usadas na revisão do primeiro ciclo

Pasta da revisão original: `/home/midnavi/Documents/CESUPA/TCC/Docs/References`.
Na revisão de 15/11, as cópias foram consultadas em
`C:\Users\Vinícius Abdon\OneDrive - Associacao Cultural e Educacional do Para\TCC\Docs\References`.
Veja [identidades dos PDFs](auditoria/gan/papers.json) e
[referências adicionais](auditoria/gan/referencias-adicionais.md).
A paginação abaixo distingue páginas do PDF e páginas impressas do periódico.

- **[R1] Liu, J. et al. (2021).** *Deep learning for procedural content
  generation*. Neural Computing and Applications, 33, 19–37.
  DOI: `10.1007/s00521-020-05383-8`. Arquivo local:
  `Deep learning for procedural content generation.pdf`;
  [publicação](https://doi.org/10.1007/s00521-020-05383-8).
  Trechos usados: §4.4 (PDF p. 7, impressa p. 25) e §6.5 (PDF p. 13,
  impressa p. 31). É uma revisão; consultar os estudos primários antes de
  apresentar uma implementação como reprodução de DCGAN, TOAD-GAN ou CAN.
- **[R2] Summerville, A. et al. (2018).** *Procedural Content Generation via
  Machine Learning (PCGML)*, cópia arXiv `1702.00539v3`, de 7/5/2018.
  Arquivo local:
  `Procedural Content Generation via Machine Learning.pdf`;
  [preprint](https://arxiv.org/abs/1702.00539).
  Trechos usados: §IV.A–C (PDF pp. 11–12) e §IV.E (PDF p. 12).
  Fundamenta cuidados com dados, representação, funcionalidade e comparação;
  não especifica uma arquitetura GAN volumétrica para cavernas.

- **[R3] Awiszus, M.; Schubert, F.; Rosenhahn, B. (2021).** *World-GAN:
  a Generative Model for Minecraft Worlds*, cópia arXiv `2106.10155v1`,
  de 18/6/2021. Arquivo local:
  `World-GAN_ a Generative Model for Minecraft Worlds.pdf`;
  [preprint](https://arxiv.org/abs/2106.10155).
  Trechos usados: §III.B–E (PDF pp. 2–5), §IV.A–B e Tabelas II–III
  (PDF pp. 5–6), §V (PDF pp. 7–8). Evidência primária em Minecraft;
  a versão binária, a avaliação de túneis e a comparação com CA/Random Walk
  são adaptações propostas para este projeto.

- **[R4] Zheng, X.-Y.; Liu, Y.; Wang, P.-S.; Tong, X. (2022).**
  *SDF-StyleGAN: Implicit SDF-Based StyleGAN for 3D Shape Generation*.
  Fonte consultada: resumo dos autores e registro arXiv `2206.12055v1`.
  Disponível em: <https://arxiv.org/abs/2206.12055>.
  Fundamenta a possibilidade de discriminar formas por valores e gradientes
  de SDF; não fornece validação específica para cavernas ou para o contrato
  discreto do Felipe. A arquitetura completa deverá ser estudada antes de uma
  reprodução ou adoção de seus discriminadores especializados.

## Registro bibliográfico das alternativas

Os estudos centrais [R1–R4], PCGRL e ARLPCG estão registrados com referência,
resumo e uso concreto em
`Novas_Referências_Bibliográficas.docx`, na pasta externa indicada acima.
Ao propor outro artigo como alternativa experimental, acrescentar uma entrada
nesse documento, no mesmo padrão, verificando metadados e distinguindo evidência
publicada de adaptação para o TCC. Métodos apenas citados pelas revisões exigem
consulta à fonte primária antes de serem adotados como novas alternativas.

## Referências de partida

- [Khalifa et al., PCGRL (2020)](https://arxiv.org/abs/2001.09212): geração como problema sequencial de RL.
- [Gisslén et al., ARLPCG (2021)](https://arxiv.org/abs/2103.04847): gerador e solucionador adversariais; há cópia na pasta externa de referências.
- [Awiszus et al., World-GAN (2021)](https://arxiv.org/abs/2106.10155): modelo voxel multiescala a partir de um exemplo.

Os artigos motivam alternativas; adaptação para cavernas, recompensa, dados,
escalabilidade e critérios quantitativos ainda exigem pesquisa e validação.
