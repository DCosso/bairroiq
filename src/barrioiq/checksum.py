import hashlib


def calcular_sha256(conteudo: bytes) -> str:
    """Calcula o hash SHA-256 de um conteúdo."""
    return hashlib.sha256(conteudo).hexdigest()
