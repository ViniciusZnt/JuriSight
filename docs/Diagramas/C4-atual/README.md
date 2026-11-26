# Diagramas C4 — arquitetura atual

Fontes em C4-PlantUML (`.puml`) e imagens geradas (`.svg`) da arquitetura como está hoje.
Seguem o padrão visual dos diagramas da proposta, na pasta acima, que ficam como registro da
arquitetura da RFC. Explicação de cada diagrama na Wiki, página
[Arquitetura](https://github.com/ViniciusZnt/JuriSight/wiki/Arquitetura).

| Arquivo | Diagrama |
|---|---|
| `C4-Nivel1-Contexto` | Nível 1: contexto |
| `C4-Nivel2-Containers` | Nível 2: containers |
| `C4-Nivel3-Backend` | Nível 3: Backend API |
| `C4-Nivel3-Frontend` | Nível 3: Frontend |
| `C4-Nivel3-Pipeline-Ingestao` | Nível 3: Pipeline de Ingestão |
| `C4-Nivel3-Pipeline-Provimento` | Nível 3: Pipeline de Filtros e Provimento |
| `C4-Implantacao` | Implantação em produção |

Para gerar o SVG de novo: abra o `.puml` na extensão PlantUML do VS Code e exporte, ou use
`java -jar plantuml.jar -tsvg <arquivo>.puml` (precisa do Graphviz).
