# Evidência adicional para a arquitetura GAN — 15/11/2026

As sete cópias locais consultadas estão identificadas por tamanho, número de
páginas e SHA-256 em [papers.json](papers.json). O plano mantém [R1–R4] e
explica as adaptações; este registro complementa a bibliografia externa sem
alterar o DOCX fora do repositório.

| Referência primária / acesso | O que fundamenta e o que não demonstra |
| --- | --- |
| Wu, J.; Zhang, C.; Xue, T.; Freeman, W. T.; Tenenbaum, J. B. (2016). *Learning a Probabilistic Latent Space of Object Shapes via 3D Generative-Adversarial Modeling*. NeurIPS 29. [Publicação dos autores](https://proceedings.neurips.cc/paper/2016/hash/44f683a84163b3523afe57c2e008bc8c-Abstract.html), §3.1 / Figura 1. | Demonstra geração voxel 64³ de objetos com GAN volumétrica. Motiva a baseline global; nossa dimensão/distribuição latente, capacidade e blocos diferem. Não valida cavernas ou aprendizagem com quatro scans. |
| Mescheder, L.; Geiger, A.; Nowozin, S. (2018). *Which Training Methods for GANs do actually Converge?* ICML, PMLR 80, 3481–3490. [Artigo e PDF](https://proceedings.mlr.press/v80/mescheder18a.html), §4, Eq. 9. | Analisa estabilidade local sob hipóteses e propõe penalidade de gradiente real centrada em zero. Motiva R1 e instance noise. Gamma, frequência esparsa e sua aplicação 3D são escolhas do projeto; o teorema não garante convergência da nossa rede. |
| Odena, A.; Dumoulin, V.; Olah, C. (2016). *Deconvolution and Checkerboard Artifacts*. Distill. DOI 10.23915/distill.00003. [Estudo dos autores](https://distill.pub/2016/deconv-checkerboard/). | Discute sobreposição desigual e resize-convolution em imagens. Motivou nearest + Conv3D; a eficácia sobre artefatos volumétricos exige medição própria. |
| Zhao, S.; Liu, Z.; Lin, J.; Zhu, J.-Y.; Han, S. (2020). *Differentiable Augmentation for Data-Efficient GAN Training*. NeurIPS 33, 7559–7570. [Artigo dos autores](https://arxiv.org/abs/2006.10738). | Aumentos diferenciáveis em exemplos reais e gerados melhoram eficiência nos domínios estudados. Implementamos apenas rotações yaw, não a receita completa para imagens, nem um aumento adaptativo ADA. |
| Karras, T.; Aittala, M.; Hellsten, J.; Laine, S.; Lehtinen, J.; Aila, T. (2020). *Training Generative Adversarial Networks with Limited Data*. NeurIPS 33. [Artigo dos autores](https://arxiv.org/abs/2006.06676). | Reforça o risco de sobreajuste do discriminador com poucos dados. ADA não foi implementada; resultados com milhares de imagens não são garantia para duas cavernas por fold. |
| Racine, T. et al. (2025). *KarstConduitCatalogue: a dataset of LiDAR derived point clouds for the analysis of karstic conduit geometry and morphology*. Earth System Science Data 17, 4671–4690. [Artigo final](https://essd.copernicus.org/articles/17/4671/2025/). | A cópia local é o preprint `essd-2025-194` de 26/05/2025, 28 páginas. A versão final foi conferida online. Lacunas e reconstruções incertas justificam validar interior e região inferida; licenças dos dados não são substituídas pela licença do artigo. |
| Jouves, J. et al. (2017). *Speleogenesis, geometry, and topology of caves: A quantitative study of 3D karst conduits*. Geomorphology 298. DOI 10.1016/j.geomorph.2017.09.019. [Cópia dos autores](https://escholarship.org/uc/item/0wc9m3nv). | Leitura local: resumo e abordagem morfométrica. Motiva separar geometria/topologia e contexto de cavernas; os descritores de grafos do artigo não foram apresentados como equivalentes às métricas voxel implementadas. |
| Withington, O.; Cook, M.; Tokarchuk, L. (2024). *On the Evaluation of Procedural Level Generation Systems*. FDG 2024. DOI 10.1145/3649921.3650016. [Preprint dos autores](https://arxiv.org/abs/2404.18657). | Leitura local: taxonomia e limites de avaliação. Motiva declarar critérios, controles e alcance; não oferece uma medida pronta de proximidade entre cavernas 3D. |

As decisões que não vêm diretamente desses trabalhos estão identificadas no
plano: triagem de geometria, split por caverna, score de validação,
hiperparâmetros, representação TSDF discreta, JS dos padrões 2³ e protocolo de
seeds. Todas exigem experimentos; foram implementadas e testadas como contratos
de software, sem resultados de aprendizagem nas referências.

Para carregamento de checkpoints foi conferida a
[documentação oficial de torch.load](https://docs.pytorch.org/docs/stable/generated/torch.load):
usa-se `weights_only=True`, com tensores e tipos primitivos nos checkpoints.
A [documentação de reprodutibilidade](https://docs.pytorch.org/docs/stable/notes/randomness.html)
fundamenta a ressalva sobre versões/plataformas; o teste de retomada idêntica
foi feito em CPU no mesmo ambiente, sem alegação equivalente para qualquer GPU.
