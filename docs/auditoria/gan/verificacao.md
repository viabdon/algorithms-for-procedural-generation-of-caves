# Verificações da implementação GAN — 15/11/2026

**Nenhum treino foi executado nas referências.** As atualizações de pesos
abaixo são exclusivamente testes automatizados de um ou dois passos sobre
pequenas máscaras artificiais. Não há checkpoint de caverna treinado nem
resultado de desempenho da GAN. `models/checkpoints/` permanece sem modelo
novo. O bloqueio dos dados é um resultado da auditoria, não uma falha de
aprendizado medida.

## Atualização para o commit de 17/11/2026

O planejamento dos recortes foi detalhado e vinculado ao preparo de volumes,
roadmap, tarefas, arquitetura e resumo simples. Seleção incremental dos pontos,
correção de precisão, seções/tampas e novo voxelizador continuam propostas;
nenhum recorte real foi produzido. O empacotador Colab passou a incluir esses
documentos, com teste de presença e integridade. O `uv.lock` foi sincronizado
com os extras `gan` e `test`; `uv lock --check` confirmou 131 pacotes resolvidos.

Verificações repetidas nesta data:

- **44 testes GAN/auditoria passaram** em 9,58 s, incluindo o pacote com os
  novos documentos. Foram usados apenas dados artificiais nos passos de pesos.
- Suíte de `tests/`: **184 passaram, 2 ignorados, 1 falhou e 2 erros de
  coleta**, com 162 subtestes aprovados, em 18,08 s. Persistem o arquivo F32
  mapeado durante a limpeza no Windows e as duas importações ausentes do CA.
- A descoberta foi limitada a `tests/`, evitando diretórios temporários de
  execuções anteriores. Para o teste isolado, uma pasta nova no workspace
  foi passada em `--basetemp`, pois o diretório temporário padrão do pytest
  herdava permissões incompatíveis da sessão anterior.
- Notebook preservado com suas 18 células e flags de treino desativadas.
  Um contador de execução sem outputs foi limpo para versionamento, mantendo
  os textos das células. Schema, código e importações foram conferidos.

Comandos de teste desta revisão (usar um `--basetemp` novo a cada execução):

```powershell
$env:PYTHONPATH='src'
.\.venv-gan\Scripts\python.exe -m pytest tests/test_gan.py tests/test_gan_reference_data.py -q --basetemp tmp/pytest-gan-20261117-clean -o cache_dir=tmp/pytest-gan-20261117
# Para a suíte, definir TMP/TEMP e MPLCONFIGDIR como descrito abaixo.
.\.venv-gan\Scripts\python.exe -m pytest tests -q --continue-on-collection-errors -o cache_dir=tmp/pytest-suite-20261117
```

Os logs recentes estão em `tmp/verification-2026-11-17-gan.txt` e
`tmp/verification-2026-11-17-tests.txt`, ignorados pelo Git. A solicitação
atual inclui um commit; as observações de 15/11 sobre ausência de commit
referem-se somente àquela entrega.

## Ambiente de execução local

Windows, Python **3.12.10**, torch **2.15.0+cpu**, NumPy **2.5.4**, SciPy
**1.18.1**, pytest **9.2.0**, em `.venv-gan`. O `.venv` original foi preservado:
seu `pyvenv.cfg` aponta para `/usr/bin`, indisponível no Windows. O ambiente de
documentos `/home/midnavi/.local/share/codex-artifacts-venv` foi procurado e
não existe aqui; a distribuição WSL Ubuntu também não está instalada.
`pypdf` foi usado no ambiente Windows disponível para consultar as cópias
locais. Nenhuma nuvem bruta ou PDF foi modificado.

Essas versões são as observadas no teste, não uma garantia sobre a imagem
futura do Colab. O notebook instala dependências mínimas e registra as versões
efetivas; torch/CUDA podem ser diferentes na VM. Não foi executada uma VM
Colab nem medido seu consumo de VRAM. O custo de backward 64³, R1 e Adam deve
ser verificado no hardware escolhido após corrigir os dados.

## Código novo

```powershell
$env:PYTHONPATH='src'
.\.venv-gan\Scripts\python.exe -m pytest tests/test_gan.py tests/test_gan_reference_data.py -q
```

Resultado: **44 testes passaram** (9,07 s na execução isolada). Cobertura de
contratos públicos:

- Inventário determinístico de superfície/ar, binariedade, reprodução do
  flood fill, resíduos geométricos e duplicatas.
- Folds por caverna, integridade/hash, vazamento, mudança de conteúdo, paths
  fora da raiz e insuficiência de fontes. Auditoria ainda emite relatório
  quando não pode formar partições; não reutiliza um split antigo.
- Shapes e domínios de saída em 16³/32³/64³ nas duas representações.
- Gradientes finitos, R1 e atualização de G/D em máscaras artificiais 16³.
- Salvamento e retomada de modelos/Adam/RNG, com próxima atualização e campo
  idênticos no mesmo ambiente CPU.
- Inferência com seeds 0, 1, 42, 2³²−1 e 2⁶³−1; validação de entradas e
  preservação do RNG global durante a geração; round-trip `Volume3D`/NPZ.
- TSDF reconstruindo todo-ar, todo-sólido, cubo e linha fina na borda por sinal;
  limiar explícito de ocupação e rejeição de campos não finitos.
- Loader exigindo opt-in para candidatos e recusando geometria residual;
  configuração inválida não aceita silenciosamente.
- Métricas detectando controle degenerado, cópia e duplicação; padrões 2³ e
  score invariantes à repetição idêntica da referência.
- Uma execução mínima completa com fixtures artificiais: checkpoint escolhido,
  exportação, métricas de teste e proteção contra sobrescrita.
- Falha simulada gerando status e preservando o último checkpoint completo;
  avaliação rejeitando pesos de passo zero.
- ZIP com manifesto de hashes e ausência de nuvens brutas.

Além disso, G/D da configuração padrão 64³ foram importados e executaram
forward em CPU: saída G `(1,1,64,64,64)`, saída D `(1,)`, parâmetros G/D
**1.354.801 / 697.585**. As importações e o parse dos módulos novos passaram.
Os quatro folds verificaram hashes dos NPZ disponíveis. O preflight CLI
recusou o interior Archamps por maior componente/EDT insuficientes, conforme
esperado. Não iniciou otimização.

## Notebook e dados

O notebook tem **18 células**, schema nbformat 4 válido, código Python
compilável, outputs vazios e contadores de execução nulos. O fluxo padrão
foi executado localmente contra um ZIP extraído: hashes verificados,
259 seeds previstas, `DATA_READY=False`, treino e avaliação desativados,
nenhum checkpoint criado. Nesse smoke test, `/content/cavegan` foi substituído
por uma pasta temporária local, a célula `%pip` não foi executada e a função
de exibição IPython foi substituída por impressão do nome da imagem. Upload,
Drive e CUDA reais ainda dependem do Colab; não são alegados como testados.

A figura `projections.png` foi renderizada e inspecionada visualmente nos três
planos. O manifesto contém nove NPZ, e os interiores conferiram byte a byte
com a recomputação binária do flood fill. Os arquivos originais foram apenas
lidos. O pacote final pode ser regenerado pelo `prepare_colab`; o manifesto
interno identifica cada arquivo incluído e não contém as nuvens de vários GB.

## Suíte geral: falhas anteriores ainda abertas

Foi executada a suíte inteira com `--continue-on-collection-errors`, para não
ocultar os testes que conseguem ser coletados:

```powershell
$env:PYTHONPATH='src'
$env:TMP=(Join-Path (Get-Location) 'tmp\tests')
$env:TEMP=$env:TMP
$env:MPLCONFIGDIR=(Join-Path (Get-Location) 'tmp\matplotlib')
# Criar as pastas antes de executar.
.\.venv-gan\Scripts\python.exe -m pytest -q --continue-on-collection-errors
```

Resultado final: **184 passaram, 2 ignorados, 1 falhou e 2 erros de coleta**,
além de **162 subtestes aprovados** (17,52 s). A suíte geral não está verde.

| Pendência | Evidência / relação com esta alteração |
| --- | --- |
| `tests/test_experiment_records.py` e `tests/test_menu.py` não coletam | `ImportError`: `cavegen.generators.cellular_automata` não exporta `generate_cellular_automata`, importado pelo benchmark. Já constava como pendência no plano e foi observado antes de integrar a GAN. Não foram alterados esses módulos. |
| `tests/test_f32.py::F32ReaderTests::test_counts_maps_and_iterates_xyz_records` falha no Windows | `PermissionError: WinError 32` ao limpar `TemporaryDirectory` com `points.f32` ainda mapeado. O teste mantém a memmap aberta. O leitor F32 e esse teste não foram alterados. |

Na primeira execução com o TEMP padrão do Windows, quatro subtestes do runner
também divergiram entre caminho curto `VINCIU~1` e caminho resolvido com nome
completo. Usar TEMP dentro do workspace resolveu essa diferença, sem mudar
código. Plotly, dependência declarada no projeto, foi instalado no ambiente
de verificação para coletar os testes de visualização. As falhas restantes
não foram contornadas nem apresentadas como testes aprovados.

As saídas completas das verificações locais estão em `tmp/suite-final.txt` e
`tmp/notebook-smoke-report.txt` (artefatos temporários ignorados pelo Git).
Não houve commit automático nem modificação do DOCX bibliográfico externo.
