#!/bin/bash
# Executa delta scraping — apenas documentos novos desde a última coleta

set -e

echo "🔄 Iniciando delta scraping..."
scrapy crawl tst_delta -s JOBDIR=.scrapy/jobs/delta
echo "✅ Delta scraping finalizado."
