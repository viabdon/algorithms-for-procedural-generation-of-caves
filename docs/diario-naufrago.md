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
     *processo/entendimento*, não sobre nomenclatura ou fatos soltos.
   - **Tipo C — Dúvidas em aberto.** Perguntas rápidas que o próprio Felipe
     levanta pra si mesmo enquanto pesquisa ou implementa — do tipo "será que
     X ajudaria?" — mas sem desenvolver a resposta ali na hora. É basicamente
     uma garrafa lançada ao mar: fica registrada pra talvez ser respondida
     num Dia futuro, sem prazo. Diferente do Tipo B: aqui quem pergunta é o
     **Felipe**, não a IA, e a IA não tenta responder nem aprofundar — só
     registra a dúvida como citação curta, entre aspas, uma por linha, sem
     elaboração. Também diferente do Tipo B, não precisa virar par
     pergunta+resposta — pode ficar em aberto indefinidamente.

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
      [Dúvidas em aberto](#dúvidas-em-aberto).
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

## Dúvidas em aberto

Dúvidas rápidas (Tipo C) levantadas pelo próprio Felipe em algum Dia, sem
resposta ainda. Quando uma delas for respondida — na narrativa de um Dia
futuro, por exemplo — a linha se move pra "Respondidas", apontando pra onde
a resposta ficou registrada.

### Em aberto

| Dúvida | Levantada em |
|---|---|
| *(nenhuma ainda)* | |

### Respondidas

| Dúvida | Levantada em | Respondida em |
|---|---|---|
| *(nenhuma ainda)* | | |

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
