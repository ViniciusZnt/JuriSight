import time
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ========== CONFIGURAÇÕES ==========
URL_BASE = "https://jurisprudencia.jt.jus.br/jurisprudencia-nacional-backend/api/no-auth/pesquisa"

# Parâmetros atuais (substitua pelos valores válidos)
PARAMS = {
    "sessionId": "_nivtmjh",
    "latitude": "0",
    "longitude": "0",
    "juristkn": "9d4b8a21131385",
    "texto": "",
    "verTodosPrecedentes": "false",
    "tribunais": "",
    "pesquisaSomenteNasEmentas": "false",
    "filtroRapidoData": "IntervaloSelecionado",
    "dataInicio": "2024-01-01",
    "dataFim": "2024-01-31",
    "colecao": "acordaos",
    "page": "1",
    "size": "10"
}

COOKIES = {
    "JSESSIONID": "BdiH33ibZNAsxDVdySAeEK54duJq-LrXrmGFZcPn",
    "SESSION_ID_COOKIE_PUJ": "_nivtmjh"
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://jurisprudencia.jt.jus.br/jurisprudencia-nacional/pesquisa",
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.8",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
}

# Configurações do teste
CONCURRENT_REQUESTS = 5      # Número de requisições simultâneas
TOTAL_REQUESTS = 50          # Total de requisições a serem feitas
DELAY_BETWEEN_REQUESTS = 1 # Delay entre cada requisição (em segundos)

def test_api(concurrency, total_requests, delay):
    # Cria uma sessão e configura os cookies/headers uma única vez
    session = requests.Session()
    session.cookies.update(COOKIES)
    session.headers.update(HEADERS)

    # Função que será executada em paralelo
    def make_request(i):
        start = time.time()
        try:
            # Usa a sessão (já tem cookies e headers)
            resp = session.get(URL_BASE, params=PARAMS, timeout=10)
            elapsed = time.time() - start
            rate_remaining = resp.headers.get("x-rate-limit-remaining")
            return i, resp.status_code, elapsed, rate_remaining, None
        except Exception as e:
            elapsed = time.time() - start
            return i, None, elapsed, None, str(e)

    results = []
    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        # Submete todas as tarefas
        futures = [executor.submit(make_request, i) for i in range(total_requests)]
        # Aguarda os resultados e aplica delay entre cada conclusão
        for future in as_completed(futures):
            i, status, elapsed, rate_remaining, error = future.result()
            results.append((i, status, elapsed, rate_remaining, error))
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Req {i+1:3d} | status: {status} | tempo: {elapsed:.2f}s | restante: {rate_remaining}")
            if delay > 0:
                time.sleep(delay)

    # Estatísticas
    success = [r for r in results if r[1] == 200]
    errors = [r for r in results if r[1] != 200]
    avg_time = sum(r[2] for r in success) / len(success) if success else 0

    print("\n--- Estatísticas ---")
    print(f"Total: {total_requests}")
    print(f"Sucessos: {len(success)}")
    print(f"Falhas: {len(errors)}")
    print(f"Tempo médio de resposta (sucessos): {avg_time:.2f}s")
    if errors:
        status_set = set(r[1] for r in errors if r[1] is not None)
        print("Códigos de erro:", status_set)
        exc_set = set(r[4] for r in errors if r[4])
        if exc_set:
            print("Exceções:", exc_set)

if __name__ == "__main__":
    test_api(CONCURRENT_REQUESTS, TOTAL_REQUESTS, DELAY_BETWEEN_REQUESTS)