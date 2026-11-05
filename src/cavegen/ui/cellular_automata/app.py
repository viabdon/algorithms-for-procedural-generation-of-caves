"""Bancada de teste do autômato celular.

Faz o ciclo do menu (seed -> peso -> CA) pela barra lateral e mostra o
resultado na mesma página, sem abrir HTML no navegador. O CA roda em memória;
só vai para seeds/ e results/ quando se clica em Salvar.

O cache fica todo aqui, em funções que chamam o pacote do CA: o CA não importa
nada da interface.

    uv sync --extra ui
    uv run streamlit run src/cavegen/ui/cellular_automata/app.py
"""

import numpy as np
import streamlit as st

from cavegen.generators.cellular_automata.generator import BorderTreatment
from cavegen.generators.cellular_automata.menu import (
    EXPLICACAO_BORDAS,
    ITERACOES_PADRAO,
    MAX_VIZINHOS,
    PROBABILIDADE_PADRAO,
    SENSIBILIDADE_PADRAO,
    TAMANHO_PADRAO,
)
from cavegen.generators.cellular_automata.pesos import (
    load_peso_info,
    load_peso_matrix,
    used_peso_ids,
)
from cavegen.generators.cellular_automata.plot import MODOS_COR, PALETAS
from cavegen.generators.cellular_automata.results import (
    load_result,
    load_result_info,
    used_result_ids,
)
from cavegen.generators.cellular_automata.seeds import (
    generate_seed_matrix,
    load_seed_info,
    load_seed_matrix,
    used_seed_ids,
)
from cavegen.ui.cellular_automata.dados import (
    Execucao,
    historico_dos_passos,
    rodar_passo_a_passo,
    salvar,
)
from cavegen.ui.cellular_automata.figuras import (
    EIXOS_CORTE,
    celulas_visiveis,
    fatia,
    figura_3d,
    figura_cortes,
    figura_evolucao,
)

st.set_page_config(page_title="Bancada do CA", layout="wide")

AJUDA_SENSIBILIDADE = (
    "Mínimo de vizinhos vivos no cubo 3x3x3 (a própria célula conta) para a célula "
    "virar vazio no passo seguinte. Menor deixa mais vazio: abaixo de 10 quase tudo "
    "vira caverna. Maior deixa mais rocha: acima de 18 quase tudo fecha. Com "
    "probabilidade 0.5 a média é ~13.5, então 14 é o equilíbrio. Típico: 13 a 15."
)
AJUDA_LADO = ("Lado do cubo, em células. O volume tem lado³ células, então dobrar o "
              "lado multiplica o custo por 8. Típico: 64.")
AJUDA_PROBABILIDADE = ("Chance de cada célula nascer vazia. Perto de 0.5 o ruído sai "
                       "equilibrado; mais baixo nasce mais rocha. Típico: 0.45 a 0.50.")
AJUDA_ITERACOES = ("Quantas vezes o passo se repete. Cada passo suaviza as paredes; o "
                   "volume costuma estabilizar entre 3 e 5.")
AJUDA_PESO = ("Matriz somada à contagem de vizinhos antes da sensibilidade. Negativo "
              "(fora da caverna) tira vizinhos, positivo (dentro) dá vizinhos.")
AJUDA_SUPERFICIE = ("Desenha só as células vivas que encostam em rocha ou na borda. As "
                    "do miolo ficam escondidas de qualquer jeito, e tirá-las alivia o navegador.")


# --- cache: tudo o que lê disco ou monta figura pesada -----------------------

@st.cache_data(show_spinner=False)
def carregar_seed(seed_id: int) -> np.ndarray:
    return load_seed_matrix(seed_id)


@st.cache_data(show_spinner=False)
def carregar_peso(peso_id: int) -> np.ndarray:
    return load_peso_matrix(peso_id)


@st.cache_data(show_spinner=False)
def carregar_resultado(result_id: int) -> dict:
    return load_result(result_id)


@st.cache_resource(max_entries=16, show_spinner="montando a nuvem 3D...")
def nuvem_3d(chave: int, passo: int, _matriz, borda: str, modo: str, paleta: str,
             so_superficie: bool):
    """
        figura_3d guardada por (execução, passo, visual). O underscore em _matriz
        tira a matriz do hash: quem identifica o volume é a chave da execução.
    """
    return figura_3d(_matriz, borda, modo, paleta, so_superficie)


# --- rótulos -----------------------------------------------------------------

def rotulo_seed(seed_id: int) -> str:
    info = load_seed_info(seed_id)
    return f"{seed_id:03d} · {info['size']}³ · p={info['one_probability']}"


def rotulo_peso(peso_id) -> str:
    if peso_id is None:
        return "nenhum (CA básico)"
    return f"{peso_id:03d} · {load_peso_info(peso_id)['origem']}"


def rotulo_resultado(result_id: int) -> str:
    info = load_result_info(result_id)
    peso = f" · peso {info['peso_id']:03d}" if "peso_id" in info else ""
    return (f"{result_id:03d} · {info['size']}³ · seed {info['seed_id']:03d} · "
            f"s={info['sensitivity']} · {info['border_treatment']} · "
            f"it={info['iterations']}{peso}")


def descricao(execucao: Execucao) -> str:
    if execucao.seed_id is None:
        seed = f"seed sorteada (p={execucao.one_probability})"
    else:
        seed = f"seed {execucao.seed_id:03d}"
    peso = f" · peso {execucao.peso_id:03d}" if execucao.peso_id is not None else ""
    return (f"{execucao.lado}³ · {seed} · sensibilidade {execucao.sensitivity} · "
            f"borda {execucao.border_treatment} · {execucao.iterations} iterações{peso}")


# --- ações -------------------------------------------------------------------

def abrir(execucao: Execucao) -> None:
    st.session_state.execucao = execucao
    st.session_state.chave = st.session_state.get("chave", 0) + 1


def rodar(config: dict) -> None:
    if config["seed_id"] is None:
        seed = generate_seed_matrix(config["lado"], config["probabilidade"])
    else:
        seed = carregar_seed(config["seed_id"])
    peso = carregar_peso(config["peso_id"]) if config["peso_id"] is not None else None

    barra = st.progress(0.0, text="rodando o CA...")
    passos, segundos = rodar_passo_a_passo(
        seed, config["sensibilidade"], config["borda"], config["iteracoes"], peso,
        progress=lambda passo, total: barra.progress(passo / total,
                                                     text=f"passo {passo}/{total}"),
    )
    barra.empty()

    abrir(Execucao(
        seed=passos[0], final=passos[-1], historico=historico_dos_passos(passos),
        sensitivity=config["sensibilidade"], border_treatment=config["borda"].value,
        iterations=config["iteracoes"], passos=passos, seed_id=config["seed_id"],
        one_probability=config["probabilidade"], peso_id=config["peso_id"],
        segundos=segundos,
    ))


def abrir_gravado(result_id: int) -> None:
    dados = carregar_resultado(result_id)
    final = np.asarray(dados["matrix"], dtype=bool)
    historico = dados["live_cells_history"]
    if historico is None:
        # Resultado anterior ao histórico: só se conhece o passo final.
        historico = np.array([int(final.sum())])

    seed_id = dados["seed_id"]
    tem_seed = seed_id in used_seed_ids()
    abrir(Execucao(
        seed=carregar_seed(seed_id).astype(bool) if tem_seed else None,
        final=final, historico=np.asarray(historico),
        sensitivity=dados["sensitivity"], border_treatment=dados["border_treatment"],
        iterations=dados["iterations"], seed_id=seed_id,
        one_probability=load_seed_info(seed_id)["one_probability"] if tem_seed else None,
        peso_id=dados.get("peso_id"), result_id=result_id,
    ))


# --- barra lateral -----------------------------------------------------------

def barra_lateral() -> None:
    with st.sidebar:
        st.title("Autômato celular")

        st.subheader("1. Seed")
        seeds = sorted(used_seed_ids())
        origem = st.radio("origem da seed", ["sortear nova", "usar gravada"],
                          horizontal=True, label_visibility="collapsed")
        if origem == "usar gravada" and seeds:
            seed_id = st.selectbox("seed", seeds, index=len(seeds) - 1,
                                   format_func=rotulo_seed)
            info = load_seed_info(seed_id)
            lado, probabilidade = info["size"], info["one_probability"]
        else:
            if origem == "usar gravada":
                st.caption("nenhuma seed gravada ainda, sorteando uma nova.")
            seed_id = None
            lado = st.number_input("tamanho do lado", min_value=8, max_value=128,
                                   value=TAMANHO_PADRAO, step=8, help=AJUDA_LADO)
            probabilidade = st.slider("probabilidade de vazio", 0.0, 1.0,
                                      PROBABILIDADE_PADRAO, 0.01, help=AJUDA_PROBABILIDADE)

        st.subheader("2. Peso (SDF)")
        # O peso é somado posição por posição: só serve um do mesmo formato da seed.
        compativeis = [numero for numero in sorted(used_peso_ids())
                       if load_peso_info(numero)["shape"] == (lado, lado, lado)]
        peso_id = st.selectbox("peso", [None] + compativeis, format_func=rotulo_peso,
                               help=AJUDA_PESO, label_visibility="collapsed")
        if not compativeis:
            st.caption(f"nenhum peso {lado}³ gravado.")

        st.subheader("3. Autômato")
        sensibilidade = st.slider("sensibilidade", 0, MAX_VIZINHOS, SENSIBILIDADE_PADRAO,
                                  help=AJUDA_SENSIBILIDADE)
        bordas = list(BorderTreatment)
        borda = st.radio("tratamento de borda", bordas, format_func=lambda b: b.value,
                         captions=[EXPLICACAO_BORDAS[b] for b in bordas])
        iteracoes = st.number_input("iterações", min_value=1, max_value=50,
                                    value=ITERACOES_PADRAO, help=AJUDA_ITERACOES)

        execucao = st.session_state.get("execucao")
        coluna_rodar, coluna_salvar = st.columns(2)
        clicou_rodar = coluna_rodar.button("Rodar", type="primary", width="stretch")
        clicou_salvar = coluna_salvar.button(
            "Salvar", width="stretch",
            disabled=execucao is None or execucao.result_id is not None,
            help="Grava a seed (se for nova) e o resultado, no formato do menu.",
        )

        st.divider()
        st.subheader("Resultados gravados")
        gravados = sorted(used_result_ids(), reverse=True)
        if gravados:
            escolhido = st.selectbox("resultado", gravados, format_func=rotulo_resultado,
                                     label_visibility="collapsed")
            clicou_abrir = st.button("Abrir resultado", width="stretch")
        else:
            st.caption("nenhum resultado gravado ainda.")
            clicou_abrir = False

    if clicou_rodar:
        rodar(dict(seed_id=seed_id, lado=int(lado), probabilidade=float(probabilidade),
                   peso_id=peso_id, sensibilidade=int(sensibilidade), borda=borda,
                   iteracoes=int(iteracoes)))
    if clicou_salvar:
        seed_id_gravada, result_id = salvar(execucao)
        execucao.seed_id, execucao.result_id = seed_id_gravada, result_id
        st.toast(f"gravado como result_{result_id:03d} (seed {seed_id_gravada:03d})")
        st.rerun()
    if clicou_abrir:
        abrir_gravado(escolhido)


# --- área principal ----------------------------------------------------------

def passo_estavel(passos) -> int | None:
    """Primeiro passo idêntico ao anterior: dali em diante o volume não muda mais."""
    for passo in range(1, len(passos)):
        if np.array_equal(passos[passo], passos[passo - 1]):
            return passo
    return None


def cabecalho(execucao: Execucao) -> None:
    st.markdown(f"#### {descricao(execucao)}")

    vazio = 100 * execucao.historico[-1] / execucao.total_celulas
    vazio_seed = 100 * execucao.historico[0] / execucao.total_celulas
    colunas = st.columns(5)
    colunas[0].metric("vazio final", f"{vazio:.1f}%",
                      delta=f"{vazio - vazio_seed:+.1f} pp vs passo 0"
                      if execucao.historico.size > 1 else None,
                      delta_color="off")
    colunas[1].metric("células vivas", f"{int(execucao.historico[-1]):,}".replace(",", "."))
    colunas[2].metric("volume", f"{execucao.lado}³")
    colunas[3].metric("tempo do CA",
                      f"{execucao.segundos:.2f}s" if execucao.segundos is not None else "—",
                      help="Só referência de bancada; o benchmark usa o track_resources.")
    colunas[4].metric("arquivo", f"result_{execucao.result_id:03d}"
                      if execucao.result_id is not None else "não salvo")

    if vazio == 100:
        st.warning("Volume 100% vazio: a sensibilidade está baixa demais, tente um valor maior.")
    elif vazio == 0:
        st.warning("Volume 100% rocha: a sensibilidade está alta demais, tente um valor menor.")
    elif execucao.passos is not None:
        estavel = passo_estavel(execucao.passos)
        if estavel is not None:
            st.caption(f"o volume parou de mudar no passo {estavel}.")


def aba_3d(execucao: Execucao) -> None:
    coluna_figura, coluna_controles = st.columns([5, 1])
    with coluna_controles:
        st.radio("cor", MODOS_COR, index=MODOS_COR.index("vizinhos"), key="modo")
        st.selectbox("paleta", PALETAS, index=PALETAS.index("Purp"), key="paleta")
        st.toggle("só superfície", value=True, key="superficie", help=AJUDA_SUPERFICIE)
        desenhadas = (int(celulas_visiveis(execucao.final).sum())
                      if st.session_state.superficie else int(execucao.final.sum()))
        st.caption(f"{desenhadas:,} pontos na nuvem".replace(",", "."))

    with coluna_figura:
        st.plotly_chart(figura_do_passo(execucao, execucao.iterations if execucao.passos
                                        else -1), width="stretch", key="nuvem_final")


def figura_do_passo(execucao: Execucao, passo: int):
    matriz = execucao.final if passo < 0 else execucao.passos[passo]
    return nuvem_3d(st.session_state.chave, passo, matriz, execucao.border_treatment,
                    st.session_state.modo, st.session_state.paleta,
                    st.session_state.superficie)


@st.fragment
def aba_cortes(execucao: Execucao) -> None:
    # Fragmento: mexer no slider redesenha só os cortes, não a página inteira.
    coluna_eixo, coluna_indice = st.columns([1, 3])
    eixo = coluna_eixo.radio("cortar na", list(EIXOS_CORTE), horizontal=True)
    eixo_matriz = EIXOS_CORTE[eixo][0]
    tamanho = execucao.final.shape[eixo_matriz]
    indice = coluna_indice.slider("posição do corte", 0, tamanho - 1, tamanho // 2)

    paineis = []
    if execucao.seed is not None:
        paineis.append(("seed (passo 0)", fatia(execucao.seed, eixo, indice), "binario"))
    paineis.append((f"resultado (passo {execucao.iterations})",
                    fatia(execucao.final, eixo, indice), "binario"))
    if execucao.peso_id is not None:
        paineis.append((f"peso {execucao.peso_id:03d}",
                        fatia(carregar_peso(execucao.peso_id), eixo, indice), "peso"))

    st.plotly_chart(figura_cortes(paineis, eixo), width="stretch")
    st.caption("verde = vazio (caverna), cinza = rocha. No peso, azul é dentro da "
               "caverna de referência e vermelho é fora.")


@st.fragment
def aba_evolucao(execucao: Execucao) -> None:
    if execucao.passos is None:
        st.plotly_chart(figura_evolucao(execucao.historico, execucao.total_celulas),
                        width="stretch")
        st.caption("Resultado lido de arquivo: só o passo final está gravado. Rode de "
                   "novo pela barra lateral para navegar pelos passos.")
        return

    passo = st.slider("passo", 0, execucao.iterations, execucao.iterations)
    st.plotly_chart(figura_evolucao(execucao.historico, execucao.total_celulas, passo),
                    width="stretch")
    st.plotly_chart(figura_do_passo(execucao, passo), width="stretch", key="nuvem_passo")


def main() -> None:
    barra_lateral()

    execucao = st.session_state.get("execucao")
    if execucao is None:
        st.title("Bancada do autômato celular")
        st.info("Configure a seed, o peso e o autômato na barra lateral e clique em "
                "**Rodar**, ou abra um resultado gravado.")
        return

    cabecalho(execucao)
    tab_3d, tab_cortes, tab_evolucao = st.tabs(["3D", "Cortes 2D", "Evolução"])
    with tab_3d:
        aba_3d(execucao)
    with tab_cortes:
        aba_cortes(execucao)
    with tab_evolucao:
        aba_evolucao(execucao)


main()
