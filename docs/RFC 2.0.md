# RFC: Request for Comments — Projeto de Portfólio

**Engenharia de Software – Católica SC**

---
## ==O que está em amarelo precisa ser revisto==
# Identificação

- **Título do Projeto:** Sistema de Análise Contextual de Jurisprudência Trabalhista com IA
- **Linha de Projeto (Direction):** IA
- **Autor:** Vinicius Gabriel Zanatta
- **Data da Proposta:** _(a definir)_
- **Versão:** 1.0

---

# 1. Visão do Produto e Impacto (O Problema)

## 1.1 Contexto e Problema

Escritórios de advocacia trabalhista gerenciam centenas de processos simultâneos, cada um exigindo pesquisa de jurisprudência para embasar petições e manifestações dentro de prazos rígidos. Segundo relato de assistente jurídica com atuação em escritório de médio porte, o volume chega a 300 processos ativos, com foco em casos de insalubridade e periculosidade.

O problema central não é a ausência de ferramentas de busca — ferramentas como o Falcão e o Jusbrasil já existem — mas sim a incapacidade dessas ferramentas de compreender a **intenção argumentativa** do profissional. A busca retorna acórdãos sobre o tema, mas sem indicar se o posicionamento da decisão é favorável ou contrário à tese que o advogado precisa sustentar. O resultado é que aproximadamente 5 horas semanais são gastas em pesquisa, grande parte resultando em acórdãos fora de contexto ou inacessíveis por estarem em plataformas pagas.

Ferramentas de IA já disponíveis no mercado tentaram resolver esse problema, mas cometem alucinações — citando acórdãos inexistentes ou com teor distorcido — o que inviabiliza seu uso em contexto jurídico, onde a confiabilidade da fonte é inegociável.

**Como o problema é resolvido atualmente:**

- Busca manual por palavras-chave em ferramentas como Falcão e Jusbrasil
- Filtragem manual dos resultados pelo advogado
- Seleção da ementa e inserção na petição com breve explicação

**Limitações das soluções atuais:**

- Filtros genéricos sem alinhamento argumentativo
- Sem indicação de posicionamento favorável ou contrário à tese
- Acórdãos relevantes frequentemente atrás de paywall
- Quantidade de retorno massivo, resultando em horas de pesquisa
- Ferramentas de IA disponíveis cometem alucinações, citando acórdãos inexistentes

---

## 1.2 Origem da Demanda e Evidências

### Pesquisa com Usuário

Foi conduzida entrevista estruturada com **Alexia S. Rebello**, Assistente Jurídica com atuação em direito trabalhista, com foco em casos de insalubridade e periculosidade. Os principais achados foram:

| Dimensão               | Achado                                                          |
| ---------------------- | --------------------------------------------------------------- |
| Volume de trabalho     | ~300 processos ativos por escritório                            |
| Tempo em pesquisa      | ~5 horas semanais                                               |
| Ferramenta atual       | Falcão (busca por jurisprudência)                               |
| Principal limitação    | Filtragem genérica, sem alinhamento argumentativo               |
| Experiência com IA     | Resultados inexistentes ou alucinados                           |
| Sistema ideal descrito | Input de contexto + intenção argumentativa → acórdãos alinhados |
| Fator de abandono      | Falta de confiabilidade e alucinação                            |
|                        |                                                                 |

> _"Eu colocaria o contexto e a intenção argumentativa, assim poderiam ser localizados recursos para fortalecer a manifestação."_ — Alexia S. Rebello, Assistente Jurídica

---

## 1.3 Análise de Soluções Existentes (Benchmark)

| Solução                                   | Pontos Fortes                                                                                                           | Limitações                                       |
| ----------------------------------------- | ----------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------ |
| Falcão                                    | Filtragem mais simples, porem facilidade na pesquisa                                                                    | Filtros genéricos, sem alinhamento argumentativo |
| Sistema de pesquisa de Jurisprudência TST | Filtragem mais robusta                                                                                                  | Paywall, busca por palavras-chave                |
| Jus AI                                    | Contextualização do processo com inserção de documentos, além de outras funcionalidades fora pesquisa de jurisprudência | Alucinação em respostas                          |

**Diferencial do Projeto:** O sistema proposto é o único que recebe a **intenção argumentativa** como input — não apenas palavras-chave ou tema — e retorna acórdãos publicamente acessíveis do Falcão com indicação de alinhamento à tese do advogado, sem alucinações, pois todas as respostas são fundamentadas em fontes reais e citadas.

---

## 1.4 Público-Alvo

**Perfil principal:** Advogados e assistentes jurídicos atuantes em direito trabalhista, especialmente em casos de insalubridade, periculosidade, horas extras e rescisão.

**Contexto de uso:** Durante a elaboração de petições e manifestações, com necessidade de pesquisa rápida e precisa de jurisprudência alinhada à tese do caso.

**Nível técnico esperado:** Baixo — o usuário não precisa conhecer IA ou programação. A interface deve ser simples o suficiente para uso direto no fluxo de trabalho jurídico.

---

## 1.5 Objetivos do Projeto

### Objetivo Geral

Desenvolver um sistema de análise contextual de jurisprudência trabalhista que, a partir do upload de documentos do caso e da intenção argumentativa do advogado, extraia automaticamente o contexto jurídico relevante e recupere documentos jurídicos do Falcão — ==acórdãos, súmulas, orientações jurisprudenciais, precedentes normativos== (Sujeito a mudanças do que pode ser retornado) — ordenados pela hierarquia das fontes jurídicas e alinhados à tese, utilizando Query Enrichment, GraphRAG, busca híbrida e SAC Chunking — garantindo resultados precisos, contextualizados e sem alucinações.

### Objetivos Específicos

- Construir um pipeline de ingestão e processamento de **alguns tipos de documento jurídico do Falcão** — ==acórdãos, súmulas, orientações jurisprudenciais (OJs), precedentes normativos e decisões monocráticas== — coletados via scraping do portal oficial (jurisprudencia.tst.jus.br), com extração de entidades via NER (spaCy + LeNER-Br)
- Implementar modelo de dados que preserve o tipo de cada documento, permitindo diferenciação no pipeline de indexação, no GraphRAG e na apresentação dos resultados
- Implementar **ordenação categórica por hierarquia das fontes jurídicas** — baseada em doutrina consolidada do direito brasileiro — exibindo súmulas antes de OJs, OJs antes de acórdãos, acórdãos antes de decisões monocráticas, sem pesos numéricos arbitrários
- Implementar **Query Enrichment contextual**: o advogado sobe o PDF do caso, o sistema extrai automaticamente agente nocivo, tipo de violação, NRs citadas, setor e período — enriquecendo a query sem que o usuário precise digitar manualmente
- Implementar GraphRAG sobre os documentos indexados para capturar relações entre entidades como NRs, agentes nocivos e decisões, com arestas diferenciadas por tipo de documento
- Implementar busca híbrida (semântica + lexical via BM25 com Reciprocal Rank Fusion) para combinar precisão de termos jurídicos exatos com similaridade contextual
- Aplicar SAC Chunking para preservar o contexto global de cada documento durante a recuperação, eliminando confusão entre documentos estruturalmente similares
- Desenvolver interface funcional onde o advogado sobe o documento, complementa com intenção argumentativa em texto livre, e recebe resultados ordenados pela hierarquia jurídica com citação obrigatória da fonte original

---

## 1.6 Métricas de Sucesso (KPIs)

| Métrica                           | Categoria                           | Meta                         | Como medir                                                                        |
| --------------------------------- | ----------------------------------- | ---------------------------- | --------------------------------------------------------------------------------- |
| Tempo de resposta por consulta    | Desempenho                          | < 30s (meta: < 15s)          | Medição local do pipeline end-to-end                                              |
| Faithfulness                      | RAG — Zero alucinação               | ≥ 0.90                       | RAGAS: verifica se cada afirmação gerada está ancorada nos documentos recuperados |
| Answer Relevance                  | RAG — Alinhamento com a tese        | ≥ 0.80                       | RAGAS: mede alinhamento semântico entre resposta e query enriquecida              |
| Precision@5                       | IR — Qualidade da ordenação híbrida | ≥ 0.70                       | Dos 5 primeiros resultados, quantos são relevantes para a tese informada          |
| Precision@10                      | IR — Cobertura da busca             | ≥ 0.60                       | Dos 10 primeiros resultados, quantos são relevantes                               |
| Cobertura de documentos indexados | Dados                               | ==100% dos tipos do Falcão== | ==Acórdãos, súmulas, OJs, precedentes normativos e decisões monocráticas==        |
| Ordenação dos resultados          | Correção                            | 100%                         | Sempre respeitando a hierarquia das fontes jurídicas brasileiras                  |
| Documentos com fonte real citada  | Confiabilidade                      | 100%                         | Zero documentos gerados sem número, tipo e link verificável                       |

> **Ferramenta de avaliação:** [RAGAS](https://docs.ragas.io/) para Faithfulness e Answer Relevance. Precision@K avaliada com conjunto de queries.

---

# 2. Engenharia de Requisitos

## 2.1 Personas

> _(A ser preenchido — seção em desenvolvimento)_

---

## 2.2 Casos de Uso Principais

> _(A ser preenchido — seção em desenvolvimento)_

---

## 2.3 Requisitos Funcionais (RF)

- RF01 — O sistema deve permitir que o usuário faça upload de um PDF do caso como contexto principal da busca
    
- RF02 — O sistema deve extrair automaticamente do PDF as entidades jurídicas relevantes utilizando spaCy + LeNER-Br complementado por uma Ontologia Trabalhista específica do projeto, mapeando: NRs (ex: NR-15, NR-9), CBOs (ocupações profissionais), CIDs (doenças ocupacionais) e agentes químicos/físicos/biológicos — garantindo que as relações construídas no GraphRAG sejam precisas e sem ruído semântico
    
- RF03 — O sistema deve permitir que o usuário informe a intenção argumentativa em texto livre (ex: "quero provar insalubridade por benzeno sem EPI")
    
- RF04 — O sistema deve combinar extração automática do PDF com a intenção argumentativa para construir uma query enriquecida (Query Enrichment)
    
- RF05 — O sistema deve recuperar documentos jurídicos do Falcão de todos os tipos — acórdãos, súmulas, orientações jurisprudenciais, precedentes normativos e decisões monocráticas — semanticamente alinhados ao contexto e à tese informada
    
- RF06 — O sistema deve exibir a fonte real de cada documento retornado — número, tipo, data, relator e link — nunca gerando documento fictício
    
- RF07 — O sistema deve identificar visualmente o tipo de cada documento retornado, permitindo que o advogado compreenda de imediato seu peso jurídico
    
- RF08 — O sistema deve permitir que o usuário filtre os resultados por período além do retorno já em ordem de relevância semântica
    
- RF09 — O documento privado enviado pelo usuário deve ser processado exclusivamente em memória RAM durante a sessão e descartado ao encerramento, sem persistência em disco, banco de dados ou log
    

---

## 2.4 Requisitos Não Funcionais (RNF)

- RNF01 — O sistema não deve gerar acórdãos fictícios — toda resposta deve ser fundamentada em fonte indexada real
- RNF02 — O tempo de resposta por consulta deve ser inferior a 30 segundos, com meta de 15 segundos em condições normais — SLA compatível com pipeline local rodando LLM, embeddings e GraphRAG em hardware consumer
- RNF03 — O sistema deve garantir confidencialidade jurídica dos documentos privados enviados pelo usuário por meio de processamento 100% local: todos os componentes de IA (LLM, embeddings, NER) rodam via Ollama no hardware do operador, sem envio de dados para APIs externas.
- RNF04 — A interface deve ser acessível a usuários sem conhecimento técnico
- RNF05 — O sistema deve suportar documentos de entrada de qualquer tamanho no Query Enrichment por meio de sumarização hierárquica prévia: documentos que ultrapassem o limite de contexto do LLM (ex: petições longas) são divididos em blocos, sumarizados individualmente e depois condensados numa tese única antes do cruzamento com a base extraída do Falcão
- RNF06 — O sistema deve ordenar os resultados pela hierarquia das fontes jurídicas brasileiras: súmulas → orientações jurisprudenciais → precedentes normativos → acórdãos → decisões monocráticas

---

## 2.5 Regras de Negócio

- RN01 — O sistema opera exclusivamente sobre documentos públicos do TST — acórdãos, súmulas, OJs, precedentes normativos e decisões monocráticas — coletados via scraping do portal oficial; nenhuma fonte privada ou paga é utilizada.
- RN02 — A ordenação dos resultados segue a hierarquia das fontes jurídicas brasileiras, conforme doutrina consolidada: súmulas têm precedência sobre OJs, OJs sobre acórdãos, acórdãos sobre decisões monocráticas — sem pesos numéricos arbitrários
- RN03 — Nenhum documento privado enviado pelo usuário é armazenado ou indexado permanentemente
- RN04 — Toda resposta gerada pelo LLM deve obrigatoriamente citar o documento de origem com número, tipo e **link verificável** ==(IMPORTANTE LEMBRAR DE ANEXAR NA HORA DO SCRAPING)==

---

## 2.6 Fora do Escopo

- Acórdãos de Tribunais Regionais do Trabalho (TRTs) — previsto como melhoria futura (abaixo)
- Acórdãos de outras esferas não trabalhistas (STF, STJ) — fora do escopo
- Outras áreas do direito além do trabalhista — fora do escopo

**Melhoria Futura Planejada — Expansão para TRTs Regionais:** A Justiça do Trabalho é organizada em três instâncias: Varas do Trabalho (1ª instância), Tribunais Regionais do Trabalho — TRTs (2ª instância) e TST (3ª instância e uniformizador nacional). O sistema na versão inicial opera sobre acórdãos do TST, que têm maior peso como precedente nacional. Como evolução natural, está prevista a incorporação de acórdãos do **TRT da 12ª Região (SC)**, tornando o sistema mais relevante para advogados que atuam em Santa Catarina, onde decisões regionais têm aplicação direta nos casos de 1ª instância.

- Recomendação automática de estratégia jurídica ou substituição da análise do advogado
- Armazenamento ou processamento de documentos privados de processos reais
- Integração direta com sistemas de peticionamento (PJe, e-SAJ)

---

# 3. Fluxos e Comportamento do Sistema

## 3.1 Fluxo Principal do Usuário

1. Advogado acessa o sistema e faz upload do PDF do caso (petição, laudo, notificação ou outro documento)
2. Sistema extrai o texto via pdfplumber e aplica NER para identificar: agente nocivo, tipo de violação, NRs citadas, setor profissional, período e partes envolvidas
3. Sistema exibe as entidades extraídas para revisão — o advogado pode corrigir ou complementar o que foi identificado automaticamente
4. Advogado informa a intenção argumentativa em texto livre (ex: "quero provar que a empresa tinha conhecimento da exposição e não forneceu EPI adequado")
5. Sistema constrói a query enriquecida combinando contexto extraído do PDF + intenção argumentativa (**Query Enrichment**)
6. Pipeline RAG híbrido + GraphRAG processa a query enriquecida sobre os acórdãos indexados do TST
7. Sistema retorna lista de acórdãos relevantes com posicionamento, resumo do argumento central e citação completa da fonte
8. Advogado seleciona os acórdãos para uso na petição
9. Documento privado é descartado da memória — nenhum dado privado é persistido

---

## 3.2 Fluxos Alternativos

> _(A ser preenchido — seção em desenvolvimento)_

---

# 4. Mockups e Experiência do Usuário (UX)

> _(A ser preenchido — seção em desenvolvimento)_

---

# 5. Arquitetura do Sistema

## 5.1 Diagrama C4

> _(A ser preenchido com diagramas — seção em desenvolvimento)_

---

## 5.2 Modelo de Dados

> _(A ser preenchido — seção em desenvolvimento)_

---

## 5.3 Principais Componentes

**Pipeline de IA completo **

| Etapa               | Componente                                   | Responsabilidade                                                                                                                                      |
| ------------------- | -------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Ingestão         | Scraper TST                                  | Coleta de todos os tipos de documento via scraping (Scrapy + Playright) com suporte a delta — apenas documentos novos                                 |
| 2. Extração         | pdfplumber                                   | Extração de texto por seção: ementa, relatório, votos, dispositivo                                                                                    |
| 3. Chunking         | SAC Chunker                                  | Gera resumo global (80-120 tokens) por documento via LLM local (Ollama, Qwen...); divide em chunks de 600-800 tokens; prepend do resumo em cada chunk |
| 4. NER              | spaCy + LeNER-Br                             | Extração offline de entidades: agente_nocivo, NR, tipo_violacao, setor → vira metadados estruturados                                                  |
| 5. Embeddings       | Poly-Vector (nomic-embed-text-v2 via Ollama) | Gera 2 embeddings por chunk: embedding completo (chunk + SAC summary) e embedding da ementa/tese isolada                                              |
| 6. Indexação        | ChromaDB + LightRAG                          | ChromaDB armazena vetores com metadados; LightRAG constrói grafo leve (nós = entidades NER + chunks; arestas = cita, aplica, revoga, tipo_documento)  |
| 7. Query Enrichment | LLM local (Llama 3.2 3B)                     | Advogado sobe PDF + escreve intenção; LLM extrai fatos, gera tese formal e keywords                                                                   |
| 8. Busca Híbrida    | ChromaDB + BM25 + LightRAG + RRF             | Vector search (cosine) + BM25 lexical + 1-hop no grafo; Reciprocal Rank Fusion combina os três; retorna top-20                                        |
| 9. Ordenação        | Sort categórico                              | Ordena por hierarquia das fontes jurídicas: súmulas → OJs → precedentes normativos → acórdãos → decisões monocráticas                                 |
| 10. Interface       | React + Vite                                 | Upload de PDF + input argumentativo + resultados em acordão com citação, link oficial e trecho relevante                                              |

---

## 5.4 Decisões Arquiteturais — Por que o sistema é construído dessa forma

Esta seção documenta as decisões técnicas centrais do projeto, explicando o raciocínio por trás de cada escolha arquitetural.

---

### Decisão 1 — Por que RAG e não um LLM puro?

LLMs como GPT-4 ou Llama cometem **alucinações** — geram acórdãos com números de processo, datas e ementas completamente inventados, mas com aparência convincente. No domínio jurídico, citar uma fonte fictícia é um erro grave que pode comprometer uma petição e a credibilidade do advogado.

RAG (Retrieval-Augmented Generation) resolve isso fundamentalmente: o LLM só pode falar sobre acórdãos que existem na base indexada. A geração é ancorada em documentos reais. Todo resultado citado tem número de processo, data e relator verificáveis.

---

### Decisão 2 — Por que GraphRAG e não RAG vetorial simples?

RAG vetorial tradicional trata cada acórdão como um documento isolado. No domínio jurídico trabalhista, acórdãos formam uma rede de relações: uma decisão sobre NR-15 cita outra sobre benzeno, que referencia a mesma NR, que se conecta a um conjunto de casos com o mesmo agente nocivo. RAG vetorial não captura essas conexões.

GraphRAG constrói um grafo de conhecimento onde entidades (NRs, agentes nocivos, tipos de violação, leis) são nós e suas relações são arestas. Quando o advogado busca um caso sobre insalubridade por benzeno sem EPI, o sistema não apenas encontra acórdãos com benzeno — ele navega o grafo para trazer acórdãos conectados: sobre NR-15, sobre obrigação de fornecimento de EPI, sobre ciência do empregador. O resultado é qualitativamente superior.

---

### Decisão 3 — Por que Busca Híbrida (BM25 + Embeddings)?

Embeddings capturam significado semântico mas podem falhar em termos técnicos exatos. "NR-15", "CLT art. 193", "LTCAT" e "benzeno" são strings que precisam ser encontradas exatamente — um embedding pode aproximar "NR15" de "norma quinze" semanticamente, mas perder um acórdão que usa exatamente "NR-15".

BM25 garante precisão lexical — encontra o termo exato. Embeddings garantem compreensão semântica — encontram o contexto similar. Reciprocal Rank Fusion mescla os dois rankings, priorizando documentos que aparecem bem em ambas as buscas. Para um domínio com terminologia técnica precisa como o jurídico trabalhista, essa combinação é superior a qualquer abordagem isolada.

---

### Decisão 4 — Por que SAC Chunking?

Acórdãos trabalhistas sobre o mesmo tema (ex: insalubridade por benzeno) são estruturalmente muito similares entre si — mesma estrutura de ementa, mesmo vocabulário, mesmas referências normativas. RAG com chunking tradicional frequentemente recupera o chunk certo mas do acórdão errado, porque os chunks isolados parecem idênticos.

SAC (Summary-Augmented Chunking) resolve isso adicionando o resumo global do acórdão (ementa) como contexto de cada chunk. Assim o sistema sabe não apenas o que o trecho diz, mas de qual decisão específica ele veio. A ementa dos acórdãos do TST é naturalmente o identificador semântico único de cada decisão — o SAC aproveita essa estrutura existente.

---

### Decisão 5 — Por que Query Enrichment com upload de PDF?

A principal dor relatada pela especialista do domínio foi que ferramentas atuais retornam acórdãos sobre o tema, mas não sobre a situação específica do caso. Um advogado que busca "insalubridade benzeno" recebe milhares de resultados — mas seu caso é específico: trabalhador metalúrgico, exposição entre 2018 e 2022, empresa contesta com laudo próprio, sem EPI documentado.

Query Enrichment resolve isso extraindo automaticamente o contexto específico do documento do caso com NER, combinando com a intenção argumentativa digitada pelo advogado, e construindo uma query muito mais rica e precisa. O resultado é busca pelo caso específico, não pelo tema genérico — exatamente o que a especialista descreveu como sistema ideal.

O documento privado é processado exclusivamente em memória e descartado ao fim da sessão, garantindo conformidade com a LGPD.

---

### Decisão 6 — Por que LightRAG e não Microsoft GraphRAG ou Neo4j?

O Microsoft GraphRAG requer infraestrutura pesada (Azure, custos elevados de API) e foi projetado para escala corporativa — inviável para portfólio acadêmico. Neo4j é robusto mas adiciona complexidade de infraestrutura (servidor dedicado, linguagem Cypher) desnecessária para o escopo do projeto.

LightRAG (HKUDS, 2024) integra nativamente grafo de conhecimento com recuperação vetorial em uma biblioteca Python simples, sem servidor externo. Suporta os mesmos padrões de GraphRAG com uma API significativamente mais acessível. Para o escopo de portfólio, é a escolha que maximiza resultado técnico minimizando complexidade operacional.

---

### Decisão 8 — Por que indexar todos os tipos de documento e não apenas acórdãos

O portal do TST disponibiliza sete tipos de documento: acórdãos, decisões monocráticas, súmulas, precedentes normativos, orientações jurisprudenciais, decisões da presidência e da vice-presidência. Sistemas atuais como o Falcão e a busca do próprio TST retornam todos esses tipos misturados sem distinção de relevância argumentativa.

O sistema proposto indexa todos os tipos mas os trata de forma diferenciada no pipeline e na apresentação. Isso é relevante porque uma súmula sobre insalubridade vale argumentativamente mais do que dezenas de acórdãos sobre o mesmo tema — ela representa o entendimento consolidado do tribunal, seguido por todos os juízes. Ignorar essa distinção é uma das limitações das ferramentas atuais relatada pela especialista do domínio.

---

### Decisão 9 — Por que ordenação categórica e não pesos numéricos

A alternativa de atribuir pesos numéricos como súmula=5, acórdão=2 foi considerada e descartada por ser arbitrária — não há fundamentação científica ou jurídica para afirmar que súmula vale exatamente 2,5 vezes mais que um acórdão.

A ordenação categórica é defensável porque a hierarquia das fontes jurídicas — súmulas acima de OJs, OJs acima de acórdãos, acórdãos acima de decisões monocráticas — é doutrina consolidada no direito processual do trabalho brasileiro, não uma decisão do sistema. O sistema apenas implementa o que a doutrina já estabelece. Dentro de cada categoria, os documentos são ordenados por similaridade semântica com a query do advogado — essa sim é uma métrica objetiva e mensurável.

---

### Decisão 7 — Por que LLM local (Ollama + Llama 3.2 3B) e não API externa

APIs externas como Groq ou OpenAI introduzem custo operacional, dependência de conectividade e envio de dados potencialmente sensíveis para servidores externos. Para um sistema jurídico onde o advogado pode subir documentos do caso, isso é indesejável mesmo que o documento seja descartado após a sessão.

Ollama permite rodar modelos localmente sem custo, inclusive em CPU para modelos leves como Llama 3.2 3B. Para as tarefas do sistema — geração de resumos SAC (80-120 tokens) e extração de tese no Query Enrichment — o Llama 3.2 3B é suficiente. Isso mantém todo o pipeline offline, com custo R$ 0 e sem envio de dados para terceiros.

---

### Decisão 10 — Por que Poly-Vector Embeddings (2 vetores por chunk)

Embeddings únicos por chunk capturam ou o contexto argumentativo detalhado ou a tese jurídica consolidada — raramente os dois com igual precisão. Súmulas e OJs têm texto curto mas juridicamente denso: um embedding único tende a capturar a forma mas perder a profundidade da tese.

Poly-Vector Indexing resolve isso gerando dois embeddings por chunk com o modelo nomic-embed-text-v2: um do chunk completo com SAC summary (contexto argumentativo rico) e um da ementa/tese isolada (precisão jurídica). Durante a busca, ambos os vetores são consultados independentemente e os resultados fundidos via RRF. O resultado é recuperação que é simultaneamente precisa na tese jurídica e rica no contexto argumentativo — especialmente relevante para documentos curtos como súmulas e OJs.

---

### Decisão 11 — Por que uma Ontologia Trabalhista própria além do LeNER-Br

O LeNER-Br reconhece entidades jurídicas genéricas em português — legislação, organizações, pessoas, tempo, local. Para o domínio trabalhista específico, isso é insuficiente: o modelo não distingue "NR-15" de "NR-9", não reconhece CBOs (Classificação Brasileira de Ocupações) como entidade estruturada, não mapeia CIDs de doenças ocupacionais e não conhece a taxonomia de agentes nocivos da legislação de insalubridade.

Sem essa distinção, o GraphRAG construiria arestas ruidosas — conectando "ruído" (agente físico) com "ruído" (ruído como metáfora jurídica), por exemplo. A Ontologia Trabalhista é uma lista estruturada de entidades específicas do domínio que complementa o LeNER-Br como dicionário de termos precisos, garantindo que as relações do grafo reflitam a semântica jurídica real e não coincidências lexicais.

---

### Decisão 12 — Estratégia de Janela de Contexto para documentos longos

Petições iniciais e laudos periciais podem ter 30, 50 ou mais páginas. O Llama 3.2 3B tem janela de contexto limitada — jogar o documento inteiro no prompt geraria truncamento silencioso, perdendo partes relevantes do caso sem aviso.

A estratégia adotada é **sumarização hierárquica prévia**: o documento é dividido em blocos de tamanho controlado, cada bloco é sumarizado individualmente pelo LLM local, e os resumos são depois condensados numa tese única. Só essa tese final entra no Query Enrichment para cruzamento com a base do TST. Isso garante que nenhuma informação relevante seja perdida por truncamento, mesmo em documentos muito extensos, e mantém o custo computacional previsível independentemente do tamanho do documento original.

---

## 5.5 Stack Tecnológica

**Todo o pipeline roda localmente — custo operacional R$ 0.**

|Tecnologia|Função|Justificativa|
|---|---|---|
|requests + BeautifulSoup|Scraping do portal TST|Coleta simples e controlada com suporte a delta|
|pdfplumber|Extração de texto de PDFs|Preserva estrutura de seções em documentos jurídicos pt-BR|
|Ollama|Runtime local para LLMs|Permite rodar modelos localmente sem custo de API, até em CPU|
|Llama 3.2 3B (via Ollama)|SAC Chunking + Query Enrichment|Modelo leve suficiente para geração de resumos e extração de tese|
|spaCy + LeNER-Br|NER jurídico offline|Único modelo treinado especificamente em textos jurídicos brasileiros|
|nomic-embed-text-v2 (via Ollama)|Poly-Vector Embeddings|Modelo de embeddings 2026 com ótimo desempenho em português jurídico, roda local|
|ChromaDB|Banco de vetores local|Persistente em disco, sem servidor externo, integração nativa com LightRAG|
|LightRAG|GraphRAG leve|Constrói grafo automaticamente sobre ChromaDB; dual-level retrieval (vector + 1-hop graph)|
|BM25 (rank_bm25)|Busca lexical|Precisão em termos jurídicos exatos: NR-15, CLT art. 193, LTCAT|
|Reciprocal Rank Fusion|Combinação de rankings|Funde vector search + BM25 + graph retrieval de forma objetiva e sem hiperparâmetros arbitrários|
|Streamlit|Interface|Prototipagem rápida em Python, deploy público via Streamlit Cloud|

---

### Nota sobre Poly-Vector Embeddings

A escolha de gerar **2 embeddings por chunk** — um completo (chunk + SAC summary) e um da ementa/tese isolada — é uma decisão deliberada chamada Poly-Vector Indexing. O embedding completo captura o contexto argumentativo detalhado do voto. O embedding da ementa captura a tese jurídica consolidada. Durante a busca, ambos os vetores são consultados e os resultados são fundidos via RRF, resultando em recuperação que é simultaneamente precisa na tese e rica no contexto. Isso é especialmente relevante para súmulas e OJs, cujo texto é curto mas juridicamente denso.

---

# 6. Segurança e Privacidade

## 6.1 Privacidade e LGPD

**Dados coletados:** Apenas o texto da consulta digitada pelo usuário no momento da busca.

**Dados não coletados:** Nenhum documento privado de processo é armazenado. O sistema opera exclusivamente sobre acórdãos públicos do TST.

**Base legal:** O sistema opera sobre dados públicos e não armazena dados pessoais, estando fora do escopo de tratamento de dados sensíveis pela LGPD.

**Princípio aplicado:** Minimização de dados — coleta apenas o necessário para responder à consulta, sem persistência.

---

# 7. Planejamento do Projeto

> _(A ser detalhado — seção em desenvolvimento)_

|Marco|Descrição|Prazo|
|---|---|---|
|M1|Setup do ambiente + pipeline de ingestão dos acórdãos|A definir|
|M2|NER + construção do grafo de conhecimento|A definir|
|M3|Busca híbrida + SAC Chunking funcionando|A definir|
|M4|Integração LLM + interface Streamlit|A definir|
|M5|Validação com especialista + ajustes finais|A definir|

---

# 8. Referências

- **Acórdãos TST** — Fonte principal de dados do sistema. Coletados via scraping público do portal de jurisprudência do TST: https://jurisprudencia.tst.jus.br
- **Iudicium Textum Dataset (ITD)** — UFPR. Base acadêmica de referência para NLP jurídico em português, utilizada como inspiração metodológica para estruturação do pipeline de ingestão. Contém 41.353 acórdãos do STF (2010–2018). Referência: SOUSA, A. W.; DEL FABRO, M. D. Iudicium Textum Dataset: Uma Base de Textos Jurídicos para NLP. In: 34º SBBD. SBC, 2019. Acesso: https://dadosabertos.c3sl.ufpr.br/acordaos
- **LeNER-Br** — NER jurídico em português: https://github.com/peluz/lener-br
- **Microsoft GraphRAG**: https://github.com/microsoft/graphrag
- **LightRAG**: https://github.com/HKUDS/LightRAG
- **SAC — Summary-Augmented Chunking** _(paper 2025 — a inserir referência completa)_
- **rufimelo/bert-large-portuguese-cased-sts** — HuggingFace: https://huggingface.co/rufimelo/bert-large-portuguese-cased-sts
- **spaCy pt**: https://spacy.io/models/pt
- **LangChain**: https://python.langchain.com
- **ChromaDB**: https://www.trychroma.com

---

# 9. Apêndices

> _(A ser preenchido — entrevista completa com Alexia S. Rebello, diagramas complementares)_

---

# 10. Parecer do Comitê de Avaliação

_(A ser preenchido pelos professores)_

**Avaliador 1:** __________________________ **Status:** [ ] Aprovado [ ] Ajustar

Observações:

---

**Avaliador 2:** __________________________ **Status:** [ ] Aprovado [ ] Ajustar

Observações:

---

**Avaliador 3:** __________________________ **Status:** [ ] Aprovado [ ] Ajustar

Observações: