# Convenções de teste

- Ao implementar ou alterar comportamento Python, crie ou atualize um teste
  automatizado em `tests/` quando a mudança introduzir um contrato observável,
  uma validação, um caso de borda ou uma correção de regressão.
- Antes de concluir uma alteração Python, execute a suíte de testes disponível
  e uma checagem de importação ou exemplo pequeno pertinente.
- Não crie testes apenas para detalhes privados de implementação; priorize o
  comportamento público e os contratos relevantes para o pipeline.

# Convenções de commit

- Escreva um assunto curto e um corpo de commit com estas três seções
  numeradas, sempre nesta ordem:
  1. O que havia sido planejado.
  2. O que foi feito, incluindo verificações relevantes.
  3. O que será feito após este commit.
- Distinga resultados confirmados de hipóteses e deixe explícitas as
  pendências que dependem de validação experimental.

# Ambiente para documentos

- As bibliotecas de leitura e edição de DOCX/PDF estão instaladas no ambiente
  persistente `/home/midnavi/.local/share/codex-artifacts-venv`.
- Para scripts que usam `python-docx`, `pypdf`, `pdfplumber`, `pdf2image`,
  `reportlab` ou `Pillow`, use
  `/home/midnavi/.local/share/codex-artifacts-venv/bin/python`.
- Verifique esse ambiente antes de instalar dependências novamente. Ele é um
  ambiente dedicado a documentos, separado do ambiente Python do projeto.
