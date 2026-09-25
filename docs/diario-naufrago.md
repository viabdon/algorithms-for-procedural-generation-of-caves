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

3. **Dois tipos de anotação dentro de um Dia:**
   - **Tipo A — Narrativa.** O Felipe descreve livremente o que fez, o que
     tentou, o que deu certo ou errado, e o que entendeu no processo. Escrito
     em primeira pessoa, tom pessoal mas tecnicamente preciso.
   - **Tipo B — Perguntas & Respostas.** Usado *só quando necessário* — quando
     a narrativa ficou inconclusiva, confusa, ou quando vale a pena fixar um
     conceito de um jeito mais fácil de lembrar depois. Quem está assistindo
     (Claude ou outra IA) faz perguntas objetivas sobre o tema, o Felipe
     responde, e o par pergunta+resposta é registrado. Nem todo Dia precisa
     desse bloco — só entra quando ajuda a clarear algo.

4. **Passo a passo para adicionar uma nova entrada** (para uma IA que retome
   este arquivo sem contexto da conversa original):
   1. Leia o Sumário abaixo para saber em que fase a jornada parou.
   2. Deixe o Felipe narrar livremente o que aconteceu desde a última
      entrada — o que ele produziu, tentou, descobriu.
   3. Escreva essa narrativa como um bloco **Tipo A**, organizando mas
      preservando a voz em primeira pessoa. Marque o(s) algoritmo(s)
      envolvido(s) (Random Walk 3D, Cellular Automata 3D, ou Geral) e, se der,
      os commits relacionados (hash curto), pra rastreabilidade com o código.
   4. Avalie se a explicação ficou completa e clara. Se não — se algo ficou
      solto, contraditório, ou é um conceito que vale a pena fixar melhor —
      monte de 2 a 5 perguntas objetivas sobre o tema, peça as respostas ao
      Felipe, e registre como bloco **Tipo B** logo depois do Tipo A da mesma
      entrada.
   5. Atualize a tabela do Sumário com o título e um resumo de uma linha da
      nova entrada.
   6. Use o modelo em [Modelo para novas entradas](#modelo-para-novas-entradas)
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
autômato "enxerga" os vizinhos de cada célula. Lembrei que existem (pelo
menos) dois tipos clássicos de vizinhança: um em formato de cruz, e outro que
enxerga tudo em volta, incluindo as diagonais, mas não tinha certeza dos
nomes nem de quantos vizinhos cada um via em 3D — pedi correção sobre isso
(ver Tipo B).

Percebi também que mexer na quantidade de vizinhos considerados é algo bem
sensível para o resultado final do autômato. Isso me fez pensar num dilema:
inicialmente eu queria uma função bem básica — determinística, sempre
entregando o mesmo resultado pra mesma entrada — mas comecei a achar que,
para fins científicos (o TCC compara algoritmos), faz mais sentido ter
funções mais robustas e parametrizáveis, que aceitem variação controlada em
vez de um comportamento fixo. Esse pensamento ainda ficou incompleto (ver
pergunta aberta no Tipo B).

### Tipo B — Perguntas & Respostas

**P1 (Felipe perguntou, corrigindo o entendimento):** Quais são os nomes
corretos das duas vizinhanças clássicas de autômato celular, e quantos
vizinhos cada uma enxerga em 2D e em 3D?

**R1:** Os nomes estão certos — **Von Neumann** (a "cruz") e **Moore** (o
"quadrado"/"cubo cheio", o nome que faltava). As contagens:

| Vizinhança | 2D | 3D |
|---|---|---|
| Von Neumann (cruz — só faces ortogonais) | 4 vizinhos | 6 vizinhos |
| Moore (cubo/quadrado completo, incluindo diagonais) | 8 vizinhos | 26 vizinhos |

Ou seja, em 3D não é "26 e 8" — é **26 (Moore) e 6 (Von Neumann)**. O 8 que
você lembrou é o Moore *2D*; em 3D ele cresce pra 26 porque conta as 6 faces
+ 12 arestas + 8 cantos do cubo 3x3x3 ao redor da célula.

**P2 (verificação no código atual):** O `count_neighbors` em
`src/cavegen/generators/cellular_automata/generator.py:55` varre um cubo
3x3x3 inteiro ao redor de `(x, y, z)` — ou seja, hoje o gerador só implementa
**Moore 3D**, não tem Von Neumann como opção. Só que o docstring da função diz
"incluindo a própria célula": o laço soma as **27** células do cubo (26
vizinhos + a célula central), não só os 26 vizinhos. Isso é intencional (uma
variante "vizinhança + self" bem comum em geração de cavernas), ou era pra
excluir a célula central e não excluiu?

**R2:** *(em aberto — responder na próxima entrada)*

**P3 (completando o raciocínio cortado):** Você começou a dizer que queria
migrar de uma função determinística pra uma "mais robusta"/"mais volátil"
para fins científicos, mas a frase ficou pela metade. Você quis dizer
parametrizar o autômato (permitir variar vizinhança, sensibilidade, seed,
tratamento de borda etc. por configuração, mantendo reprodutibilidade via
seed) em vez de ter tudo fixo no código? Isso bate com o `BorderTreatment`
(zeros/ones/random) e a seed com coluna central que já existem no projeto?

**R3:** *(em aberto — responder na próxima entrada)*

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

**P1:** [pergunta objetiva sobre o tema]
**R1:** [resposta do Felipe]

**P2:** [...]
**R2:** [...]
```
