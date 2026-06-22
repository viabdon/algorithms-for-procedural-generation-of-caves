# Notebooks Colab

Use esta pasta para notebooks de prototipação e treinamento.

Sugestão de ordem:

1. `00_environment_check.ipynb`: verificar GPU, CUDA, PyTorch e paths.
2. `01_train_gan_small_volume.ipynb`: treinar GAN 3D simplificada em `32³`.
3. `02_train_pcgrl_small_env.ipynb`: treinar ambiente PCGRL reduzido.
4. `03_export_checkpoints.ipynb`: salvar checkpoints em `models/checkpoints/` ou Google Drive.

O Colab deve ser tratado como ambiente de treinamento/prototipação, não como único ambiente de benchmark final, salvo se as tabelas identificarem claramente que os resultados vieram do Colab.
