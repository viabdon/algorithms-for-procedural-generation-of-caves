# Notebooks Colab

O [notebook GAN](01_gan_reference_volumes.ipynb) está implementado e não foi
treinado. Consulte o [plano neural](../../docs/plano-redes-neurais.md) e a
[auditoria](../../docs/auditoria/gan/README.md) antes de executar. Os quatro
interiores atuais são resíduos de 1 a 98 voxels; o preflight bloqueia seu uso
como exemplos de cavernas resolvidas. Reduzir para 16³ apaga todo o ar.

## Preparar e abrir

1. No Windows, use um ambiente Python funcional. O `.venv` copiado de Linux
   não funciona nesta máquina; a verificação local usou `.venv-gan` com Python
   3.12. Defina `PYTHONPATH=src` ou instale o projeto no seu ambiente.
2. Gere o pacote com `python -m cavegen.training.prepare_colab`. O padrão é
   `data/processed/gan_colab_bundle.zip`; o comando recusa sobrescrever um ZIP
   existente. Ele verifica as partições e inclui código, configurações,
   auditoria, notebook, voxels e recibos. Não inclui nuvens brutas ou artigos.
   Inclui também os planos de reconstrução/recortes e o resumo do gargalo;
   o pacote não implementa nem gera os recortes planejados.
   Os NPZ são ignorados pelo Git: um clone sozinho não contém os dados.
3. Envie `01_gan_reference_volumes.ipynb` ao Colab, selecione uma VM com GPU e
   execute as células de instalação e upload. Envie o ZIP quando solicitado;
   o notebook confere o SHA-256 de cada arquivo.
4. Use `USE_DRIVE=True` se quiser persistir checkpoints entre sessões. Sem
   Drive, a pasta `/content/gan_runs` pode desaparecer com a VM.
5. Inspecione o inventário e o preflight. Nos dados desta entrega a mensagem
   `TREINO BLOQUEADO` é esperada. Corrija e valide a reconstrução, gere nova
   auditoria/partições/pacote e repita essa verificação antes de experimentar.

O notebook já contém a execução e retomada de treino, mas mantém
`RUN_TRAINING=False`. Configurações de ocupação e SDF ficam em `configs/gan`.
Para habilitar uma futura execução, escolha configuração/fold/seed, revise
o orçamento e mude a flag. `RESUME=True` usa o último passo completo de
`latest.pt`, preservando Adam e RNG. `best.pt` só é criado após validação;
não ajuste checkpoint ou limiar no teste. A primeira atualização pode falhar
por VRAM: não foi medida uma GPU Colab nesta revisão.

## Avaliar e exportar

A célula de avaliação também começa desativada (`RUN_EVALUATION=False`).
Depois de existir um checkpoint selecionado, ela compara sua geração à
caverna de teste reservada e aos controles de cópia/todo-sólido, preservando
todas as 259 seeds propostas. A lista pode ser alterada ou ampliada para
qualquer inteiro em `[0,2**63)`. Seeds não criam novas fontes de referência.

Para uso fora do notebook, após um futuro treino:

```bash
python -m cavegen.training.evaluate_gan \
  --checkpoint CAMINHO/best.pt --output results/gan_test \
  --seed-start 0 --count 256 --device cuda
# Ou uma lista explícita:
python -m cavegen.training.evaluate_gan \
  --checkpoint CAMINHO/best.pt --output results/gan_extremos \
  --seeds 0 42 4294967295 9223372036854775807
```

Guardar `evaluation.json`, campos `*.field.npz`, volumes `seed_N.npz`, logs,
configurações e checkpoints. Identificar hardware/versões como Colab nas
tabelas; não misturar seus tempos com tempos locais sem essa identificação.
PCGRL/PCGARL e a integração ao benchmark dos clássicos continuam propostas
independentes no plano.
