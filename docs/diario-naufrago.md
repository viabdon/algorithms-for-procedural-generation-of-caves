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
