# Motivação e contexto das principais decisões

## Por que criamos esse projeto

- **Reduzir reconciliação manual**: a conciliação entre o relatório Odontotech e os lançamentos bancários era feita manualmente em planilhas, demandando tempo e sujeita a erros de transcrição.  
- **Padronizar o processo**: havia variação na forma como cada pessoa limpava o CSV (colunas com nomes diferentes, datas sem padrão, valores com vírgulas). Centralizamos a lógica em `odontotech.py` para garantir consistência.  
- **Disponibilizar visão em tempo real**: com Streamlit, qualquer pessoa da equipe consegue carregar um arquivo e obter relatórios na hora, sem precisar de um analista de dados dedicado.

## Decisões de destaque

- **Dois aplicativos separados**  
  - `app.py`: foco no fluxo Odontotech → contabilidade/OFX.  
  - `main.py`: visualizador genérico para outros relatórios e OFX.  
  - Motivação: manter o app principal enxuto para o uso diário, mas preservar ferramentas auxiliares para investigações pontuais.

- **Normalização agressiva de colunas**  
  - O Odontotech muda frequentemente o nome das colunas ou entrega arquivos com acentuação inconsistente. Criamos o dicionário `CANONICAL_COLUMNS` para absorver essas diferenças e evitar quebras no front.

- **Filtros com state compartilhado**  
  - Mantemos a seleção (dia/semana/mês/período e bancos) na `session_state` para que as abas compartilhem o mesmo contexto. Assim, o usuário filtra uma vez e todas as visões (dados limpos, relatórios, comparação OFX) refletem a escolha.

- **Exportações completas**  
  - CSV limpo: necessidade básica para enviar dados corrigidos a parceiros.  
  - Excel com abas: solicitação da contabilidade para ter resumos prontos por data/classe/banco.  
  - PDF com resumo: pensado para apresentações e armazenamento em DMS.  
  - Arquivos contábeis (`conciliacao_contabil.csv`): atende layout padrão dos sistemas usados pelo financeiro.

- **Matching OFX por data + valor**  
  - Decisão tomada após testes: o `FITID` nem sempre estava presente ou confiável nos OFX fornecidos. Optamos por data + valor arredondado e controle de duplicidades com `cumcount`, que cobriu os casos conhecidos sem introduzir chaves artificiais.

- **Remoção das abas fixas por agrupamento**  
  - O histórico incluía abas dedicadas (“Por CLASSE”, “Por banco”). Depois de feedback dos usuários, consolidamos tudo no agrupamento livre e adicionamos downloads equivalentes. Resultado: interface mais simples e menos código duplicado.

## Benefícios observados

- Geração de relatórios contábeis e conciliação bancária em minutos.  
- Redução de inconsistências nos totais por conta de padronização automática de datas/valores.  
- Facilidade para auditar filtros e decisões (os arquivos de download acompanham os campos utilizados nos cálculos).  
- Equipe financeira consegue operar sem depender da equipe de tecnologia, apenas com acompanhamento pontual para ajustes de regra.

