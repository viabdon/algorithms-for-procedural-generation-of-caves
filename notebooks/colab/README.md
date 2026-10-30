# Notebooks Colab

Use esta pasta para prototipação e treinamento após fechar o benchmark clássico
em Python. GAN e PCGRL ainda não geram volumes no código atual. Antes de treinar
GAN, audite a semântica e a independência dos volumes; dados sintéticos só
verificam a infraestrutura. Para PCGRL, comece com conectividade e ocupação,
sem IoU contra o scan do Elaphes.

Sugestão de ordem:

1. `00_environment_check.ipynb`: verificar GPU, CUDA, PyTorch e paths.
2. `01_train_gan_small_volume.ipynb`: treinar GAN 3D simplificada em `32³`.
3. `02_train_pcgrl_small_env.ipynb`: treinar ambiente PCGRL reduzido.
4. `03_export_checkpoints.ipynb`: salvar checkpoints em `models/checkpoints/` ou Google Drive.

O Colab deve ser tratado como ambiente de treinamento/prototipação, não como único ambiente de benchmark final, salvo se as tabelas identificarem claramente que os resultados vieram do Colab.
