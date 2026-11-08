"""Ambiente comum dos testes, aplicado antes de importar o app."""
import os

# O cookie de sessão é Secure por padrão (issue #17); o cliente de teste fala HTTP, como o dev
# local, então desliga explicitamente — o mesmo que o .env.example faz.
os.environ.setdefault("COOKIE_SECURE", "false")
