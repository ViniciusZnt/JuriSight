# Decisões de design — `auth/` (hashing de senha + JWT)

**Escopo desta peça:** só as primitivas de segurança (`auth/password.py`,
`auth/tokens.py`). Não há schema de banco nem endpoints aqui — ambos são
peças de outros agentes, em paralelo/depois. Nada neste pacote importa
Postgres, FastAPI ou qualquer coisa fora da stdlib + `pwdlib` + `PyJWT`.

## Hashing de senha: Argon2id, com bcrypt só como fallback de verificação

Argon2id é o KDF de senha memory-hard recomendado atualmente (OWASP Password
Storage Cheat Sheet) — bem mais caro de atacar em GPU/ASIC que bcrypt/PBKDF2,
que só custam CPU. `hash_password` usa exclusivamente Argon2id para hashes
novos. Bcrypt entra no `PasswordHash((Argon2Hasher(), BcryptHasher()))` só
como alvo que `verify_password` ainda reconhece — útil se este backend algum
dia herdar hashes de outro sistema — e nesse caso `verify_password` sinaliza
um `novo_hash` para a camada de persistência trocar o hash antigo pelo
Argon2id na hora do login (rehash-on-verify).

`verify_password` devolve `tuple[bool, str | None]` (não só `bool`) por esse
motivo: o rehash-on-verify precisa que quem chama saiba *quando* há um hash
novo para persistir, sem que este módulo precise conhecer a camada de
persistência (ela nem existe ainda — é peça de outro agente).

`DUMMY_HASH` é um hash Argon2id válido de uma senha aleatória e descartada,
calculado em import-time (não hardcoded como string). Existe para que a
peça de endpoints possa rodar `verify_password(senha, DUMMY_HASH)` quando o
lookup de usuário não encontra ninguém, pagando o mesmo custo de CPU que uma
verificação real — sem isso, a diferença de latência entre "usuário existe,
senha errada" e "usuário não existe" vaza por timing attack se um e-mail
está cadastrado. Calcular em import-time (em vez de uma string fixa, como o
template de referência faz) garante que o custo pago seja sempre o mesmo do
`Argon2Hasher` atual, mesmo que a lib mude seus parâmetros default numa
atualização futura.

## JWT: HS256, sem fallback de secret

HS256 (HMAC simétrico) em vez de RS256 porque JuriSight é um único backend
que emite e valida seus próprios tokens — RS256 (par de chaves assimétrico)
só compensa quando um serviço emite e OUTRO serviço, sem acesso à chave
privada, precisa validar (microserviços, gateway de terceiros). Não é o caso
aqui, então HS256 com um segredo forte é suficiente e mais simples — mesma
escolha do template de referência (`tiangolo/full-stack-fastapi-template`).

A chave (`JWT_SECRET_KEY`) só vem de variável de ambiente — **sem** fallback
hardcoded tipo `"changeme"`. `create_access_token`/`decode_access_token`
levantam `MissingSecretKeyError` na hora, se a variável não existir, em vez
de silenciosamente cair para um segredo previsível (isso seria uma
vulnerabilidade real: qualquer um lendo o código forjaria tokens válidos).

Expiração default: **30 minutos** (`DEFAULT_EXPIRES_DELTA`). Um access token
de vida curta é a prática recomendada — limita a janela de uso de um token
vazado. Sessões mais longas devem vir de um refresh token separado (fora do
escopo desta peça), não de alongar o access token. O parâmetro
`expires_delta` continua explícito em `create_access_token` para quem for
integrar isso poder sobrescrever caso o produto precise de outra política.

## Dependências novas (não instaladas via `uv add` — só reportadas)

Nenhuma das duas já existia em `pyproject.toml`/`uv.lock`. Comandos exatos
para quem for integrar este piece:

```
uv add "pwdlib[argon2,bcrypt]"
uv add "PyJWT>=2.9"
```

Os testes deste piece (`tests/test_auth.py`) foram rodados com essas
dependências resolvidas de forma efêmera via `uv run --with`, sem tocar
`pyproject.toml`/`uv.lock`:

```
uv run --with "pwdlib[argon2,bcrypt]" --with "PyJWT>=2.9" python -m pytest tests/test_auth.py -v
```

(Usar `python -m pytest` em vez do script `pytest` diretamente — com
`--with`, o console-script `pytest` resolvido pode vir do `.venv` do
projeto, que ainda não tem as libs novas; `python -m pytest` garante que o
interpretador certo, com o overlay efêmero, é usado.)

## Fora de escopo, propositalmente

- Nenhum lookup de usuário/banco (`auth.password`/`auth.tokens` são funções
  puras — string entra, resultado sai).
- Nenhum endpoint FastAPI, nenhum `Depends`, nenhum modelo Pydantic de
  request/response de login.
- `pyproject.toml` não foi editado (nem para adicionar as libs novas, nem a
  entrada `"auth*"` que `tool.setuptools.packages.find.include` precisaria
  para o pacote ser instalável via `pip install -e .`/build de distribuição
  — hoje `auth/` funciona para import direto e para os testes via pytest
  porque a raiz do repo não tem `__init__.py` e por isso entra no
  `sys.path`, mas **não** é resolvido pelo finder do editable-install atual
  — quem for integrar a peça de endpoints deve lembrar de adicionar
  `"auth*"` a esse include list).
