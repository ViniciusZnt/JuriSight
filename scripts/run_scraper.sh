#!/bin/bash
# Executa scraping completo de todos os tipos de documento do TST

set -e

echo "🕷️  Iniciando scraping completo do TST..."

echo "📄 Coletando acórdãos..."
scrapy crawl tst_acordaos -s JOBDIR=.scrapy/jobs/acordaos

echo "📋 Coletando súmulas..."
scrapy crawl tst_sumulas -s JOBDIR=.scrapy/jobs/sumulas

echo "📌 Coletando Orientações Jurisprudenciais..."
scrapy crawl tst_ojs -s JOBDIR=.scrapy/jobs/ojs

echo "✅ Scraping completo finalizado."
echo "   Documentos salvos em: data/raw/ e data/processed/"
