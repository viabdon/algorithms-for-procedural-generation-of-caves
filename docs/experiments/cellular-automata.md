# Teste NN — [nome curto]

**Objetivo da série:** medir como regra de borda, iterações, % inicial de rocha e sensibilidade (limiar) do autômato celular afetam conectividade e jogabilidade das cavernas geradas, comparando cada variação com o caso-base.

## Parâmetros

| Parâmetro | Caso-base | Este teste |
|---|---|---|
| Tamanho | 64x64x64 | |
| % inicial de rocha (r) | 50% | |
| Iterações (n) | 5 | |
| Regra de borda | rocha | |
| Sensibilidade do CA (T) | 13 vizinhos | |
| Seed | 0 | |

## Resultados

| Checkpoint | Fatia/imagem | open_ratio | largest_component_ratio |
|---|---|---|---|
| Inicial | | | |
| Final | | | |

## Observações

*(Conectou? Orgânico/jogável? Convergiu, estabilizou, oscilou ou divergiu?)*

## Conclusão

—

---

### Exemplo de preenchimento (formato de referência)

**TESTE 1 — regra de borda mais permissiva**

| Parâmetro | Caso-base | Este teste |
|---|---|---|
| Tamanho | 32x32x32 | 20x20x20 |
| % inicial de rocha (r) | 55% | 55% |
| Iterações (n) | 5 | 5 |
| Regra de borda | rocha | considerar 1 (chão) |
| Sensibilidade do CA (T) | 13 vizinhos | 5 vizinhos |
| Seed | 0 | 0 |