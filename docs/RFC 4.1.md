# RFC: Request for Comments — Projeto de Portfólio

**Engenharia de Software – Católica SC**

---

# Identificação

- **Título do Projeto:** Sistema de Análise Contextual de Jurisprudência Trabalhista com IA
    
- **Linha de Projeto (Direction):** IA
    
- **Autor:** Vinicius Gabriel Zanatta
    
- **Data da Proposta:** _(a definir)_
    
- **Versão:** 4.1
    

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

|Dimensão|Achado|
|---|---|
|Volume de trabalho|~300 processos ativos por escritório|
|Tempo em pesquisa|~5 horas semanais|
|Ferramenta atual|Falcão (busca por jurisprudência)|
|Principal limitação|Filtragem genérica, sem alinhamento argumentativo|
|Experiência com IA|Resultados inexistentes ou alucinados|
|Sistema ideal descrito|Input de contexto + intenção argumentativa → acórdãos alinhados|
|Fator de abandono|Falta de confiabilidade e alucinação|

> _"Eu colocaria o contexto e a intenção argumentativa, assim poderiam ser localizados recursos para fortalecer a manifestação."_ — Alexia S. Rebello, Assistente Jurídica

---

## 1.3 Análise de Soluções Existentes (Benchmark)

|Solução|Pontos Fortes|Limitações|
|---|---|---|
|Falcão|Filtragem mais simples, porém facilidade na pesquisa|Filtros genéricos, sem alinhamento argumentativo|
|Sistema de pesquisa de Jurisprudência TST|Filtragem mais robusta|Paywall, busca por palavras-chave|
|Jus AI|Contextualização do processo com inserção de documentos, além de outras funcionalidades fora pesquisa de jurisprudência|Alucinação em respostas|

**Diferencial do Projeto:** O sistema proposto é o único que recebe a **intenção argumentativa** como input — não apenas palavras-chave ou tema — e retorna acórdãos publicamente acessíveis do Falcão com indicação de alinhamento à tese do advogado, sem alucinações, pois todas as respostas são fundamentadas em fontes reais e citadas.

---

## 1.4 Público-Alvo

**Perfil principal:** Advogados e assistentes jurídicos atuantes em direito trabalhista, especialmente em casos de insalubridade, periculosidade, horas extras e rescisão.

**Contexto de uso:** Durante a elaboração de petições e manifestações, com necessidade de pesquisa rápida e precisa de jurisprudência alinhada à tese do caso.

**Nível técnico esperado:** Baixo — o usuário não precisa conhecer IA ou programação. A interface deve ser simples o suficiente para uso direto no fluxo de trabalho jurídico.

---

## 1.5 Objetivos do Projeto

### Objetivo Geral

Desenvolver um sistema de análise contextual de jurisprudência trabalhista que, a partir do upload de documentos do caso e da intenção argumentativa do advogado, extraia automaticamente o contexto jurídico relevante e recupere documentos jurídicos do Falcão — acórdãos, súmulas, orientações jurisprudenciais, precedentes normativos — ordenados pela hierarquia das fontes jurídicas e alinhados à tese, utilizando Query Enrichment, busca híbrida e SAC Chunking — garantindo resultados precisos, contextualizados e sem alucinações.

### Objetivos Específicos

- Construir um pipeline de ingestão e processamento de **alguns tipos de documento jurídico do Falcão** — acórdãos, súmulas, orientações jurisprudenciais (OJs), precedentes normativos e decisões monocráticas — coletados via scraping do portal oficial ([jurisprudencia.tst.jus.br](https://jurisprudencia.tst.jus.br/))
    
- Implementar modelo de dados que preserve o tipo de cada documento e o **provimento da decisão** (Aprovado/Negado), permitindo filtragem por alinhamento à tese do advogado
    
- Implementar **ordenação categórica por hierarquia das fontes jurídicas** — baseada em doutrina consolidada do direito brasileiro — exibindo súmulas antes de OJs, OJs antes de acórdãos, acórdãos antes de decisões monocráticas, sem pesos numéricos arbitrários
    
- Implementar **Query Enrichment contextual** baseado em **estrutura argumentativa jurídica**: o advogado sobe o PDF do caso, o sistema extrai automaticamente via LLM um conjunto fixo de campos semanticamente relevantes – ==`pedido_principal`, `agente_nocivo`, `violacoes`, `normas`, `empresa_ciente`, `setor`, `cargo`, `tese_central`== – que serão usados para construir uma query rica para BM25 (concatenação textual) e uma frase central para embeddings semânticos, sem necessidade de digitação manual extensa.
    
- Implementar busca híbrida (semântica + lexical via BM25 com Reciprocal Rank Fusion) para combinar precisão de termos jurídicos exatos com similaridade contextual
    
- Aplicar SAC Chunking para preservar o contexto global de cada documento durante a recuperação, eliminando confusão entre documentos estruturalmente similares
    
- Desenvolver interface web (Next.js) onde o advogado sobe o documento, complementa com intenção argumentativa em texto livre, e recebe resultados ordenados pela hierarquia jurídica com citação obrigatória da fonte original
    

---

## 1.6 Métricas de Sucesso (KPIs)

| Métrica                           | Categoria                           | Meta                     | Como medir                                                                                                                  |
| --------------------------------- | ----------------------------------- | ------------------------ | --------------------------------------------------------------------------------------------------------------------------- |
| Tempo de resposta por consulta    | Desempenho                          | < 30s (meta: < 15s)      | Medição local do pipeline end-to-end                                                                                        |
| Faithfulness                      | RAG — Zero alucinação               | ≥ 0.90                   | RAGAS: verifica se cada afirmação gerada está ancorada nos documentos recuperados                                           |
| Answer Relevance                  | RAG — Alinhamento com a tese        | ≥ 0.80                   | RAGAS: mede alinhamento semântico entre resposta e query enriquecida                                                        |
| Precision@5                       | IR — Qualidade da ordenação híbrida | ≥ 0.70                   | Dos 5 primeiros resultados, quantos são relevantes para a tese informada                                                    |
| Precision@10                      | IR — Cobertura da busca             | ≥ 0.60                   | Dos 10 primeiros resultados, quantos são relevantes                                                                         |
| Cobertura de documentos indexados | Dados                               | 100% dos tipos do Falcão | Acórdãos, súmulas, OJs, precedentes normativos e decisões monocráticas                                                      |
| Ordenação dos resultados          | Correção                            | 100%                     | Sempre respeitando a hierarquia das fontes jurídicas brasileiras                                                            |
| Documentos com fonte real citada  | Confiabilidade                      | 100%                     | Zero documentos gerados sem número, tipo e link verificável                                                                 |
| **Filtro por provimento**         | **Alinhamento argumentativo**       | **≥ 0.90**               | **Quando o advogado pedir apenas decisões favoráveis, o sistema deve retornar ≥ 90% de acórdãos com provimento "Aprovado"** |

> **Ferramenta de avaliação:** [RAGAS](https://docs.ragas.io/) para Faithfulness e Answer Relevance. Precision@K avaliada com conjunto de queries.

---

# 2. Engenharia de Requisitos

## 2.1 Personas

### Persona 1 — Assistente Jurídica Pesquisadora

| Atributo                       | Descrição                                                                                                         |
| ------------------------------ | ----------------------------------------------------------------------------------------------------------------- |
| **Nome fictício**              | Ana Paula                                                                                                         |
| **Papel**                      | Assistente Jurídica                                                                                               |
| **Contexto**                   | Atua em escritório de médio porte com ~300 processos ativos, maioria em insalubridade e periculosidade            |
| **Responsabilidade principal** | Pesquisa de jurisprudência para embasar petições e manifestações                                                  |
| **Ferramentas atuais**         | Falcão, Jusbrasil, Google                                                                                         |
| **Dor principal**              | Gasta ~5h semanais em pesquisa; retorno massivo e genérico; não sabe se o acórdão é favorável ou contrário à tese |
| **Relação com IA**             | Tentou usar ferramentas de IA, mas abandonou por causa de alucinações — acórdãos citados que não existem          |
| **Objetivo no sistema**        | Informar o contexto do caso + intenção argumentativa e receber acórdãos reais, já filtrados por posicionamento    |
| **Critério de sucesso**        | Encontrar em menos de 5 minutos pelo menos 3 acórdãos favoráveis à tese, com fonte verificável                    |

> _"Preciso de acórdãos que me ajudem a sustentar a tese, não de uma lista de tudo que existe sobre o assunto."_

---

### Persona 2 — Advogado Trabalhista

| Atributo | Descrição |
|---|---|
| **Nome fictício** | Dr. Marcelo |
| **Papel** | Advogado titular |
| **Contexto** | Subscreve e revisa as petições, delega a pesquisa de jurisprudência para a assistente |
| **Responsabilidade principal** | Definir a estratégia jurídica e assinar as peças processuais |
| **Dor principal** | Depende da qualidade da pesquisa da equipe; uma citação errada ou fictícia compromete a petição e a credibilidade do escritório |
| **Relação com IA** | Cético em relação a IA por conta das alucinações já vivenciadas indiretamente |
| **Objetivo no sistema** | Ter confiança de que os acórdãos entregues pela assistente são reais, verificáveis e alinhados à tese |
| **Critério de sucesso** | Todo resultado exibido deve ter número de processo, data, relator e link clicável para o portal do TST |

> _"Se o sistema me entregar um acórdão que não existe, a petição vai devolver e a credibilidade do escritório vai junto."_

---

## 2.2 Casos de Uso Principais

### Diagrama de Casos de Uso

![[Jurisight UC Diagram.png]]

---
### UC01 — Pesquisar jurisprudência com contexto de PDF

| Campo                | Descrição                                                                                                                                                                                                                                           |
| -------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Ator principal**   | Advogado / Assistente Jurídica                                                                                                                                                                                                                      |
| **Pré-condição**     | PDF do processo disponível para upload                                                                                                                                                                                                              |
| **Fluxo principal**  | 1. Usuário faz upload do PDF → 2. Sistema extrai entidades via LLM → 3. Usuário revisa entidades e informa intenção argumentativa → 4. Sistema constrói query enriquecida → 5. Sistema retorna lista ranqueada de documentos com provimento e fonte |
| **Pós-condição**     | Lista de documentos jurídicos reais exibida, ordenada por hierarquia e relevância                                                                                                                                                                   |
| **Regra de negócio** | RF01, RF02, RF04, RF05, RF06, RN01                                                                                                                                                                                                                  |

---
### UC02 — Pesquisar jurisprudência por intenção argumentativa e entidades (sem PDF)
| Campo                | Descrição                                                                                                                                                                                    |
| -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Ator principal**   | Advogado / Assistente Jurídica                                                                                                                                                               |
| **Pré-condição**     | Nenhuma                                                                                                                                                                                      |
| **Fluxo principal**  | 1. Usuário preenche os campos das entidades e a intenção em texto livre → 2. Sistema monta query combinando intenção e campos preenchidos → 3. Sistema retorna lista ranqueada de documentos |
| **Pós-condição**     | Lista de documentos jurídicos reais exibida                                                                                                                                                  |
| **Regra de negócio** | RF03, RF05, RF06, RN01                                                                                                                                                                       |
| **Observação**       | Query menos enriquecida que UC01 (sem PDF); resultados tendem a ser mais genéricos                                                                                                           |

---
### UC03 — Filtrar resultados por período

| Campo | Descrição |
|---|---|
| **Ator principal** | Advogado / Assistente Jurídica |
| **Pré-condição** | Consulta já realizada |
| **Fluxo principal** | 1. Usuário seleciona período (ex: 2020–2024) → 2. Sistema aplica filtro de metadado `data` no ChromaDB → 3. Resultados exibidos dentro do período informado |
| **Pós-condição** | Lista filtrada por período exibida |
| **Regra de negócio** | RF08 |

---
### UC04 — Revisar entidades extraídas do PDF

| Campo | Descrição |
|---|---|
| **Ator principal** | Advogado / Assistente Jurídica |
| **Pré-condição** | PDF processado (UC01 executado parcialmente) |
| **Fluxo principal** | 1. Sistema exibe entidades extraídas (agente nocivo, NRs, período, setor) → 2. Usuário corrige ou complementa as entidades → 3. Usuário confirma e prossegue para a busca |
| **Pós-condição** | Query enriquecida construída com entidades validadas pelo usuário |
| **Regra de negócio** | RF02, RF04 |

---
### UC05 – Filtrar resultados por provimento

| Campo            | Descrição                                                                                                                                                                                      |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ator principal   | Advogado / Assistente Jurídica                                                                                                                                                                 |
| Pré-condição     | Consulta já realizada (UC01 ou UC02)                                                                                                                                                           |
| Fluxo principal  | 1. Usuário marca checkbox “Apenas decisões favoráveis” ou seleciona “Aprovado”/“Negado” → 2. Sistema aplica filtro no ChromaDB pelo metadado `provimento` → 3. Resultados atualizados exibidos |
| Pós-condição     | Lista filtrada por provimento                                                                                                                                                                  |
| Regra de negócio | RF10, RN05                                                                                                                                                                                     |

---
### UC06 – Visualizar detalhes de um documento

|Campo|Descrição|
|---|---|
|Ator principal|Advogado / Assistente Jurídica|
|Pré-condição|Lista de resultados visível|
|Fluxo principal|1. Usuário clica em um card de resultado → 2. Sistema busca documento completo no PostgreSQL via `documento_id` → 3. Exibe modal/nova página com ementa integral, texto completo do acórdão, relator, data, link original|
|Pós-condição|Documento detalhado exibido|
|Regra de negócio|RF06, RN04|

---
### UC07 – Copiar citação

| Campo            | Descrição                                                                                                                                |
| ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| Ator principal   | Advogado / Assistente Jurídica                                                                                                           |
| Pré-condição     | Resultados exibidos                                                                                                                      |
| Fluxo principal  | 1. Usuário clica em “Copiar citação” → 2. Sistema formata número, relator, ementa resumida e link → 3. Copia para área de transferência. |
| Pós-condição     | Citação disponível para colar no editor de petição                                                                                       |
| Regra de negócio | RN04                                                                                                                                     |

---
### UC08 – Refinar consulta

| Campo            | Descrição                                                                                                                                                                                                                                     |
| ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Ator principal   | Advogado / Assistente Jurídica                                                                                                                                                                                                                |
| Pré-condição     | Resultados exibidos (após UC01 ou UC02)                                                                                                                                                                                                       |
| Fluxo principal  | 1. Usuário clica em “Refinar consulta” → 2. Sistema reabre o formulário com a estrutura argumentativa anterior (se houver) e a intenção original → 3. Usuário edita livremente → 4. Sistema reexecuta a busca (passos 5-8 do fluxo principal) |
| Pós-condição     | Nova lista de resultados baseada na consulta refinada                                                                                                                                                                                         |
| Regra de negócio | RF02, RF03, RF04                                                                                                                                                                                                                              |

---

## 2.3 Requisitos Funcionais (RF)

- RF01 — O sistema deve permitir que o usuário faça upload de um PDF do caso como contexto principal da busca
    
- RF02 – O sistema deve extrair automaticamente do PDF (ou, na falta deste, da intenção argumentativa em texto livre) a **estrutura argumentativa jurídica** conforme schema predefinido (==campos: `pedido_principal`, `agente_nocivo`, `violacoes`, `normas`, `empresa_ciente`, `setor`, `cargo`, `tese_central`==), utilizando LLM local com prompt estruturado e saída JSON validável.
    
- RF03 — O sistema deve permitir que o usuário informe a intenção argumentativa em texto livre (ex: "quero provar insalubridade por benzeno sem EPI")
    
- RF04 — O sistema deve combinar extração automática do PDF com a intenção argumentativa para construir uma query enriquecida (Query Enrichment)

- RF05 — O sistema deve recuperar documentos jurídicos do Falcão de 3 tipos — ==acórdãos, súmulas, orientações jurisprudenciais== — semanticamente alinhados ao contexto e à tese informada

> [!NOTE]
> #### Existem mais tipos de documentos jurídicos(Decisões Monocráticas...), mas seria muito para ser extraído e carregado localmente


- RF06 — O sistema deve exibir a fonte real de cada documento retornado — número, tipo, data, relator e link — nunca gerando documento fictício

- RF07 — O sistema deve identificar visualmente o tipo de cada documento retornado, permitindo que o advogado compreenda de imediato seu peso jurídico

- RF08 — O sistema deve permitir que o usuário filtre os resultados por período além do retorno já em ordem de relevância semântica

- RF09 — O documento privado enviado pelo usuário deve ser processado exclusivamente em memória RAM durante a sessão e descartado ao encerramento, sem persistência em disco, banco de dados ou log

- **RF10 — O sistema deve extrair automaticamente, durante a ingestão de cada documento jurídico, o metadado `provimento` com valores possíveis `Aprovado` (decisão favorável ao trabalhador/autor) ou `Negado` (decisão desfavorável), utilizando regras baseadas no texto do dispositivo ou voto**

- **RF11** – O sistema deve armazenar os documentos jurídicos coletados (acórdãos, súmulas, OJs) no PostgreSQL, mantendo todos os metadados extraídos (inclusive `provimento` e `hierarquia_categoria`). O ChromaDB deve conter apenas os chunks, embeddings e metadados mínimos de filtragem, com referência ao `id` do PostgreSQL.

- **RF12** – O sistema deve permitir que o usuário visualize o documento jurídico completo (ementa integral, texto do acórdão, relator, data, link original) a partir de qualquer resultado da lista.

- **RF13** – O sistema deve fornecer um botão ou ícone para copiar a citação formatada do documento (número, relator, ementa resumida, link) para a área de transferência do sistema operacional.

- **RF14** – O sistema deve permitir que o usuário refine a consulta original (editando a intenção argumentativa e/ou a estrutura extraída) e reexecute a busca sem precisar recomeçar do zero.

---

## 2.4 Requisitos Não Funcionais (RNF)

- RNF01 — O sistema não deve gerar acórdãos fictícios — toda resposta deve ser fundamentada em fonte indexada real
    
- RNF02 — O tempo de resposta por consulta deve ser inferior a 30 segundos, com meta de 15 segundos em condições normais — SLA compatível com pipeline local rodando LLM, embeddings e busca híbrida
    
- RNF03 — O sistema deve garantir confidencialidade jurídica dos documentos privados enviados pelo usuário por meio de processamento 100% local: todos os componentes de IA (LLM, embeddings, NER) rodam via Ollama no hardware do operador, sem envio de dados para APIs externas
    
- RNF04 — A interface deve ser acessível a usuários sem conhecimento técnico
    
- RNF05 — O sistema deve suportar documentos de entrada de qualquer tamanho no Query Enrichment por meio de sumarização hierárquica prévia: documentos que ultrapassem o limite de contexto do LLM (ex: petições longas) são divididos em blocos, sumarizados individualmente e depois condensados numa tese única antes do cruzamento com a base extraída do Falcão
    
- RNF06 — O sistema deve ordenar os resultados pela hierarquia das fontes jurídicas brasileiras: súmulas → orientações jurisprudenciais → acórdãos
    

---

## 2.5 Regras de Negócio

- RN01 — O sistema opera exclusivamente sobre documentos públicos do TST — acórdãos, súmulas, OJs — coletados via scraping do portal oficial; nenhuma fonte privada ou paga é utilizada
    
- RN02 — A ordenação dos resultados segue a hierarquia das fontes jurídicas brasileiras, conforme doutrina consolidada: súmulas têm precedência sobre OJs, OJs sobre acórdãos, acórdãos sobre decisões monocráticas — sem pesos numéricos arbitrários
    
- RN03 — Nenhum documento privado enviado pelo usuário é armazenado ou indexado permanentemente

- RN04 — Toda resposta gerada pelo LLM deve obrigatoriamente citar o documento de origem com número, tipo e **link verificável** (importante lembrar de anexar na hora do scraping)
    
- RN05 — O metadado `provimento` é extraído automaticamente durante a ingestão e armazenado no índice. Para acórdãos, a classificação se baseia no resultado do dispositivo (ex: "provido", "improvido", "deferido", "denegado"). Para súmulas e OJs, que não possuem provimento no mesmo sentido, o campo pode ser `Nulo` ou não se aplica, mas o sistema ainda deve permitir filtragem quando aplicável.

- RN06 – A estrutura argumentativa extraída do documento do usuário **nunca é persistida** (apenas memória RAM durante a sessão). Antes da busca, o sistema deve exibir os campos extraídos para que o usuário possa corrigir ou complementar (UC04). O LLM deve ser instruído a não alucinar valores; campos não encontrados no texto devem ser preenchidos com `null` ou lista vazia.

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
    
2. Sistema extrai o texto via pdfplumber e utiliza o LLM local (Llama 3.2 3B) com um prompt estruturado (few-shot, saída JSON) para extrair a **estrutura argumentativa jurídica** contendo os campos: ==`pedido_principal`, `agente_nocivo`, `violacoes`, `normas`, `empresa_ciente`, `setor`, `cargo`, `tese_central`==. O modelo é instruído a preencher com `null` ou lista vazia quando a informação não estiver presente.
    
3. Sistema exibe cada campo da estrutura extraída em uma interface de revisão (UC04). O advogado pode editar qualquer campo, adicionar itens às listas ou corrigir a tese_central. Essa interação é fundamental para eliminar alucinações e refinar a query antes da busca.
    
4. Advogado informa a intenção argumentativa em texto livre (ex: "quero provar que a empresa tinha conhecimento da exposição e não forneceu EPI adequado") e **opcionalmente seleciona o filtro "Apenas decisões favoráveis (provimento Aprovado)"**
    
5. Sistema constrói a query enriquecida combinando contexto extraído do PDF + intenção argumentativa (**Query Enrichment**)
	1. 5a. O sistema transforma a estrutura validada em duas representações:

		- **Query lexical (para BM25):** concatenação dos campos `pedido_principal`, `agente_nocivo`, `violacoes`, `normas`, `setor`, `cargo` em uma única string rica em termos-chave.
    
		- **Query semântica (para embedding):** utiliza apenas o campo `tese_central` (frase curta) para gerar o embedding via `nomic-embed-text-v2`.  
		Essas duas queries alimentam a busca híbrida.
    
6. Pipeline de busca híbrida (ChromaDB + BM25 + RRF) processa a query enriquecida sobre os documentos indexados do TST, **aplicando o filtro de provimento se solicitado**
    
7. Sistema retorna lista de documentos relevantes com posicionamento, resumo do argumento central e citação completa da fonte, **indicando visualmente se a decisão foi Aprovada ou Negada**
    
8. 8. Advogado pode, a partir dos resultados:

	- **Visualizar detalhes completos** (UC06) de qualquer documento;
    
	- **Copiar citação formatada** (UC07) para colar diretamente na petição;
    
	- **Refinar a consulta** (UC08) se os resultados não atenderem à expectativa;
    
	- **Filtrar por provimento** (UC05) ou período (UC03) dinamicamente.
    
9. Documento privado é descartado da memória — nenhum dado privado é persistido
    

---

## 3.2 Fluxos Alternativos

### FA01 — Usuário não faz upload de PDF (busca apenas por intenção argumentativa)

| Passo | Comportamento |
|---|---|
| Trigger | Usuário acessa o sistema sem selecionar arquivo e informa apenas a intenção argumentativa |
| Desvio | Etapas 2, 3 e a parte de extração do PDF do Passo 5 são ignoradas |
| Comportamento | Sistema usa a intenção argumentativa diretamente como query para a busca híbrida |
| Resultado | Retorno menos enriquecido contextualmente, porém funcional |
| Mensagem ao usuário | "Busca realizada sem contexto de documento. Para resultados mais precisos, faça o upload do PDF do caso." |

---

### FA02 — PDF não tem texto extraível (documento escaneado/imagem)

| Passo               | Comportamento                                                                                                                                                         |
| ------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Trigger             | pdfplumber retorna texto vazio ou abaixo de um limiar mínimo de caracteres                                                                                            |
| Desvio              | Etapas 2 e 3 do fluxo principal são puladas                                                                                                                           |
| Comportamento       | Sistema notifica o usuário que o PDF não pôde ser processado e prossegue como FA01                                                                                    |
| Resultado           | Busca realizada apenas com a intenção argumentativa                                                                                                                   |
| Mensagem ao usuário | "Não foi possível extrair texto do PDF enviado (possível documento escaneado). Por favor, informe o contexto manualmente ou envie uma versão com texto selecionável." |

---

### FA03 — Nenhum resultado encontrado

| Passo               | Comportamento                                                                                                                        |
| ------------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| Trigger             | Pipeline de busca retorna 0 resultados acima do threshold de similaridade mínima                                                     |
| Comportamento       | Sistema exibe estado vazio com sugestão de reformulação                                                                              |
| Resultado           | Nenhum card de acórdão exibido                                                                                                       |
| Mensagem ao usuário | "Nenhum documento encontrado para esta consulta. Tente ampliar a intenção argumentativa ou remover filtros de provimento e período." |

---

### FA04 — Filtro de provimento retorna resultados insuficientes

| Passo | Comportamento |
|---|---|
| Trigger | Filtro `provimento = Aprovado` aplicado, mas retorna menos de 3 resultados |
| Comportamento | Sistema exibe os resultados disponíveis e sugere ampliar o filtro |
| Resultado | Resultados filtrados exibidos com aviso |
| Mensagem ao usuário | "Apenas N resultado(s) encontrado(s) com provimento favorável. Considere remover o filtro para ver todas as decisões sobre o tema." |

---

### FA05 — Documento PDF muito extenso (> limite de contexto do LLM)

| Passo | Comportamento |
|---|---|
| Trigger | Texto extraído do PDF excede a janela de contexto do Llama 3.2 3B |
| Comportamento | Sistema ativa automaticamente sumarização hierárquica: divide o texto em blocos, sumariza cada bloco individualmente e condensa numa tese única (RNF05) |
| Resultado | Query Enrichment executado normalmente sobre a tese condensada |
| Mensagem ao usuário | "Documento extenso detectado. Processando em blocos para garantir que nenhuma informação relevante seja perdida..." |

---

# 4. Mockups e Experiência do Usuário (UX)

## 4.1 Tela Principal — Entrada de Consulta

![[Pasted image 20260507161225.png]]
![[Pasted image 20260507161320.png]]

---

## 4.2 Tela de Revisão de Entidades Extraídas

Exibida após o processamento do PDF, antes da busca:
![[Pasted image 20260514141700.png]]

## 4.3 Tela de Resultados
![[Pasted image 20260514141711.png]]
![[Pasted image 20260514141831.png]]
## Item especifico:
![[Pasted image 20260514141735.png]]
![[Pasted image 20260514141749.png]]

---

# 5. Arquitetura do Sistema

## 5.1 Diagrama C4

### Nível 1 — Contexto do Sistema
![[JuriSightC4Nivel1.svg]]
### Nível 2 — Containers
![[JuriSightC4Nivel2.svg]]
### Nível 3 — Component
#### Backend
![[JuriSightC4Nivel3BackEnd.svg]]
#### Frontend
![[JuriSightC4Nivel3FrontEnd.svg]]
#### Pipeline Ingestão
![[JuriSightC4NIvel3PipelineIngestão.svg]]

---

## 5.2 Modelo de Dados

### Entidade: `DocumentoJuridico` (armazenada no PostgreSQL)

Esta é a fonte de verdade, armazenada no PostgreSQL em schema relacional tipado. Cada documento corresponde a um acórdão, súmula, OJ, etc., coletado do TST.

|Campo|Tipo|Descrição|Exemplo|
|---|---|---|---|
|`id`|`UUID`|Identificador único do documento (PRIMARY KEY)|`gen_random_uuid()`|
|`tipo_documento`|`string`|Tipo do documento|`"ACORDAO"`, `"SUMULA"`, `"OJ"`|
|`hierarquia_categoria`|`int`|Prioridade para ordenação (4 = acórdão, 3 = OJ, 2 = súmula, etc.)|`4`|
|`numero_processo`|`string`|Número do processo (ou identificador da súmula/OJ)|`"RR-1234-56.2021.5.03.0000"`|
|`tribunal`|`string`|Tribunal de origem|`"TST"`, `"TRT4"`|
|`relator`|`string`|Nome do relator|`"Min. Plauto Carneiro Porto"`|
|`turma`|`string`|Turma julgadora|`"3ª Turma"`|
|`gabinete`|`string`|Gabinete responsável|`"Gab. Des. Plauto Carneiro Porto"`|
|`classe_processo`|`string`|Classe do processo|`"Recurso Ordinário Trabalhista"`|
|`sigla_classe`|`string`|Sigla da classe|`"ROT"`|
|`data_julgamento`|`date` ou `string`|Data do julgamento (ISO)|`"2026-03-11"`|
|`data_juntada`|`date` ou `string`|Data de juntada ao sistema|`"2026-03-12"`|
|`data_filtro`|`date`|Data usada no scraping (controle interno)|`"2026-03-12"`|
|`id_documento`|`string`|Identificador original do portal TST|`"acordao_123456"`|
|`referencia_legislativa`|`list[string]`|Lista de normas citadas (ex: `"art_11_clt"`, `"sumula_214_tst"`)|`["art_192_clt", "nr_15"]`|
|`possui_ementa`|`bool`|Indica se o documento possui ementa|`true`|
|`ementa`|`string`|Texto da ementa (resumo oficial)|`"Insalubridade. Benzeno..."`|
|`acordao`|`string`|Texto completo do acórdão (relatório, votos, dispositivo)|`"RELATÓRIO: ..."`|
|`provimento`|`enum`|`"APROVADO"`, `"NEGADO"`, `"NAO_APLICAVEL"` (extraído via regex do dispositivo)|`"APROVADO"`|
|`link_original`|`string` (URL)|Link para o portal do TST|`"https://jurisprudencia.tst.jus.br/..."`|

**Notas:**

- `hierarquia_categoria` será usada na ordenação final (valores: 1=súmula, 2=OJ, 3=precedente normativo, 4=acórdão, 5=decisão monocrática).
- `provimento` é extraído durante a ingestão, via regras textuais sobre o dispositivo.
- Os campos `ementa` e `acordao` são extraídos do HTML do portal.
---
### Entidade (temporária): `EstruturaArgumentativa`

Armazenada apenas em memória durante a sessão do usuário. Representa o entendimento do caso do advogado.

| Campo              | Tipo             | Descrição                              | Exemplo                                                               |
| ------------------ | ---------------- | -------------------------------------- | --------------------------------------------------------------------- |
| `pedido_principal` | `string`         | O que se pede na ação                  | `"adicional de insalubridade grau máximo"`                            |
| `agente_nocivo`    | `list[string]`   | Agentes de risco                       | `["benzeno"]`                                                         |
| `violacoes`        | `list[string]`   | Condutas omissivas ou comissivas       | `["ausência de EPI eficaz", "falta de treinamento"]`                  |
| `normas`           | `list[string]`   | Normas jurídicas citadas               | `["NR-15", "CLT art. 192"]`                                           |
| `empresa_ciente`   | `bool \| null`   | Evidência de ciência patronal          | `true`                                                                |
| `setor`            | `string \| null` | Ramo de atividade                      | `"metalurgia"`                                                        |
| `cargo`            | `string \| null` | Cargo do trabalhador                   | `"operador de prensa"`                                                |
| `tese_central`     | `string`         | Frase que resume o argumento principal | `"A empresa tinha ciência do risco e não forneceu proteção adequada"` |

**Nota:** Este modelo não é armazenado no ChromaDB, apenas usado para enriquecer a consulta.

---
### Entidade: `Chunk` (armazenada no ChromaDB, com referência ao PostgreSQL)

Cada chunk corresponde a um fragmento do `acordao` (ou `ementa` para documentos curtos), processado via SAC Chunking.

| Campo                                                              | Tipo            | Descrição                                                                   |
| ------------------------------------------------------------------ | --------------- | --------------------------------------------------------------------------- |
| `chunk_id`                                                         | `string` (UUID) | Identificador único do chunk                                                |
| `documento_id`                                                     | `string` (UUID) | `id` do documento no PostgreSQL (chave estrangeira)                         |
| `texto`                                                            | `string`        | Texto do chunk (600–800 tokens) com prefixo da ementa (SAC)                 |
| `sac_summary`                                                      | `string`        | Ementa usada como contexto global (prefixo SAC)                             |
| `embedding_completo`                                               | `vector[768]`   | Embedding do `texto` (chunk + SAC summary)                                  |
| `embedding_ementa`                                                 | `vector[768]`   | Embedding da `sac_summary` (ementa/tese)                                    |
| `posicao`                                                          | `int`           | Posição ordinal do chunk dentro do documento                                |
| **Metadados de filtragem (armazenados separadamente no ChromaDB)** |                 |                                                                             |
| `tipo_documento`                                                   | `string`        | `"ACORDAO"`, `"SUMULA"`, `"OJ"`, ...                                        |
| `provimento`                                                       | `string`        | `"APROVADO"`, `"NEGADO"`, `"NAO_APLICAVEL"`                                 |
| `data_julgamento`                                                  | `string`        | Data ISO (`2026-03-11`) para filtro por período                             |
| `numero_processo`                                                  | `string`        | Número do processo (exibição rápida)                                        |
| `hierarquia_categoria`                                             | `int`           | Prioridade (1=súmula, 2=OJ, 3=precedente, 4=acórdão, 5=decisão monocrática) |

**Nota:** Os metadados de filtragem são duplicados no ChromaDB para permitir filtros eficientes (por `provimento`, `data`, `tipo`) durante a busca vetorial, sem necessidade de consultar o PostgreSQL a cada busca.
**Nota sobre Poly-Vector Indexing:** Dois embeddings são gerados por chunk com o modelo `nomic-embed-text-v2`. O `embedding_completo` captura o contexto argumentativo detalhado do voto; o `embedding_ementa` captura a tese jurídica consolidada. Durante a busca, ambos os vetores são consultados independentemente e os resultados são fundidos via RRF. Isso é especialmente relevante para súmulas e OJs, cujo texto é curto mas juridicamente denso — o embedding isolado da ementa garante que não se perca precisão na recuperação desses documentos.

---

### Schema de Metadados no ChromaDB

Cada chunk armazenado no ChromaDB carrega os seguintes metadados para filtragem:

```python
{
    "chunk_id":      str,   # UUID do chunk
    "documento_id":  str,   # UUID do documento pai
    "tipo":          str,   # "ACORDAO" | "SUMULA" | "OJ" | "PRECEDENTE_NORMATIVO" | "DECISAO_MONOCRATICA"
    "numero":        str,   # número do processo/súmula
    "data":          str,   # ISO 8601: "2023-08-22"
    "relator":       str,   # nome do relator ou ""
    "provimento":    str,   # "APROVADO" | "NEGADO" | "NAO_APLICAVEL"
    "link_original": str,   # URL verificável no TST
    "posicao":       int,   # posição do chunk no documento
}
```

---

## 5.3 Principais Componentes

**Pipeline de IA completo**

| Etapa                                                         | Componente                                               | Responsabilidade                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                           |
| ------------------------------------------------------------- | -------------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Ingestão                                                   | Scraper Falcão (Scrapy + Playwright)                     | Coleta todos os tipos de documento do portal TST (acórdãos, súmulas, OJs, precedentes normativos, decisões monocráticas) com suporte a delta (apenas documentos novos). Para cada documento, extrai metadados brutos (número, tribunal, relator, turma, data julgamento, data juntada, referências legislativas, etc.) e o HTML completo.                                                                                                                                                                                                                                                                                                                                                                                  |
| 2. Extração de conteúdo HTML e classificação                  | BeautifulSoup + Regex + Parser customizado               | Extrai do HTML as seções estruturadas: **ementa** (resumo oficial) e **acordao** (texto completo: relatório, votos, dispositivo). Aplica regras (regex) sobre o dispositivo para classificar `provimento` como `APROVADO`, `NEGADO` ou `NAO_APLICAVEL` (para súmulas/OJs). Define `hierarquia_categoria` (1=súmula, 2=OJ, 3=precedente normativo, 4=acórdão, 5=decisão monocrática). **Persiste o objeto `DocumentoJuridico` no PostgreSQL** com todos os campos (incluindo `ementa`, `acordao`, `numero_processo`, `relator`, `data_julgamento`, `referencia_legislativa`, `link_original`, etc.).                                                                                                                           |
| 3. Chunking                                                   | SAC Chunker (sem LLM)                                    | Utiliza a **ementa** como resumo global (SAC). Divide o `acordao` (texto completo) em chunks de 600–800 tokens. Cada chunk recebe a ementa como prefixo (para manter contexto global). Gera metadados: `chunk_id`, `documento_id` (referência ao `id` do PostgreSQL), `posicao`, `sac_summary` (a própria ementa). **Não usa LLM para chunking** (baixo custo computacional).                                                                                                                                                                                                                                                                                                                                                |
| 4. Embeddings                                                 | Poly-Vector (nomic-embed-text-v2 via Ollama)             | Para cada chunk, gera dois embeddings: `embedding_completo` (do texto do chunk + ementa) e `embedding_ementa` (apenas da ementa). Ambos são vetores de 768 dimensões. O embedding duplo melhora recuperação de súmulas e OJs (texto curto mas denso).                                                                                                                                                                                                                                                                                                                                                                                                                                                                      |
| 5. Indexação vetorial e lexical                               | ChromaDB + rank_bm25                                     | **ChromaDB:** Armazena cada chunk com seus dois embeddings e metadados mínimos para filtragem (`tipo_documento`, `provimento`, `data_julgamento`, `numero_processo`, `documento_id`). O texto completo do chunk também é salvo (campo `document`). **rank_bm25:** Constrói índice lexical (arquivo JSON/pickle) a partir do campo `texto` (chunk + ementa) para busca por termos exatos (NR-15, CLT art. 193, benzeno).                                                                                                                                                                                                                                                                                                    |
| 6. Extração de PDF do usuário                                 | pdfplumber + sumarização hierárquica (quando necessário) | Extrai todo o texto do PDF enviado pelo advogado (petição, laudo, notificação). Se o texto ultrapassar a janela de contexto do LLM (Llama 3.2 3B), aplica sumarização hierárquica: divide em blocos, sumariza cada bloco, depois condensa em uma tese única. Nenhum dado privado é persistido (apenas memória RAM).                                                                                                                                                                                                                                                                                                                                                                                                        |
| 7. Query Enrichment com Estrutura Argumentativa               | LLM local (Llama 3.2 3B) + validação Pydantic            | Recebe o texto extraído do PDF (ou a intenção argumentativa em texto livre) e, via prompt estruturado (few-shot, saída JSON), extrai a **Estrutura Argumentativa** (schema fixo): `pedido_principal`, `agente_nocivo`, `violacoes`, `normas`, `empresa_ciente`, `setor`, `cargo`, `tese_central`. Após extração, a estrutura é exibida para o usuário revisar/corrigir (UC04). **Em seguida, o sistema produz duas representações:** (a) **string lexical** – concatenação dos campos `pedido_principal`, `agente_nocivo`, `violacoes`, `normas`, `setor`, `cargo` (separados por espaços) – usada no BM25; (b) **frase tese** – o campo `tese_central` – usada para gerar o embedding da query (via nomic-embed-text-v2). |
| 8. Busca Híbrida                                              | ChromaDB + BM25 + RRF (Reciprocal Rank Fusion)           | Executa **busca vetorial** no ChromaDB usando o embedding da `tese_central` (com filtros opcionais por `provimento`, `data_julgamento`, `tipo_documento`). Executa **busca lexical** (BM25) usando a string lexical enriquecida. Combina os dois rankings via RRF, retornando os top-20 `chunk_id` com scores combinados.                                                                                                                                                                                                                                                                                                                                                                                                  |
| 9. Recuperação de documentos completos e ordenação categórica | FastAPI (backend) + PostgreSQL                              | Com a lista de `chunk_id` e seus respectivos `documento_id`, o backend consulta o PostgreSQL para obter o documento completo (`DocumentoJuridico`) de cada chunk, incluindo `ementa`, `numero_processo`, `relator`, `data_julgamento`, `link_original`, `hierarquia_categoria`, `provimento`, etc. **Ordena os resultados** primeiramente pelo campo `hierarquia_categoria` (respeitando a hierarquia das fontes jurídicas: súmulas → OJs → precedentes normativos → acórdãos → decisões monocráticas) e, dentro do mesmo nível hierárquico, mantém a ordem do RRF (score combinado).                                                                                                                                         |
| 10. Interface web                                             | Next.js 14 + FastAPI                                     | Exibe tela de upload de PDF, campo para intenção argumentativa, **checkbox "Apenas decisões favoráveis"** (filtro por `provimento = APROVADO`) e interface de revisão da estrutura extraída. Apresenta os resultados ordenados com cards contendo: tipo do documento (com ícone), número do processo, ementa resumida, relator, data, selo de provimento (aprovado/negado/não aplicável), link clicável para o portal TST e botão para copiar citação. O documento privado do usuário nunca é persistido.                                                                                                                                                                                                                  |

[^1]: A geração de dois embeddings por chunk (Poly-Vector Indexing) é uma decisão deliberada. O `embedding_completo` captura o contexto argumentativo rico do voto; o `embedding_ementa` captura a tese jurídica consolidada. Os dois são consultados independentemente na busca e fundidos via RRF, resultando em recuperação mais precisa tanto na tese quanto no contexto, especialmente para súmulas e OJs cujo texto é curto mas juridicamente denso.

---

## 5.4 Decisões Arquiteturais — Por que o sistema é construído dessa forma

Esta seção documenta as decisões técnicas centrais do projeto, explicando o raciocínio por trás de cada escolha arquitetural.

---

### Decisão 1 — Por que RAG e não um LLM puro?

LLMs como GPT-4 ou Llama cometem **alucinações** — geram acórdãos com números de processo, datas e ementas completamente inventados, mas com aparência convincente. No domínio jurídico, citar uma fonte fictícia é um erro grave que pode comprometer uma petição e a credibilidade do advogado.

RAG (Retrieval-Augmented Generation) resolve isso fundamentalmente: o LLM só pode falar sobre acórdãos que existem na base indexada. A geração é ancorada em documentos reais. Todo resultado citado tem número de processo, data e relator verificáveis.

---

### Decisão 2 — Por que busca híbrida (BM25 + Embeddings) e não apenas vetorial?

Embeddings capturam significado semântico mas podem falhar em termos técnicos exatos. "NR-15", "CLT art. 193", "LTCAT" e "benzeno" são strings que precisam ser encontradas exatamente — um embedding pode aproximar "NR15" de "norma quinze" semanticamente, mas perder um acórdão que usa exatamente "NR-15".

BM25 garante precisão lexical — encontra o termo exato. Embeddings garantem compreensão semântica — encontram o contexto similar. Reciprocal Rank Fusion mescla os dois rankings, priorizando documentos que aparecem bem em ambas as buscas. Para um domínio com terminologia técnica precisa como o jurídico trabalhista, essa combinação é superior a qualquer abordagem isolada.

---

### Decisão 3 — Por que SAC Chunking?

Acórdãos trabalhistas sobre o mesmo tema (ex: insalubridade por benzeno) são estruturalmente muito similares entre si — mesma estrutura de ementa, mesmo vocabulário, mesmas referências normativas. RAG com chunking tradicional frequentemente recupera o chunk certo mas do acórdão errado, porque os chunks isolados parecem idênticos.

SAC (Summary-Augmented Chunking) resolve isso adicionando o resumo global do acórdão (ementa) como contexto de cada chunk. Assim o sistema sabe não apenas o que o trecho diz, mas de qual decisão específica ele veio. A ementa dos acórdãos do TST é naturalmente o identificador semântico único de cada decisão — o SAC aproveita essa estrutura existente.

---

### Decisão 4 — Por que Query Enrichment com upload de PDF?

A principal dor relatada pela especialista do domínio foi que ferramentas atuais retornam acórdãos sobre o tema, mas não sobre a situação específica do caso. Um advogado que busca "insalubridade benzeno" recebe milhares de resultados — mas seu caso é específico: trabalhador metalúrgico, exposição entre 2018 e 2022, empresa contesta com laudo próprio, sem EPI documentado.

Query Enrichment resolve isso extraindo automaticamente o contexto específico do documento do caso com NER, combinando com a intenção argumentativa digitada pelo advogado, e construindo uma query muito mais rica e precisa. O resultado é busca pelo caso específico, não pelo tema genérico — exatamente o que a especialista descreveu como sistema ideal.

O documento privado é processado exclusivamente em memória e descartado ao fim da sessão, garantindo conformidade com a LGPD.

---

### Decisão 5 — Por que extrair e armazenar o metadado `provimento` (Aprovado/Negado)?

A principal lacuna das ferramentas atuais é a incapacidade de alinhar os resultados à **intenção argumentativa** do advogado. O profissional não quer apenas acórdãos sobre o tema; quer acórdãos que **corroborem sua tese** — ou seja, decisões favoráveis ao seu cliente.

Ao extrair automaticamente o provimento (Aprovado/Negado) durante a ingestão, o sistema permite que o advogado filtre os resultados de acordo com sua necessidade: "só me mostre decisões onde o pedido foi deferido". Esse metadado é simples de extrair (regras textuais sobre o dispositivo) e entrega um dos maiores diferenciais do sistema, sem complexidade adicional de grafos ou ontologias profundas.

---

### Decisão 6 — Por que não utilizar GraphRAG ou grafo de conhecimento?

Após análise aprofundada do escopo e das necessidades reais dos usuários (advogados e assistentes jurídicos), identificou-se que as perguntas típicas do dia a dia são de **similaridade semântica e lexical** com a tese do caso, e não de navegação relacional complexa (ex: "cadeia de precedentes", "quais acórdãos revogaram a súmula X"). Além disso, construir e manter um grafo de conhecimento jurídico com ontologia própria exigiria esforço desproporcional para o benefício marginal obtido.

Portanto, a arquitetura atual **não inclui GraphRAG**, mantendo-se focada na busca híbrida (Chroma + BM25 + RRF) com enriquecimento de metadados (especialmente o provimento). Isso reduz drasticamente a complexidade de implementação, a latência e os custos de manutenção, sem sacrificar os objetivos principais do sistema.

---

### Decisão 7 — Por que LLM local (Ollama + Llama 3.2 3B) e não API externa?

APIs externas como Groq ou OpenAI introduzem custo operacional, dependência de conectividade e envio de dados potencialmente sensíveis para servidores externos. Para um sistema jurídico onde o advogado pode subir documentos do caso, isso é indesejável mesmo que o documento seja descartado após a sessão.

Ollama permite rodar modelos localmente sem custo, inclusive em CPU para modelos leves como Llama 3.2 3B. Para as tarefas do sistema — geração de resumos SAC (80-120 tokens) e extração de tese no Query Enrichment — o Llama 3.2 3B é suficiente. Isso mantém todo o pipeline offline, com custo R$ 0 e sem envio de dados para terceiros.

---

### Decisão 8 — Por que Poly-Vector Embeddings (2 vetores por chunk)?

Embeddings únicos por chunk capturam ou o contexto argumentativo detalhado ou a tese jurídica consolidada — raramente os dois com igual precisão. Súmulas e OJs têm texto curto mas juridicamente denso: um embedding único tende a capturar a forma mas perder a profundidade da tese.

Poly-Vector Indexing resolve isso gerando dois embeddings por chunk com o modelo nomic-embed-text-v2: um do chunk completo com SAC summary (contexto argumentativo rico) e um da ementa/tese isolada (precisão jurídica). Durante a busca, ambos os vetores são consultados independentemente e os resultados fundidos via RRF. O resultado é recuperação que é simultaneamente precisa na tese jurídica e rica no contexto argumentativo — especialmente relevante para documentos curtos como súmulas e OJs.

---

### Decisão 9 — Por que indexar todos os tipos de documento e não apenas acórdãos?

O portal do TST disponibiliza sete tipos de documento: acórdãos, decisões monocráticas, súmulas, precedentes normativos, orientações jurisprudenciais, decisões da presidência e da vice-presidência. Sistemas atuais como o Falcão e a busca do próprio TST retornam todos esses tipos misturados sem distinção de relevância argumentativa.

O sistema proposto indexa todos os tipos mas os trata de forma diferenciada no pipeline e na apresentação. Isso é relevante porque uma súmula sobre insalubridade vale argumentativamente mais do que dezenas de acórdãos sobre o mesmo tema — ela representa o entendimento consolidado do tribunal, seguido por todos os juízes. Ignorar essa distinção é uma das limitações das ferramentas atuais relatada pela especialista do domínio.

---

### Decisão 10 — Por que ordenação categórica e não pesos numéricos?

A alternativa de atribuir pesos numéricos como súmula=5, acórdão=2 foi considerada e descartada por ser arbitrária — não há fundamentação científica ou jurídica para afirmar que súmula vale exatamente 2,5 vezes mais que um acórdão.

A ordenação categórica é defensável porque a hierarquia das fontes jurídicas — súmulas acima de OJs, OJs acima de acórdãos, acórdãos acima de decisões monocráticas — é doutrina consolidada no direito processual do trabalho brasileiro, não uma decisão do sistema. O sistema apenas implementa o que a doutrina já estabelece. Dentro de cada categoria, os documentos são ordenados por similaridade semântica com a query do advogado — essa sim é uma métrica objetiva e mensurável.

---

### Decisão 11 — Estratégia de Janela de Contexto para documentos longos

Petições iniciais e laudos periciais podem ter 30, 50 ou mais páginas. O Llama 3.2 3B tem janela de contexto limitada — jogar o documento inteiro no prompt geraria truncamento silencioso, perdendo partes relevantes do caso sem aviso.

A estratégia adotada é **sumarização hierárquica prévia**: o documento é dividido em blocos de tamanho controlado, cada bloco é sumarizado individualmente pelo LLM local, e os resumos são depois condensados numa tese única. Só essa tese final entra no Query Enrichment para cruzamento com a base do TST. Isso garante que nenhuma informação relevante seja perdida por truncamento, mesmo em documentos muito extensos, e mantém o custo computacional previsível independentemente do tamanho do documento original.

---

### Decisão 12 — Por que Next.js + FastAPI e não Streamlit?

Streamlit foi considerado pela simplicidade de prototipagem em Python, mas apresenta limitações relevantes para este projeto:

- **Controle de UX limitado:** Streamlit não permite experiências interativas refinadas como revisão inline de entidades extraídas, selos visuais de provimento e cards ricos — a interface jurídica exige clareza visual na diferenciação de tipos de documento e posicionamento, algo difícil de obter com os componentes nativos do Streamlit.
- **Ausência de separação de responsabilidades:** Num sistema com pipeline de IA complexo (Ollama + ChromaDB + BM25), misturar toda a lógica numa aplicação Streamlit dificulta testes, manutenção e eventual expansão.

A arquitetura adotada separa claramente as responsabilidades:

- **FastAPI (backend):** Expõe os endpoints REST `/query` e `/enrich`; orquestra Ollama, ChromaDB e BM25; gerencia o ciclo de vida do documento em memória; facilita testes unitários das etapas do pipeline.
- **Next.js 14 (frontend):** Interface web moderna com App Router; suporte nativo a upload de arquivos; componentes React para cards de resultado, selos de provimento e filtros interativos; deploy via Vercel ou self-hosted.

Essa separação também facilita a validação com a especialista do domínio — a interface pode ser iterada e publicada independentemente do backend.

### Decisão 13 — Por que utilizar PostgreSQL como camada de origem (source of truth) junto com ChromaDB?

O ChromaDB, sozinho, consegue armazenar embeddings, metadados e até o texto original do chunk. No entanto, para um sistema que precisa:

- Armazenar documentos jurídicos completos (acórdãos com muitas páginas) e seus metadados ricos (relator, turma, referências legislativas, etc.);
- Permitir futuras expansões (relatórios, atualizações em lote, correção de metadados sem reindexar todos os chunks);
- Garantir que o banco vetorial permaneça leve e rápido (armazenando apenas o essencial para a busca);

a separação de responsabilidades é a melhor prática.

**Por que PostgreSQL e não MongoDB:**

O modelo de dados do `DocumentoJuridico` é **estruturalmente fixo e bem definido** — os campos são conhecidos desde a ingestão (relator, turma, data, ementa, provimento, hierarquia_categoria, etc.) e não variam por documento. Esse perfil é exatamente o que bancos relacionais foram feitos para servir. MongoDB teria vantagem em schemas flexíveis e documentos heterogêneos — o que não é o caso aqui.

Adicionalmente, o PostgreSQL oferece:
- **Tipo `UUID` nativo** com `gen_random_uuid()` — substitui o `ObjectId` do MongoDB com UUIDs padrão diretamente referenciáveis pelo ChromaDB;
- **Tipo `TEXT[]` (array de strings)** para campos como `referencia_legislativa` — sem necessidade de tabela auxiliar;
- **Tipo `ENUM` nativo** para `provimento` (`APROVADO`, `NEGADO`, `NAO_APLICAVEL`) e `tipo_documento` — com validação a nível de banco;
- **Tipo `TEXT`** sem limite prático de tamanho para o campo `acordao` (texto completo do acórdão), eliminando a necessidade de fragmentação;
- **Índices GIN** sobre colunas `TEXT[]` para consultas por `referencia_legislativa` (ex: todos os documentos que citam `NR-15`);
- **Garantias ACID** — crítico em contexto jurídico onde integridade dos dados não é negociável.

**Arquitetura adotada:**

- **PostgreSQL**: guarda o documento integral (`DocumentoJuridico`) e todos os metadados em schema relacional tipado. É a única fonte de verdade.
- **ChromaDB**: armazena apenas os chunks, embeddings e um subconjunto mínimo de metadados usados para filtragem rápida (`tipo_documento`, `provimento`, `data_julgamento`, `documento_id`).

**Vantagens:**

- Atualização de metadados (ex: corrigir `provimento` de um acórdão) é feita no PostgreSQL via `UPDATE` simples, e os chunks no ChromaDB são facilmente reindexados (basta regenerar embeddings para aquele documento).

- Consultas de exibição (mostrar ementa, link, relator) não sobrecarregam o ChromaDB — vão direto ao PostgreSQL pelo `documento_id` (UUID).

- O ChromaDB mantém tamanho controlado, mesmo com centenas de milhares de chunks.

- Permite futuramente adicionar mais fontes (TRTs) sem redesenhar a indexação — basta inserir novos registros no mesmo schema.

- O `documento_id` armazenado no ChromaDB é um UUID padrão, diretamente utilizável como `WHERE id = $1` no PostgreSQL, sem conversão de tipo.
---

## 5.5 Stack Tecnológica

**Todo o pipeline de IA roda localmente — custo operacional R$ 0.**

| Tecnologia                       | Camada       | Função                                                                   | Justificativa                                                                                |
| -------------------------------- | ------------ | ------------------------------------------------------------------------ | -------------------------------------------------------------------------------------------- |
| Scrapy + Playwright              | Ingestão     | Scraping do portal TST                                                   | Coleta controlada com suporte a delta; Playwright para páginas com JavaScript                |
| BeautifulSoup + Regex            | Ingestão     | Extração de seções do HTML + classificação de provimento                 | Leve, sem dependência de LLM para a extração estrutural                                      |
| Ollama                           | IA (runtime) | Runtime local para LLMs                                                  | Permite rodar modelos localmente sem custo de API, até em CPU                                |
| Llama 3.2 3B (via Ollama)        | IA           | SAC Chunking + Query Enrichment + classificação de provimento (fallback) | Modelo leve suficiente para geração de resumos, extração de tese e classificação de decisões |
| nomic-embed-text-v2 (via Ollama) | IA           | Poly-Vector Embeddings                                                   | Modelo de embeddings com ótimo desempenho em português jurídico, roda local                  |
| ChromaDB                         | Dados        | Banco de vetores local                                                   | Persistente em disco, sem servidor externo, suporte a metadados e filtros                    |
| PostgreSQL                       | Dados        | Banco relacional — source of truth dos documentos jurídicos              | Schema fixo e tipado (UUID, ENUM, TEXT[]); garantias ACID; índices GIN para arrays; psycopg2 |
| BM25 (rank_bm25)                 | Dados        | Busca lexical                                                            | Precisão em termos jurídicos exatos: NR-15, CLT art. 193, LTCAT                              |
| Reciprocal Rank Fusion           | IA           | Combinação de rankings                                                   | Funde vector search + BM25 de forma objetiva e sem hiperparâmetros arbitrários               |
| pdfplumber                       | Backend      | Extração de texto de PDFs do usuário                                     | Biblioteca Python robusta para PDFs com texto selecionável                                   |
| Pydantic v2                      | Backend      | Validação de schemas e modelos de dados                                  | Integração nativa com FastAPI; garante consistência dos metadados                            |
| FastAPI + Uvicorn                | Backend      | API REST                                                                 | Framework Python async de alta performance; endpoints `/query`, `/enrich`, `/health`         |
| Next.js 14 (App Router)          | Frontend     | Interface web                                                            | Roteamento moderno, suporte nativo a upload, componentes React; deploy via Vercel            |

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

| Marco | Descrição                                                      | Prazo     |
| ----- | -------------------------------------------------------------- | --------- |
| M1    | Setup do ambiente + pipeline de ingestão dos acórdãos          | A definir |
| M2    | Extração de entidades via LLM + extração de provimento (regex) | A definir |
| M3    | Indexação no ChromaDB com SAC e Poly Vector                    | A definir |
| M4    | Busca híbrida (Chroma + BM25 + RRF)                            | A definir |
| M5    | Backend FastAPI + integração LLM                               | A definir |
| M6    | Frontend Next.js + interface completa                          | A definir |
| M7    | Validação com especialista + ajustes finais                    | A definir |

---

# 8. Referências

- **Acórdãos TST** — Fonte principal de dados do sistema. Coletados via scraping público do portal de jurisprudência do TST: [https://jurisprudencia.tst.jus.br](https://jurisprudencia.tst.jus.br/)
    
- **Iudicium Textum Dataset (ITD)** — UFPR. Base acadêmica de referência para NLP jurídico em português, utilizada como inspiração metodológica para estruturação do pipeline de ingestão. Contém 41.353 acórdãos do STF (2010–2018). Referência: SOUSA, A. W.; DEL FABRO, M. D. Iudicium Textum Dataset: Uma Base de Textos Jurídicos para NLP. In: 34º SBBD. SBC, 2019. Acesso: [https://dadosabertos.c3sl.ufpr.br/acordaos](https://dadosabertos.c3sl.ufpr.br/acordaos)
    
- **SAC — Summary-Augmented Chunking** [https://arxiv.org/html/2510.06999](https://arxiv.org/html/2510.06999)
    
- **LangChain**: [https://python.langchain.com](https://python.langchain.com/)
    
- **ChromaDB**: [https://www.trychroma.com](https://www.trychroma.com/)

- **PostgreSQL**: [https://www.postgresql.org](https://www.postgresql.org/) — banco relacional open-source; driver Python via [psycopg2](https://pypi.org/project/psycopg2/) ou [asyncpg](https://pypi.org/project/asyncpg/) para integração com FastAPI async

- **Poly-Vector**: [https://arxiv.org/abs/2504.10508](https://arxiv.org/abs/2504.10508)
    

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
