from pathlib import Path

# Todas as pastas de dados do CA ficam ao lado deste arquivo.
PACKAGE_DIR = Path(__file__).resolve().parent

def storage_dir(name: str) -> Path:
    """
        Caminho de uma pasta de dados do pacote, como "seeds" ou "results".
        name: nome da pasta.
    """
    return PACKAGE_DIR / name

def used_ids(directory: Path, prefix: str) -> set:
    """
        Números de 3 dígitos já ocupados por arquivos na pasta.
        directory: pasta consultada.
        prefix: começo do nome do arquivo, antes do número.
    """
    padrao = f"{prefix}_[0-9][0-9][0-9].npz"
    return {int(caminho.stem[-3:]) for caminho in Path(directory).glob(padrao)}

def next_id(directory: Path, prefix: str) -> int:
    """
        Próximo número da sequência, um acima do maior já usado na pasta.
        directory: pasta consultada.
        prefix: começo do nome do arquivo, antes do número.
    """
    usados = used_ids(directory, prefix)
    proximo = max(usados) + 1 if usados else 1
    if proximo > 999:
        raise RuntimeError(f"A sequência de 3 dígitos chegou ao fim em {directory}.")

    return proximo

def build_path(directory: Path, prefix: str, file_id: int) -> Path:
    """
        Caminho de um arquivo da sequência, no formato prefix_000.npz.
        directory: pasta onde o arquivo fica.
        prefix: começo do nome do arquivo, antes do número.
        file_id: número de identificação do arquivo.
    """
    return Path(directory) / f"{prefix}_{file_id:03d}.npz"
