"""
Envio de e-mail por SMTP, só com a biblioteca padrão, para o link de redefinição de senha
(issue #14). Configuração pelo ambiente:

    SMTP_HOST        servidor (sem ele, `configurado()` é False e a API avisa que a
                     recuperação por e-mail está indisponível, em vez de fingir que enviou)
    SMTP_PORT        587 (STARTTLS, padrão) ou 465 (TLS direto)
    SMTP_USUARIO     login no servidor, se ele exigir
    SMTP_SENHA       senha ou senha de app
    SMTP_REMETENTE   endereço "De:" (padrão: SMTP_USUARIO)
"""
from __future__ import annotations

import os
import smtplib
import ssl
from email.message import EmailMessage

TIMEOUT_S = 15


def configurado() -> bool:
    return bool(os.getenv("SMTP_HOST", "").strip())


def _conectar(host: str, porta: int) -> smtplib.SMTP:
    """Conexão já cifrada: TLS direto na 465; nas outras portas, STARTTLS logo após conectar
    (nada trafega em claro). Se o STARTTLS falhar, fecha a conexão antes de repassar o erro."""
    contexto = ssl.create_default_context()
    if porta == 465:
        return smtplib.SMTP_SSL(host, porta, context=contexto, timeout=TIMEOUT_S)
    servidor = smtplib.SMTP(host, porta, timeout=TIMEOUT_S)
    try:
        servidor.starttls(context=contexto)
    except BaseException:
        servidor.close()
        raise
    return servidor


def enviar(para: str, assunto: str, texto: str) -> None:
    """Envia um e-mail de texto simples. Levanta smtplib.SMTPException/OSError se falhar."""
    host = os.environ["SMTP_HOST"].strip()
    porta = int(os.getenv("SMTP_PORT", "587"))
    usuario = os.getenv("SMTP_USUARIO", "").strip()
    mensagem = EmailMessage()
    mensagem["From"] = os.getenv("SMTP_REMETENTE", "").strip() or usuario
    mensagem["To"] = para
    mensagem["Subject"] = assunto
    mensagem.set_content(texto)

    with _conectar(host, porta) as servidor:
        if usuario:
            servidor.login(usuario, os.getenv("SMTP_SENHA", ""))
        servidor.send_message(mensagem)
