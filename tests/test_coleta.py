import json
import os
import tempfile
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from scraper.spiders.falcao_acordaos import FalcaoSpider

def run_test():
    # Cria um arquivo tasks.json temporário com uma task pequena
    tasks_data = [
        {"id": 1, "data_inicio": "2024-01-01", "data_fim": "2024-01-31"}
    ]
    # Usamos um arquivo fixo no diretório atual para facilitar
    tasks_file = "tasks_test.json"
    with open(tasks_file, 'w', encoding='utf-8') as f:
        json.dump(tasks_data, f, indent=2)
    print(f"Arquivo de tasks criado: {tasks_file}")

    # Configura o spider para usar esse arquivo
    # Modificamos o atributo de classe antes da instância
    FalcaoSpider.TASKS_FILE = tasks_file

    # Configurações do Scrapy
    settings = get_project_settings()
    # Ajusta para teste: baixar apenas algumas páginas (opcional, mas pode limitar o tamanho)
    settings.set('CONCURRENT_REQUESTS', 1)
    settings.set('DOWNLOAD_DELAY', 2)
    settings.set('LOG_LEVEL', 'INFO')
    # FEEDS para salvar os itens extraídos
    settings.set('FEEDS', {
        'output.jsonl': {
            'format': 'jsonlines',
            'encoding': 'utf-8',
        }
    })

    process = CrawlerProcess(settings)
    process.crawl(FalcaoSpider)
    process.start()

    print("\nTeste concluído. Resultados salvos em output.jsonl")
    # Opcional: exibir as primeiras linhas do arquivo
    if os.path.exists('output.jsonl'):
        print("Primeiras linhas do arquivo de saída:")
        with open('output.jsonl', 'r', encoding='utf-8') as f:
            for i, line in enumerate(f):
                if i < 5:
                    print(line.strip())
                else:
                    break
    else:
        print("Arquivo de saída não foi gerado.")

if __name__ == "__main__":
    run_test()