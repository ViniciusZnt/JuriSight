"""Envio de e-mail: a conexão é sempre cifrada (TLS direto na 465, STARTTLS nas outras)."""
import smtplib

import pytest

from auth import envio_email


class _SMTPFalso:
    def __init__(self, host, porta, timeout=None, context=None):
        self.chamadas = [("conectar", host, porta, context is not None)]
        self.falhar_starttls = False
        _SMTPFalso.ultimo = self

    def starttls(self, context=None):
        self.chamadas.append(("starttls", context is not None))
        if self.falhar_starttls:
            raise smtplib.SMTPNotSupportedError("sem STARTTLS")

    def login(self, usuario, senha):
        self.chamadas.append(("login", usuario))

    def send_message(self, mensagem):
        self.chamadas.append(("enviar", mensagem["To"]))

    def close(self):
        self.chamadas.append(("fechar",))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.chamadas.append(("sair",))


@pytest.fixture
def smtp(monkeypatch):
    monkeypatch.setattr(envio_email.smtplib, "SMTP", _SMTPFalso)
    monkeypatch.setattr(envio_email.smtplib, "SMTP_SSL", _SMTPFalso)
    monkeypatch.setenv("SMTP_HOST", "smtp.exemplo.invalid")
    monkeypatch.setenv("SMTP_USUARIO", "app@exemplo.invalid")
    monkeypatch.setenv("SMTP_SENHA", "x")
    return monkeypatch


def test_porta_587_faz_starttls_antes_do_login(smtp):
    smtp.setenv("SMTP_PORT", "587")
    envio_email.enviar("pessoa@exemplo.invalid", "Assunto", "Texto")
    nomes = [c[0] for c in _SMTPFalso.ultimo.chamadas]
    assert nomes == ["conectar", "starttls", "login", "enviar", "sair"]
    assert ("starttls", True) in _SMTPFalso.ultimo.chamadas  # com contexto TLS


def test_porta_465_usa_tls_direto_sem_starttls(smtp):
    smtp.setenv("SMTP_PORT", "465")
    envio_email.enviar("pessoa@exemplo.invalid", "Assunto", "Texto")
    chamadas = _SMTPFalso.ultimo.chamadas
    assert chamadas[0] == ("conectar", "smtp.exemplo.invalid", 465, True)
    assert "starttls" not in [c[0] for c in chamadas]


def test_starttls_falhando_fecha_a_conexao_e_nao_envia(smtp, monkeypatch):
    smtp.setenv("SMTP_PORT", "587")
    original = _SMTPFalso.__init__

    def init_que_falha(self, *a, **k):
        original(self, *a, **k)
        self.falhar_starttls = True

    monkeypatch.setattr(_SMTPFalso, "__init__", init_que_falha)
    with pytest.raises(smtplib.SMTPNotSupportedError):
        envio_email.enviar("pessoa@exemplo.invalid", "Assunto", "Texto")
    nomes = [c[0] for c in _SMTPFalso.ultimo.chamadas]
    assert nomes == ["conectar", "starttls", "fechar"]
