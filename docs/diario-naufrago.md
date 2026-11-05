# Diário do Náufrago — Geração Procedural de Cavernas

> Registro pessoal do desenvolvimento dos algoritmos clássicos do TCC (Random
> Walk 3D e Cellular Automata 3D), escrito como um diário de bordo: a cada
> "dia" de exploração, o que foi tentado, o que funcionou, o que confundiu e o
> que ficou entendido.

## Como funciona este diário

Esta seção existe para que qualquer pessoa — ou qualquer IA — que abra este
arquivo do zero, sem o histórico da conversa original, saiba como continuar o
diário sem quebrar o padrão.

1. **O que é isto.** Um relato em primeira pessoa (voz do Felipe) do processo
   de implementação dos algoritmos, separado da documentação oficial do
   projeto. Decisões de arquitetura definitivas ficam em
   `docs/architecture.md`, o plano geral em `docs/roadmap.md`, e testes
   formais de parâmetros em `docs/experiments/`. Este diário é o "como
   cheguei lá" — o raciocínio, as tentativas e os tropeços — não a versão
   final polida.

2. **Unidade de registro: "Dia".** Um "Dia" não é necessariamente um dia de
   calendário — é uma fase de desenvolvimento ou de descoberta (ex.: "Dia 3 —
   entendendo a contagem de vizinhos do CA"). Pode ter uma data real
   associada quando fizer sentido, mas o que importa é a fase, não a data.

3. **Três tipos de anotação dentro de um Dia:**
   - **Tipo A — Narrativa.** O Felipe descreve livremente o que fez, o que
     tentou, o que deu certo ou errado, e o que entendeu no processo. Escrito
     em primeira pessoa, tom pessoal mas tecnicamente preciso.

     Se, durante a narrativa, o Felipe cometer um engano factual simples
     (nome errado de um conceito, número trocado etc.) e pedir correção, a
     correção entra **direto no texto da narrativa**, de forma que o texto
     fique consistente — isso **não** vira uma pergunta no Tipo B. O Tipo B
     não serve pra registrar "qual é o nome de X" — isso é só copydesk.
   - **Tipo B — Perguntas & Respostas.** Usado *só quando necessário* — quando
     a narrativa ficou inconclusiva ou faltou algo que o Felipe vai precisar
     pra lembrar depois **como e por que chegou a uma conclusão** (o objetivo
     deste diário é ele conseguir reler no futuro e reconstruir o raciocínio,
     não só o resultado). As perguntas são **sempre escritas por quem está
     assistindo** (Claude ou outra IA) — nunca pelo Felipe. O fluxo é:
     1. A IA identifica a lacuna e escreve a pergunta no diário, na entrada
        do Dia correspondente, deixando a resposta marcada como pendente.
     2. A IA faz a mesma pergunta no chat, pro Felipe responder ali.
     3. Quando o Felipe responde no chat, a IA registra a resposta no
        diário, substituindo o placeholder de pendente.
     Nem todo Dia precisa desse bloco — só entra quando falta algo sobre o
     *processo/entendimento*, não sobre nomenclatura ou fatos soltos. As
     narrativas do Felipe vêm por ditado de voz — erros de transcrição
     (palavra errada, nome trocado por outro parecido) **não** viram
     pergunta de Tipo B: corrija direto no Tipo A, sem comentário. O Tipo B é
     pra coisas que vão pesar na conclusão do TCC ou no entendimento do
     processo — não pra copydesk de transcrição.
   - **Tipo C — Dúvidas em aberto.** Perguntas rápidas que o próprio Felipe
     levanta pra si mesmo enquanto pesquisa ou implementa — do tipo "será que
     X ajudaria?" — mas sem desenvolver a resposta ali na hora. É basicamente
     uma garrafa lançada ao mar: fica registrada pra talvez ser respondida
     num Dia futuro, sem prazo. Diferente do Tipo B: aqui quem pergunta é o
     **Felipe**, não a IA, e a IA não tenta responder nem aprofundar — só
     registra a dúvida como citação curta, entre aspas, uma por linha, sem
     elaboração. Também diferente do Tipo B, não precisa virar par
     pergunta+resposta — pode ficar em aberto indefinidamente.

     Não é obrigatório ter dúvida em todo Dia. Mas é obrigatório **perguntar**
     — depois que o Felipe terminar de narrar um Dia, a IA sempre pergunta se
     tem alguma dúvida em aberto pra registrar antes de fechar a entrada. Só
     não entra bloco Tipo C se a resposta for "não".

4. **Passo a passo para adicionar uma nova entrada** (para uma IA que retome
   este arquivo sem contexto da conversa original):
   1. Leia o Sumário abaixo para saber em que fase a jornada parou.
   2. Deixe o Felipe narrar livremente o que aconteceu desde a última
      entrada — o que ele produziu, tentou, descobriu.
   3. Escreva essa narrativa como um bloco **Tipo A**, organizando mas
      preservando a voz em primeira pessoa. Marque o(s) algoritmo(s)
      envolvido(s) (Random Walk 3D, Cellular Automata 3D, ou Geral) e, se der,
      os commits relacionados (hash curto), pra rastreabilidade com o código.
   4. Se, durante a narrativa, o Felipe soltar uma dúvida rápida sem querer
      discorrer sobre ela, registre como citação no bloco **Tipo C**, logo
      depois do Tipo A (ou do Tipo B, se houver) — sem tentar responder.
      Acrescente essa dúvida também na tabela "Em aberto" do índice de
      [Dúvidas em aberto](#dúvidas-em-aberto). Depois que o Felipe terminar
      de narrar o Dia, pergunte explicitamente se tem mais alguma dúvida em
      aberto pra registrar antes de fechar a entrada — mesmo que a resposta
      seja "não" e o Tipo C fique de fora dessa vez.
   5. Avalie se falta algo pro Felipe conseguir reconstruir o raciocínio no
      futuro (não nomenclatura — isso corrige direto no Tipo A). Se faltar,
      escreva de 1 a 5 perguntas objetivas num bloco **Tipo B** logo depois
      do Tipo A, com a resposta marcada como pendente, faça as mesmas
      perguntas no chat, e só preencha a resposta no diário depois que o
      Felipe responder ali.
   6. Se uma entrada nova responder uma dúvida que estava em aberto no
      índice, mova a linha correspondente de "Em aberto" pra "Respondidas",
      apontando pro Dia onde ela foi resolvida.
   7. Atualize a tabela do Sumário com o título e um resumo de uma linha da
      nova entrada.
   8. Use o modelo em [Modelo para novas entradas](#modelo-para-novas-entradas)
      como esqueleto.

5. **Idioma e tom.** Português, sempre. Estilo pessoal (é um diário), mas sem
   sacrificar precisão técnica — este material apoia a redação do TCC.

6. **Commits deste arquivo.** Quando uma IA for commitar alterações neste
   diário (ou qualquer outro arquivo do repositório), **nunca** deve se
   colocar como coautora do commit — nada de trailer `Co-Authored-By`. A
   autoria do repositório é exclusivamente do Felipe Cruz, pois é o código de
   um TCC.

## Sumário

| Dia | Título | Algoritmo | Resumo |
|---|---|---|---|
| [Dia 0](#dia-0--abertura-do-diário) | Abertura do diário | Geral | Criação do arquivo e das regras de uso |
| [Dia 1](#dia-1--primeiro-contato-com-o-cellular-automata-vizinhanças-e-sensibilidade) | Primeiro contato com o Cellular Automata: vizinhanças e sensibilidade | Cellular Automata 3D | Estudo das vizinhanças de Von Neumann e Moore, e a ideia de tornar o gerador mais parametrizável/não-determinístico |
| [Dia 2](#dia-2--visualizando-resultados-padrões-de-decaimento-e-a-explosão-combinatória-de-parâmetros) | Visualizando resultados: padrões de decaimento e a explosão combinatória de parâmetros | Cellular Automata 3D | Plotagens 3D, padrões de crescimento/decaimento de células vivas ao longo das iterações, e o problema de escolher os melhores resultados entre milhares de combinações de parâmetros |
| [Dia 3](#dia-3--dois-extremos-estruturais-vazio-contínuo-e-bolsões-de-ar-isolados) | Dois extremos estruturais: vazio contínuo e bolsões de ar isolados | Cellular Automata 3D | Padrões estruturais nos extremos de sensibilidade — grande vazio contínuo sem caminhos vs. bolsões de ar isolados dentro da rocha — e a constatação de que nenhum dos dois ainda é uma caverna. Também esclarece que a plotagem inverte rocha/vazio só pra visualização |
| [Dia 4](#dia-4--hipótese-usar-random-walk-ou-l-system-como-conector-dos-bolsões-de-ar-do-ca) | Hipótese: usar Random Walk ou L-System como conector dos bolsões de ar do CA | Cellular Automata 3D, Random Walk 3D | Ideia (ainda sem conclusão) de usar o CA como esqueleto/"cérebro" e um algoritmo auxiliar pra conectar os bolsões de ar em nós, formando caminhos — e o problema de identificar esses bolsões como nós numa matriz 3D |
| [Dia 5](#dia-5--convolução-acelera-o-autômato-e-o-plot-de-trajetória-não-revela-um-padrão-claro) | Convolução acelera o autômato e o plot de trajetória não revela um padrão claro | Cellular Automata 3D | Troca do laço de contagem de vizinhos por convolução (400-580x mais rápido, equivalência testada bit a bit) com justificativa metodológica pro TCC, e implementação do gráfico de células vivas por iteração — que mostra os comportamentos já notados no Dia 2, mas sem revelar um padrão claro ligado aos parâmetros |
| [Dia 6](#dia-6--pesquisando-sdf-da-superfície-para-a-matriz-voxelizada) | Pesquisando SDF: da superfície para a matriz voxelizada | Cellular Automata 3D, Random Walk 3D | Ideia de usar o SDF de uma caverna de Random Walk como matriz de peso pro CA (reforçar voxels perto dela, apagar bolsões distantes); estudo da base do Signed Distance Field, a falta (até agora) de literatura aplicando SDF direto em matriz voxelizada em vez de malha, e o custo inviável da busca ingênua por distâncias em 2D e, pior, em 3D |
| [Dia 7](#dia-7--flood-fill-pra-separar-dentro-e-fora-e-a-mediatriz-como-atalho-pra-distância-euclidiana) | Flood fill pra separar dentro e fora, e a mediatriz como atalho pra distância euclidiana | Geral (SDF) | Flood fill escolhido pra classificar interior/exterior no Elaphes depois de comparar com vizinhos de face e CA de preenchimento (trata os 26 voxels de buraco fechado sem mexer no lado de fora e sem parâmetros, mas depende da parede externa estar fechada) e a mediatriz como ideia pra cortar comparações no cálculo da distância euclidiana |
| [Dia 8](#dia-8--ca-guiado-pelo-sdf-do-elaphes-segue-o-contorno-sem-copiar-a-caverna) | CA guiado pelo SDF do Elaphes: segue o contorno sem copiar a caverna | Cellular Automata 3D | SDF do Elaphes calculado (inundação + EDT exata do scipy) e somado como peso à contagem de vizinhos do CA: o vazio fica confinado ao entorno da caverna e a sensibilidade controla a espessura (IoU máximo 0,49 em s = 13), seguindo o contorno sem copiar. Próximo passo: trocar o Elaphes pelo SDF de uma caverna de Random Walk |

## Dúvidas em aberto

Dúvidas rápidas (Tipo C) levantadas pelo próprio Felipe em algum Dia, sem
resposta ainda. Quando uma delas for respondida — na narrativa de um Dia
futuro, por exemplo — a linha se move pra "Respondidas", apontando pra onde
a resposta ficou registrada.

### Em aberto

| Dúvida | Levantada em |
|---|---|
| "Será que o algoritmo consegue alcançar a melhor eficiência?" | [Dia 1](#dia-1--primeiro-contato-com-o-cellular-automata-vizinhanças-e-sensibilidade) |
| "Será que fazer testes com cálculos matemáticos mais sofisticados ajudaria a melhorar o resultado?" | [Dia 1](#dia-1--primeiro-contato-com-o-cellular-automata-vizinhanças-e-sensibilidade) |
| "Como escolher os melhores resultados entre as ~1620 combinações de parâmetros sem visualizar todas manualmente?" | [Dia 2](#dia-2--visualizando-resultados-padrões-de-decaimento-e-a-explosão-combinatória-de-parâmetros) |
| "Dá pra descobrir padrões de carregamento de seed dentro da parametrização do CA, agrupar esses padrões, e será que certos grupos dão resultados visuais melhores que outros?" | [Dia 2](#dia-2--visualizando-resultados-padrões-de-decaimento-e-a-explosão-combinatória-de-parâmetros) |
| "Como transformar essas estruturas (o grande vazio contínuo ou os bolsões de ar isolados) em algo que realmente pareça uma caverna, com espaços conectados e navegáveis?" | [Dia 3](#dia-3--dois-extremos-estruturais-vazio-contínuo-e-bolsões-de-ar-isolados) |
| "Usar Random Walk (ou L-System) como conector dos bolsões de ar do CA entrega resultados melhores do que rodar o Random Walk sozinho?" | [Dia 4](#dia-4--hipótese-usar-random-walk-ou-l-system-como-conector-dos-bolsões-de-ar-do-ca) |
| "Que técnica dá pra usar pra identificar os bolsões de ar como nós dentro de uma matriz 3D?" | [Dia 4](#dia-4--hipótese-usar-random-walk-ou-l-system-como-conector-dos-bolsões-de-ar-do-ca) |
| "Dá pra classificar os comportamentos de crescimento/decaimento de células vivas a partir de parâmetros específicos do autômato?" | [Dia 5](#dia-5--convolução-acelera-o-autômato-e-o-plot-de-trajetória-não-revela-um-padrão-claro) |
| "Qual algoritmo otimiza o cálculo de distâncias em 3D?" | [Dia 6](#dia-6--pesquisando-sdf-da-superfície-para-a-matriz-voxelizada) |
| "Em que casos o flood fill não funciona, e como corrigir quando ele vazar?" | [Dia 7](#dia-7--flood-fill-pra-separar-dentro-e-fora-e-a-mediatriz-como-atalho-pra-distância-euclidiana) |
| "Quanto do vazio 'quase fechado' (26 → 48 → 64) é falha real e quanto é dobra da parede?" | [Dia 7](#dia-7--flood-fill-pra-separar-dentro-e-fora-e-a-mediatriz-como-atalho-pra-distância-euclidiana) |
| "A mediatriz entra de fato como otimização no cálculo do SDF?" | [Dia 7](#dia-7--flood-fill-pra-separar-dentro-e-fora-e-a-mediatriz-como-atalho-pra-distância-euclidiana) |
| "Um CA guiado pelo SDF de uma caverna de Random Walk chega tão perto de uma caverna real quanto o guiado pelo Elaphes?" | [Dia 8](#dia-8--ca-guiado-pelo-sdf-do-elaphes-segue-o-contorno-sem-copiar-a-caverna) |
| "Que sensibilidade (ou escala do peso) equilibra seguir o guia sem copiá-lo?" | [Dia 8](#dia-8--ca-guiado-pelo-sdf-do-elaphes-segue-o-contorno-sem-copiar-a-caverna) |

### Respondidas

| Dúvida | Levantada em | Respondida em |
|---|---|---|
| "Dá pra fazer outras plotagens auxiliares pra acompanhar o crescimento/decaimento das células vivas ao longo das iterações?" | Dia 2 | [Dia 5](#dia-5--convolução-acelera-o-autômato-e-o-plot-de-trajetória-não-revela-um-padrão-claro) — sim, implementado: gráfico de linha ao lado do 3D |
| "Dá pra aplicar SDF direto numa matriz voxelizada em vez de numa malha?" | Dia 6 | [Dia 8](#dia-8--ca-guiado-pelo-sdf-do-elaphes-segue-o-contorno-sem-copiar-a-caverna) — sim: inundação separa borda e interno, e a EDT exata do scipy dá a distância até a borda voxelizada |

---

## Dia 0 — Abertura do diário

**Algoritmo:** Geral

### Tipo A — Narrativa

Hoje criei este diário para registrar o processo de implementação dos
algoritmos que ficaram sob minha responsabilidade no TCC — Random Walk 3D e
Cellular Automata 3D. A ideia é ter um relato corrido, tipo diário de
náufrago, do que fui descobrindo no caminho, separado da documentação
"oficial" do projeto (`architecture.md`, `roadmap.md`, `experiments/`), que já
existe e continua sendo a fonte de verdade sobre decisões e resultados
formais.

Pelo histórico de commits, o Cellular Automata já tem bastante coisa pronta:
autômato manual com contagem de vizinhos, tratamento de borda configurável,
persistência dos volumes em `.npz`, plot volumétrico, menu de terminal para o
ciclo completo, e mais recentemente um refactor da medição de recursos
(profiling). A partir da próxima entrada, o diário passa a registrar o
raciocínio por trás dessas decisões e o que vier a seguir — incluindo o
início do Random Walk 3D.

---

## Dia 1 — Primeiro contato com o Cellular Automata: vizinhanças e sensibilidade

**Algoritmo:** Cellular Automata 3D

### Tipo A — Narrativa

Comecei estudando o que de fato é um autômato celular e percebi que o
resultado final depende de várias variáveis — entre elas, a forma como o
autômato "enxerga" os vizinhos de cada célula. Existem dois tipos clássicos
de vizinhança: **Von Neumann** (formato de cruz, só as faces ortogonais) e
**Moore** (o cubo/quadrado completo, incluindo diagonais). Eu tinha as
contagens de 3D erradas de cabeça — pensei que fossem 26 e 8. O certo é:

| Vizinhança | 2D | 3D |
|---|---|---|
| Von Neumann | 4 vizinhos | 6 vizinhos |
| Moore | 8 vizinhos | 26 vizinhos |

O 8 que eu lembrava era o Moore em 2D; em 3D ele cresce pra 26 (6 faces + 12
arestas + 8 cantos do cubo 3x3x3 ao redor da célula), e o Von Neumann em 3D é
6, não 8.

Percebi também que mexer na quantidade de vizinhos considerados é algo bem
sensível para o resultado final do autômato. Isso me fez pensar num dilema:
inicialmente eu queria uma função bem básica — determinística, sempre
entregando o mesmo resultado pra mesma entrada — mas comecei a achar que,
para fins científicos (o TCC compara algoritmos), faz mais sentido ter
funções mais robustas e parametrizáveis, que aceitem variação controlada em
vez de um comportamento fixo.

### Tipo B — Perguntas & Respostas

**P1:** Conferindo o `count_neighbors` em
`src/cavegen/generators/cellular_automata/generator.py:55`: hoje ele varre um
cubo 3x3x3 inteiro ao redor de `(x, y, z)` — só implementa Moore 3D, sem
opção de Von Neumann — e o próprio docstring diz que a soma inclui "a própria
célula", ou seja, na prática são 27 células somadas (26 vizinhos + o
centro), não 26. Isso foi uma escolha deliberada (uma variante
"vizinhança + self", comum em geração de cavernas) ou passou batido e devia
excluir a célula central?

**R1:** Não dá pra considerar 100% um erro. A vizinhança em si tem 26
vizinhos, mas se a célula se conta como entidade, isso cria um viés: uma
célula que já é 1 ganha um "voto de desempate" a favor de continuar 1 (ela
mesma conta como vizinho vivo), o que dá prioridade pra manter células já
vivas e ajuda menos as células que são 0 a virarem 1. Ou seja, o autocount
não é necessariamente errado, mas introduz um comportamento observável —
talvez seja algo pra corrigir mais pra frente, mas por enquanto fica
registrado como algo a observar na produção do código.

**P2:** Você começou a dizer que queria migrar de uma função determinística
pra uma "mais robusta"/"mais volátil" para fins científicos, mas a frase
ficou pela metade. Isso significa parametrizar o autômato (vizinhança,
sensibilidade, seed, tratamento de borda etc. configuráveis) mantendo
reprodutibilidade via seed, em vez de deixar tudo fixo no código? E isso já
é o motivo por trás do `BorderTreatment` (zeros/ones/random) e do modificador
de seed com coluna central que já existem no projeto, ou é uma ideia nova que
ainda não foi implementada?

**R2:** É sobre poder receber parâmetros diferentes pra fazer experimentos
mais rápidos. Em vez de deixar toda modificação do autômato hardcoded e ter
que reescrever o código toda vez que eu quiser uma variação diferente, a
ideia é poder configurar os parâmetros mais facilmente e rodar vários de uma
vez — e, futuramente, talvez até usar um algoritmo genético pra descobrir os
melhores hiperparâmetros.

### Tipo C — Dúvidas em aberto

> "Será que o algoritmo consegue alcançar a melhor eficiência?"

> "Será que fazer testes com cálculos matemáticos mais sofisticados ajudaria a
> melhorar o resultado?"

---

## Dia 2 — Visualizando resultados: padrões de decaimento e a explosão combinatória de parâmetros

**Algoritmo:** Cellular Automata 3D

### Tipo A — Narrativa

Nessa fase foquei na visualização dos resultados. O gerador — já rodando com
a contagem de 27 vizinhos que veio do Dia 1 — está produzindo resultados que
eu consigo plotar em 3D e comparar entre execuções diferentes.

Percebi que o resultado é extremamente sensível à sensibilidade (ao
parâmetro que define quantos vizinhos uma célula precisa pra virar 1):
quando esse limiar exige muitos vizinhos, o autômato praticamente apaga
tudo — algumas execuções terminam sem nenhuma célula viva. Por causa disso,
incluí nas plotagens uma forma de conferir a quantidade de células vivas no
resultado final.

Testando manualmente vários parâmetros e comparando diferentes quantidades
de iterações, percebi pelo menos três padrões de comportamento diferentes,
em cubos de 64x64x64:
- **decaimento simples** — a quantidade de voxels vivos só cai;
- **decaimento e depois crescimento** — cai e depois sobe de novo, como uma
  parábola invertida;
- **decaimento suave** — cai bem pouco, um comportamento mais logarítmico.

Importante: esses padrões vieram de observar os resultados manualmente,
comparando execuções — ainda não fiz uma plotagem dedicada que acompanhe a
quantidade de células vivas ao longo do percurso (iteração por iteração)
dentro de uma mesma execução. Isso ainda é TODO — é a próxima plotagem
auxiliar que pretendo fazer.

O outro ponto é o crescimento combinatório dos parâmetros: cada parâmetro
novo multiplica a quantidade de combinações a testar (é uma análise
combinatória — um parâmetro com 2 valores vezes outro com 3 valores já dá 6
combinações, e por aí vai). Contando os parâmetros atuais do autômato — mas
sem contar a seed, que fica de fora dessa conta por enquanto e vai ganhar
sua própria história no Dia 3 — já estou em ~1620 combinações possíveis, o
que torna inviável visualizar uma por uma manualmente. Por isso estou
pensando em usar um arquivo **YAML** pra descrever vários parâmetros de uma
vez e gerar um lote de autômatos automaticamente, em vez de testar um por
um manualmente. Só que ainda não sei qual vai ser o método pra escolher os
melhores resultados dentro desse volume — ter os dados é uma coisa, saber
quais são os dados bons é outra, e visualizar as 1620 combinações uma por
uma não é viável (ver Tipo C).

### Tipo B — Perguntas & Respostas

**P1:** Pra bater com as ~1620 combinações (sem contar seed): quais
parâmetros estão entrando nessa conta hoje e quantos valores cada um está
assumindo nos testes?

**R1:** Todos os parâmetros atuais do autômato entram na conta, exceto a
seed — essa fica de fora por enquanto, porque foi implementada em outro
momento (não junto com essa fase) e vai virar sua própria entrada no Dia 3.

### Tipo C — Dúvidas em aberto

> "Como escolher os melhores resultados entre as ~1620 combinações de
> parâmetros sem ter que visualizar todas manualmente?"

> "Dá pra descobrir padrões de carregamento de seed dentro da parametrização
> do CA, agrupar esses padrões, e será que certos grupos dão resultados
> visuais melhores que outros?"

---

## Dia 3 — Dois extremos estruturais: vazio contínuo e bolsões de ar isolados

**Algoritmo:** Cellular Automata 3D

### Tipo A — Narrativa

Nessa fase aprofundei um pouco mais nos resultados visuais do autômato,
olhando o que diferentes combinações de parâmetros produzem
estruturalmente.

Uma clareza que vale registrar: metodologicamente, "célula viva" (o valor 1
da matriz) é rocha — isso está até no texto do menu do projeto ("chance de
cada célula nascer viva (rocha)"). Só que, **só pra facilitar a plotagem**,
eu ando considerando 1 como se fosse o vazio na hora de desenhar (uma matriz
invertida só pra visualização) — assim, o que aparece renderizado no plot é
a forma do espaço vazio (os "buracos" entre as rochas) em vez da casca
externa da rocha, que é bem menos informativa de se olhar. Ou seja: quanto
mais voxels aparecem concentrados no plot, mais espaço vazio tem ali.

Correção sobre o armazenamento: os dados **não** estão sendo salvos com
1 = rocha — hoje eles são salvos exatamente do jeito que já ficam prontos
pra plotagem (ou seja, na forma invertida). Pretendo, no futuro, adicionar
uma conversão (inverter todo 0 em 1 e todo 1 em 0) pra alinhar o que fica
salvo com a definição metodológica de 1 = rocha, mas isso ainda não foi
implementado — é uma decisão em aberto, a ser tomada mais pra frente.

Levando essa inversão em conta, encontrei dois padrões estruturais bem
distintos nos extremos (já reinterpretando em termos do espaço vazio, não
da rocha):
- Com **sensibilidade alta** — o que no plot aparecia como "um grande
  aglomerado" — o resultado real é um grande espaço vazio contínuo, sem
  formar caminhos distintos — uma cavidade única grande, não uma rede de
  túneis.
- Com **sensibilidade baixa** — os "geodos" no plot — não é rocha, é o
  oposto: bolsões de ar isolados dentro de uma massa de rocha — pequenas
  câmaras vazias e densas, mas desconectadas entre si.

Ainda não rodei a parametrização completa (as ~1620 combinações do Dia 2) —
testei manualmente entre 30 e 50 combinações até agora — mas esse padrão de
dois extremos já apareceu de forma consistente.

Nenhum dos dois extremos é, de fato, uma caverna ainda — falta a estrutura
de vazios conectados e navegáveis que se espera de uma caverna. Estamos
pensando em formas de resolver isso (ver Tipo C).

### Tipo C — Dúvidas em aberto

> "Como transformar essas estruturas (o grande vazio contínuo ou os bolsões
> de ar isolados) em algo que realmente pareça uma caverna, com espaços
> conectados e navegáveis?"

---

## Dia 4 — Hipótese: usar Random Walk ou L-System como conector dos bolsões de ar do CA

**Algoritmo:** Cellular Automata 3D, Random Walk 3D

### Tipo A — Narrativa

Depois de ver que nenhum dos extremos do autômato celular forma uma caverna
de verdade, comecei a pensar em usar algo auxiliar pra criar caminhos
conectados entre as regiões vazias. A ideia é usar o resultado do CA como
uma espécie de esqueleto ("cérebro do autômato") e rodar um segundo
algoritmo em cima dele pra conectar os pedaços.

Já temos o Random Walk implementado como algoritmo próprio, que gera
caverna sozinho. A ideia nova é diferente: usar esse mesmo Random Walk (ou
talvez um L-System) não como gerador solo, mas como o algoritmo que
conecta os bolsões de ar que o autômato celular já encontra. Ainda não
tirei nenhuma conclusão sobre isso — é só uma hipótese que quero investigar
(ver Tipo C).

Pra essa ideia funcionar, tem um problema separado que preciso resolver:
transformar os bolsões de ar — que são aglomerados de voxels, não pontos
fixos — em algo que dá pra tratar como "nó". Isso significa identificar,
dentro da matriz 3D, onde estão esses aglomerados e agrupá-los em nós, pra
poder rodar o algoritmo conector a partir de um nó até encontrar os
próximos. Ainda não sei que técnica vou usar pra essa identificação (ver
Tipo C).

De modo geral, ainda preciso discorrer mais sobre o que aplicar em cima dos
melhores resultados do autômato celular pra conseguir, de fato, gerar uma
caverna.

### Tipo C — Dúvidas em aberto

> "Usar Random Walk (ou um L-System) como 'cérebro' pra conectar os bolsões
> de ar do autômato entrega resultados melhores do que rodar o Random Walk
> sozinho?"

> "Que técnica dá pra usar pra identificar os bolsões de ar como nós dentro
> de uma matriz 3D?"

---

## Dia 5 — Convolução acelera o autômato e o plot de trajetória não revela um padrão claro

**Algoritmo:** Cellular Automata 3D
**Commits relacionados:** `8c3f90b`, `18a4b93`, `d79adb8`

### Tipo A — Narrativa

Troquei a contagem de vizinhos, que antes era um laço triplo em Python
percorrendo célula por célula, por uma convolução (`scipy.ndimage.convolve`
com um kernel 3x3x3). O tratamento de borda também mudou de abordagem: em vez
de ser um caso especial dentro da contagem, agora é uma moldura de 1 célula
aplicada à matriz antes da convolução, e descartada depois no recorte — isso
faz os três tratamentos (zeros, ones, random) passarem pelo mesmo caminho de
código. Validei que o resultado é idêntico ao laço antigo bit a bit, usando o
laço como oráculo de teste numa faixa de sensibilidades, formatos de volume e
quantidades de iteração diferentes; 24 dos 26 resultados que eu já tinha
salvo bateram exatamente igual depois do refactor — os 2 que não bateram usam
tratamento de borda aleatório, que não é reprodutível de qualquer jeito, com
ou sem convolução.

O ganho de performance foi bem relevante: de 2,67s pra 0,0064s por passo num
cubo 64³, uma aceleração de 400 a 580x. Isso é o tipo de coisa que ataca
diretamente o problema da explosão combinatória que registrei no Dia 2 (as
~1620 combinações de parâmetros) — testar lotes grandes de combinações passa
a ser muito mais viável em termos de tempo.

Essa otimização também ganhou uma justificativa metodológica própria, que
registrei em `docs/methodology-adjustments.md`: se o Cellular Automata vai
ser comparado contra métodos de IA — que rodam sobre bibliotecas compiladas —
deixá-lo rodando num laço Python puro seria uma comparação de desempenho
injusta. E, do lado da métrica de complexidade de implementação, a simetria
se mantém: continuo contando a definição da regra do autômato do mesmo jeito
que contaria a definição de um modelo de IA, sem entrar no código interno da
biblioteca de convolução.

Separado disso, implementei o plot que tinha ficado como TODO desde o Dia 2:
agora o autômato guarda a quantidade de células vivas em cada iteração (do
passo 0, a semente, até o último passo), e o HTML de visualização ganhou um
gráfico de linha ao lado da nuvem de pontos 3D. Resultados antigos continuam
só com o 3D, porque não tinham esse histórico salvo.

Com esse gráfico, consegui enfim visualizar os diferentes comportamentos de
quantidade de células vivas que já tinha notado manualmente no Dia 2
(decaimento simples, decaimento seguido de crescimento, decaimento suave) —
mas não consegui achar um padrão que explique quando cada comportamento
aparece. Talvez seja possível classificar esses comportamentos a partir de
parâmetros específicos do autômato, mas não tenho certeza de que isso
realmente seria vantajoso (ver Tipo C).

### Tipo C — Dúvidas em aberto

> "Dá pra classificar os comportamentos de crescimento/decaimento de células
> vivas a partir de parâmetros específicos do autômato?"

---

## Dia 6 — Pesquisando SDF: da superfície para a matriz voxelizada

**Algoritmo:** Cellular Automata 3D, Random Walk 3D (SDF como campo de controle)
**Commits relacionados:** `2290df4` (divisão de tarefas SDF/CA, em
`docs/tarefas-felipe-sdf-ca.md`)

### Tipo A — Narrativa

Nessa fase saí um pouco do código e fui pesquisar **SDF — Signed Distance
Field** (campo de distância com sinal). A ideia básica é calcular, pra cada
ponto, a distância até a superfície mais próxima, com o sinal indicando de
que lado ele está (dentro ou fora). Com isso dá pra saber, dentro da matriz,
quais regiões estão mais perto e quais estão mais longe das paredes.

O motivo de eu querer o SDF vem direto dos resultados do autômato: ele gera
vários bolsões de ar grandes, mas separados entre si (Dia 3). Em vez de
sobrepor uma caverna pronta por cima do resultado, a ideia é gerar uma
caverna com o Random Walk, que sozinho não gera uma caverna tão perfeita, e
calcular o SDF dela. Assim eu tenho, pra cada voxel, a distância mínima até
essa caverna, e esse SDF vira uma **matriz 3D de suporte** à matriz gerada a
partir da seed.

Como o próprio CA já decide cada voxel pela quantidade de vizinhos, essa
matriz auxiliar entraria como um **peso**: voxels mais próximos da caverna do
Random Walk ganham peso maior, e os muito distantes ganham peso menor. Na
prática, o autômato tenderia a seguir o formato do Random Walk. Os bolsões
muito afastados, que antes apareciam soltos em várias das imagens geradas,
tenderiam a sumir, e os que estão perto da caverna se reforçariam. O
objetivo é deixar o resultado do CA com mais cara de caverna. Isso é uma
evolução da hipótese do Dia 4: lá o Random Walk seria um conector entre os
bolsões, e aqui ele vira um guia para o próprio autômato.

O problema é que, no que encontrei até agora, o SDF aparece quase sempre
aplicado a **malhas**, ou seja, superfícies. Mesmo quando o objeto é 3D, o
que se mede é a distância até uma superfície descrita por uma malha. Ainda
não achei literatura que sustente aplicar o SDF diretamente numa **matriz
voxelizada**, que é o formato em que o autômato trabalha. Por isso voltei pra
base do assunto: quero entender bem a matemática, que não é muito complexa,
e procurar alguma solução já aplicada em 2D que dê pra levar pro 3D.

A outra preocupação é desempenho. A abordagem ingênua, que testa todos os
pontos pra achar a distância euclidiana até o mais próximo, já é inviável
numa matriz 2D, e em 3D fica muito pior. Então não basta entender o SDF: vou
precisar de algum algoritmo que otimize esse cálculo.

Vou continuar a pesquisa pra ver se dá pra implementar o SDF numa matriz 3D
voxelizada em vez de numa superfície, e qual é a melhor forma de otimizar.

### Tipo C — Dúvidas em aberto

> "Dá pra aplicar SDF direto numa matriz voxelizada em vez de numa malha?"

> "Qual algoritmo otimiza o cálculo de distâncias em 3D?"

---

## Dia 7 — Flood fill pra separar dentro e fora, e a mediatriz como atalho pra distância euclidiana

**Algoritmo:** Geral (SDF)
**Commits relacionados:** nenhum — experimento local em `elaphes_test/inundacao/`
(pasta fora do git, com README próprio)

### Tipo A — Narrativa

Uma das etapas do SDF é definir o que é borda e o que é parte interna, já
que o sinal do campo depende de saber de que lado da parede cada voxel
está. Pesquisando sobre isso, cheguei à conclusão de que a melhor forma
provavelmente é usar **flood fill**: partir de fora e "inundar" tudo que dá
pra alcançar sem atravessar a parede. O que não foi alcançado é interior.

Testei isso no Elaphes normalizado e voxelizado (grade 64³, 1049 voxels de
superfície depois de remover um outlier). O ponto de partida foi a
classificação mais simples, **por vizinhos de face**: é borda todo voxel
cheio que tenha pelo menos uma face vazia. Ela erra no Elaphes porque o
modelo tem **falhas internas**, ou seja, vazios fechados no meio da caverna.
Os voxels que encostam nesses vazios saem como borda, mesmo cercados de
parede.

Primeiro tentei tapar essas falhas com um CA de preenchimento antes de
classificar. A regra é `cheio | (vizinhos >= s)`, que só acende voxels e
nunca apaga, então a caverna nunca ficou mais fina. Depois comparei com o
flood fill:

| abordagem | parâmetros | buracos fechados tratados (de 26) | voxels alterados por fora | borda (1) | interno (2) |
|---|---|---|---|---|---|
| Vizinhos de face, sem preenchimento | 6 vizinhos de face | 0 | 0 | 853 | 196 |
| CA von Neumann | s = 5 de 6; 2 iterações (4 dá igual) | 11 | **2** | 817 | 245 |
| CA Moore | s = 20 de 26; 2 iterações | 15 | 0 | 812 | 252 |
| CA Moore | s = 20 de 26; 4 iterações | 18 | 0 | 806 | 261 |
| **Flood fill** | conectividade 6 (sem ajuste) | **26** | **0** | **783** | **292** |

"Por fora" é um vazio ligado ao lado de fora da grade que o método
preencheu, engordando a caverna. Nas linhas do CA, borda e interno vêm da
classificação por vizinhos de face, aplicada depois do preenchimento.

O CA ajudou, mas esbarrou em três limites. Primeiro, a regra é local: ela
não diferencia um vazio interno de uma dobra côncava da parede externa, e
por isso o von Neumann preencheu 2 voxels por fora. Segundo, ele para cedo:
o von Neumann estabiliza na 2ª iteração e o Moore na 3ª, e o melhor caso
pegou só 18 dos 26 voxels de buraco. Terceiro, ele tem três parâmetros pra
calibrar (vizinhança, sensibilidade e iterações). Testei sensibilidades de 4
a 6 no von Neumann e de 14 a 22 no Moore, e baixar a sensibilidade preenche
mais, mas aumenta o risco de engordar por fora.

O flood fill troca o critério local por um global. Em vez de perguntar
"esse vazio tem muitos vizinhos cheios?", ele pergunta "existe um caminho
desse vazio até o lado de fora sem atravessar parede?". Com isso ele
encontrou os 26 voxels de buraco fechado (6 grupos, o maior com 17). Ele não
mexe no lado de fora, porque tudo o que a água alcança é externo por
definição, e não tem parâmetro pra calibrar. Também passou pra interno 70
voxels que a classificação por vizinhos de face marcava como borda só porque
encostavam num buraco fechado. Os dois métodos concordam: tudo o que o CA
Moore preencheu estava dentro dos 26 voxels do flood fill.

Um detalhe que liga isso ao resto do meu trabalho: o flood fill também é um
autômato celular. O `scipy.ndimage.binary_fill_holes` funciona como um CA
com vizinhança de von Neumann, sensibilidade 1, borda `ONES` (fora da grade
é água) e máscara (só vazio vira água), iterado até estabilizar. Só mudou a
regra. A vizinhança de 6 é proposital: com Moore, a água passaria na
diagonal por frestas de canto, e paredes quase fechadas vazariam.

A limitação é que o flood fill exige que a **parede externa** esteja
fechada. O meio da caverna pode ter falhas, e é isso que ele resolve. Mas
basta uma fresta contínua de vazios até o lado de fora pra água entrar e o
buraco inteiro virar externo. Pra estimar quanto vazio está "quase fechado",
tapei frestas pequenas com um *closing* morfológico antes de inundar. O
vazio interno subiu de 26 pra 48 voxels com frestas de até 1 voxel, e pra 64
com frestas de até 2. É uma estimativa por cima, porque o *closing* também
pode tapar dobras reais da parede. Ainda preciso entender bem esses casos e
como corrigir quando der problema. Algumas opções são o *closing*, um CA de
preenchimento antes de inundar ou uma grade mais grossa. Mas, pro arquivo
que temos hoje pra comparação, o flood fill foi o melhor dos métodos
testados.

O ponto principal agora é otimizar o cálculo da distância euclidiana do
SDF. Uma das ideias que encontrei é usar a **mediatriz** (o *perpendicular
bisector* da literatura em inglês; em 3D, o plano mediador): pega dois
pontos e traça a reta, ou o plano, que corta o segmento entre eles ao meio.
Todo ponto de um lado desse plano está mais perto de um dos dois pontos do
que do outro. Com isso, dá pra descartar comparações inteiras de uma vez em
vez de testar ponto contra ponto, o que cortaria bastante operações.

Ainda preciso estudar mais antes de colocar isso de fato no projeto. Fica
registrado como opção de otimização pra quando o SDF estiver implementado.

### Tipo C — Dúvidas em aberto

> "Em que casos o flood fill não funciona, e como corrigir quando ele vazar?"

> "Quanto do vazio 'quase fechado' (26 → 48 → 64) é falha real e quanto é
> dobra da parede?"

> "A mediatriz entra de fato como otimização no cálculo do SDF?"

---

## Dia 8 — CA guiado pelo SDF do Elaphes: segue o contorno sem copiar a caverna

**Algoritmo:** Cellular Automata 3D (SDF como peso)
**Commits relacionados:** `d20feaf`, `429a4b5` (pipeline do SDF); `286414f`,
`d016569`, `47331a3` (peso no CA); `3fe3ede` (plot)

### Tipo A — Narrativa

Depois de estudar a base do SDF, implementei ele e usei como peso no
Cellular Automata. A pasta `sdf_temp/` continua no projeto porque o SDF
ainda vai servir pra uma métrica futura, a de proximidade com uma caverna
real, mas por enquanto não vou mexer muito nela. O foco aqui foi outro:
usar o SDF pra enviesar o CA.

A pipeline do SDF ficou em duas etapas. A primeira é a inundação do Dia 7,
que saiu do experimento local e entrou no git, reproduzindo o resultado
anterior bit a bit (783 voxels de borda, 292 internos, 26 de buraco
fechado). A segunda calcula a distância euclidiana de cada voxel até a
borda mais próxima com a EDT exata do scipy (`distance_transform_edt`), e o
sinal vem da classificação da inundação: positivo dentro, negativo fora,
zero na borda. No Elaphes 64³ o campo vai de +2 no interno até −63,16 no
ponto mais distante do lado de fora. Esse sinal é o inverso do
`docs/architecture.md` (lá `SDF < 0` é vazio), então o arquivo gerado grava
a convenção usada, até alinhar isso com o Pablo.

Plotando o SDF, apareceu uma suspeita de água dentro da caverna, ou seja,
um voxel externo preso entre paredes. Não se confirmou: na grade inteira só
existe uma componente de água, ligada à borda da grade. O ponto suspeito
estava na frente da parede, projetado por cima do interno, e a paleta
pintava o externo próximo com uma cor parecida com a do interno.

No CA, o peso entra de um jeito simples: a matriz de peso é somada à
contagem de vizinhos de cada célula antes da comparação com a
sensibilidade, em todo passo. Dentro da caverna o peso é positivo e dá
vizinhos extras, então a célula vira vazio mais fácil. Fora ele é negativo
e tira vizinhos, e a partir de certa distância nem os 27 vizinhos vivos
alcançam a sensibilidade. É o mecanismo que eu imaginava no Dia 6 pra fazer
os bolsões distantes sumirem. Sem peso (ou com peso zero) o CA é o básico,
testado bit a bit, e fica como baseline da comparação CA × CA+SDF. Os pesos
ficam guardados ao lado das seeds, com a origem e a convenção de sinal
anotadas, e o menu deixa escolher o peso na hora de rodar.

E funcionou: consegui de fato enviesar o CA. Na seed 001 (64³, p = 0,5,
borda zeros, 3 iterações), o peso confina o vazio ao entorno do Elaphes, e
a sensibilidade passa a controlar a espessura da caverna. De 6 a 11, o CA
cobre todo o Elaphes mais um halo em volta. Em 13 a sobreposição com o
Elaphes é a maior (IoU 0,49). De 14 em diante ele corrói a caverna: em
s = 14 sobram 678 vazios, contra 108.128 do mesmo CA sem peso.

O que mais me interessa é que ele segue a trajetória do Elaphes, mas não
imita o Elaphes. Mesmo no melhor caso a sobreposição fica perto da metade,
então o CA não reproduz a caverna voxel a voxel, só acompanha o contorno
dela. Pra mim esse é o melhor comportamento possível. Em vez dos vários
bolsões separados que eu tinha antes (Dia 3), agora tenho uma aproximação
de estrutura de caverna real, com caminhos bem estruturados como os do
Elaphes, mas com o grau de naturalidade que vem do próprio CA.

Um detalhe de visualização: o plot do CA desenhava a largura na vertical, e
o CA guiado pelo Elaphes saía em pé, com a caverna deitada virando uma
coluna. O cálculo sempre esteve alinhado, só o desenho girava. Corrigi pra
altura ficar na vertical, como nos plots do Elaphes e do SDF, e o plot
ganhou a opção de colorir cada célula pela quantidade de vizinhos, o que
separa a superfície do miolo.

Ainda falta a parte mais importante. Até aqui eu usei uma caverna real pra
enviesar o CA, então é óbvio que o resultado se parece com uma caverna. E
se o guia for uma caverna feita pelo Random Walk? Cavernas reais mapeadas
são dados limitados. O ideal é que tudo seja procedural: gerar a caverna
com o Random Walk, calcular o SDF dela e rodar o CA em cima desse SDF, pra
chegar no melhor nível de caverna possível sem depender de um dado real.
Ainda não sei se os resultados vão ser tão bons quanto com o Elaphes.

### Tipo C — Dúvidas em aberto

> "Um CA guiado pelo SDF de uma caverna de Random Walk chega tão perto de
> uma caverna real quanto o guiado pelo Elaphes?"

> "Que sensibilidade (ou escala do peso) equilibra seguir o guia sem
> copiá-lo?"

---

## Modelo para novas entradas

Copie o bloco abaixo para criar a próxima entrada. Apague o bloco Tipo B
inteiro se a fase não precisar dele.

```markdown
## Dia N — [título curto da fase]

**Algoritmo:** [Random Walk 3D | Cellular Automata 3D | Geral]
**Commits relacionados:** [hash curto, opcional]

### Tipo A — Narrativa

[Relato em primeira pessoa: o que foi feito, tentado, o que funcionou ou não,
o que ficou entendido.]

### Tipo B — Perguntas & Respostas

[Perguntas escritas pela IA, sobre o processo/entendimento — nunca sobre
nomenclatura ou fatos soltos (isso corrige direto no Tipo A). Faça as mesmas
perguntas no chat antes de preencher a resposta aqui.]

**P1:** [pergunta da IA]
**R1:** *(pendente — perguntar no chat e preencher depois que o Felipe
responder)*

**P2:** [...]
**R2:** *(pendente)*

### Tipo C — Dúvidas em aberto

[Citações curtas de dúvidas do próprio Felipe, sem elaborar. Adicione cada
uma também na tabela "Em aberto" do índice de Dúvidas em aberto.]

> "[dúvida do Felipe, como pergunta curta]"

> "[...]"
```
