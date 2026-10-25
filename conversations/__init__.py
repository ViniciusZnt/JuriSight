"""
conversations — persistência das conversas de busca do usuário.

Guarda só o que importa para a busca (EstruturaArgumentativa revisada +
resultados do /query) — nunca o PDF enviado nem seu texto extraído. Ver
conversations/db.py para o porquê e o schema completo.
"""
from conversations.store import Conversa, ConversaNaoEncontradaError, ConversaStore

__all__ = ["Conversa", "ConversaNaoEncontradaError", "ConversaStore"]
