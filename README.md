# Analisador sintático LL(1) manual para Java simplificado

Trabalho Prático de Compiladores, implementado em **Python 3.10 ou superior**, sem
bibliotecas externas e sem geradores de analisadores. Reconhece exatamente o
subconjunto de Java definido em `gramatica.txt`.

## Executar

Na pasta deste projeto:

```bash
python3 main.py exemplos/Exemplo1_Sucesso.java
```

A execução padrão exibe a gramática, FIRST e FOLLOW de todos os 15 não-terminais,
a tabela M, o trace completo (Pilha, Entrada e Ação), os erros e o veredito.
A tabela usa uma linha por célula preenchida `M[não-terminal, terminal]`;
todas as demais células são erros. A produção `ε` é diferente de uma célula vazia.

```bash
# Mostrar integração com o léxico e árvore de derivação em pré-ordem
python3 main.py exemplos/Exemplo1_Sucesso.java --tokens --arvore

# Dois erros exigidos pelo enunciado: parar no primeiro erro
python3 main.py exemplos/Exemplo2_ErroTabela.java --sem-teoria
python3 main.py exemplos/Exemplo3_ErroPilha.java --sem-teoria

# Encontrar vários erros e continuar até o final
python3 main.py exemplos/Exemplo4_MultiplosErros.java --recuperar --sem-teoria

# Verificar o tratamento separado de erros léxicos
python3 main.py exemplos/Exemplo5_ErroLexico.java --tokens --sem-teoria

# Salvar um relatório completo, sem uma tabela larga no terminal
python3 main.py exemplos/Exemplo1_Sucesso.java --arvore --saida docs/relatorio_sucesso.txt

# Executar as verificações automatizadas
python3 -m unittest discover -s tests -v
```

`--sem-trace` omite o trace, `--sem-teoria` omite a parte teórica e
`--gramatica caminho.txt` permite carregar outra gramática no mesmo formato.
O adaptador de tokens continua específico do léxico Java do Trabalho 1.
Os códigos de saída são 0 para aceitação, 1 para rejeição léxica ou sintática
e 2 para problemas de argumentos, arquivos ou gramática.

## Arquivos e funcionamento

| Arquivo | Responsabilidade |
| --- | --- |
| `lexer.py` | Cópia integral de `../atvd1/lexer.py`, desenvolvido no Trabalho 1; preserva sua implementação manual e os dois buffers. |
| `gramatica.txt` | Todas as produções do enunciado, lidas em tempo de execução. |
| `grammar.py` | Leitura da gramática, cálculo iterativo de FIRST/FOLLOW e construção da tabela, com detecção de conflitos LL(1). |
| `parser.py` | Adaptação dos tokens, algoritmo de pilha dirigido por M, diagnóstico, recuperação e árvore. |
| `main.py` | Interface de linha de comando e formatação dos relatórios. |
| `exemplos/` | Os três exemplos obrigatórios e dois exemplos adicionais. |
| `tests/test_analisador.py` | Validação dos conjuntos, exemplos, erros, recuperação, adaptação e conflitos. |
| `docs/fundamentos.txt` | Gramática, FIRST, FOLLOW e tabela M calculados pelo código. |

### Integração léxica

O programa chama `Lexer(source).analyze()` e recebe os objetos `Token` do Trabalho 1,
com tipo, lexema, atributo, linha e coluna. `IDENTIFICADOR` torna-se `id`, enquanto
`LITERAL_INTEIRO` e `LITERAL_REAL` tornam-se `num`. Palavras-chave, operadores e
delimitadores são desambiguados por seus lexemas, pois o léxico usa categorias
genéricas como `PALAVRA_CHAVE` e `OPERADOR_RELACIONAL`.

Assim, `TesteSucesso`, `main` e `resultado` viram `id`; `10` e `2.5` viram `num`.
Este léxico já classifica `main` como identificador, dispensando mudar a gramática.
Comentários e espaços são ignorados pelo léxico. Tokens de erro são reportados
antes da análise sintática. O adaptador também rejeita NUL no código-fonte,
pois esse caractere é a sentinela interna do leitor do Trabalho 1.

### FIRST, FOLLOW e tabela M

Os conjuntos começam vazios. FIRST é atualizado até não ocorrer mais nenhuma
mudança: para cada sequência, acrescentam-se os símbolos iniciais possíveis,
avançando pelo próximo símbolo se o anterior puder produzir ε. Se todos puderem
produzir vazio, acrescenta-se ε.

FOLLOW(PROG) começa com `$`. Para cada ocorrência `A → α B β`, acrescenta-se
`FIRST(β) − {ε}` a FOLLOW(B). Se β for vazio ou anulável, acrescenta-se FOLLOW(A).
Repete-se até estabilizar. ε nunca pertence a FOLLOW.

Para cada produção `A → α`, insere-se essa produção em `M[A, a]` para cada
`a ∈ FIRST(α) − {ε}`. Se α for anulável, insere-se também em cada coluna de FOLLOW(A).
Duas produções distintas na mesma célula causam um diagnóstico de conflito LL(1),
em vez de uma sobrescrita silenciosa. A tabela é um dicionário Python indexado
por tuplas `(não_terminal, terminal)`; a produção vazia é a tupla `()`.

### Algoritmo da pilha

1. Acrescentar `$` aos tokens e iniciar a pilha com `$ PROG`.
2. Se o topo for terminal e igual à entrada, desempilhar e consumir o token.
3. Se o topo for não-terminal, consultar M com o próximo terminal da entrada.
   Substituir o topo pelo lado direito da produção **em ordem inversa** para
   processar primeiro o símbolo à esquerda. Para ε, apenas remover o topo.
4. Se a célula não existir ou o terminal for diferente do esperado, comunicar o erro.
5. Aceitar somente após casar `$` com `$`, esvaziar a pilha, consumir toda a entrada
   e terminar sem nenhum erro.

O trace registra o estado **antes** de cada ação; a base da pilha fica à esquerda
e o topo à direita. Por isso a última linha de uma aceitação mostra pilha `$`,
entrada `$` e a ação que esvazia a pilha. Os tokens normalizados aparecem na entrada;
os lexemas originais e sua localização aparecem nas ações e nos diagnósticos.

Cada expansão cria os filhos do nó correspondente na árvore. ε é um filho
explícito e os terminais casados guardam o lexema. A impressão usa uma travessia
iterativa em pré-ordem. Em programas inválidos a árvore é parcial; nós removidos
ou terminais inseridos pela recuperação são marcados como recuperados.

### Recuperação opcional

Sem `--recuperar`, o analisador para no primeiro erro, reproduzindo os exemplos
do enunciado. Com a opção, uma célula vazia ativa o modo pânico: a entrada avança
até FIRST ou FOLLOW do não-terminal, `;`, `}` ou `$`. Se o símbolo encontrado
permitir uma produção, o analisador retoma por ela; caso contrário, remove o
não-terminal da pilha para preservar o delimitador para quem o espera.

Na incompatibilidade de terminal, o analisador remove o terminal esperado da
pilha e registra uma inserção virtual, sem consumir o próximo token. Após chegar
ao `$` da pilha, tokens excedentes são descartados. Cada recuperação consome
entrada ou reduz a pilha, garantindo progresso. A recuperação pode causar erros
em cascata; chegar ao final depois de um erro **não** torna o programa válido.

## Resultados esperados

| Exemplo | Resultado |
| --- | --- |
| `Exemplo1_Sucesso.java` | Aceito com Sucesso, após casar `$` com `$`. |
| `Exemplo2_ErroTabela.java` | Linha 7, coluna 18: `M[T, )]` vazia, esperando `(`, `id` ou `num`. |
| `Exemplo3_ErroPilha.java` | Linha 6, coluna 20: encontrado `;`, esperando `)` no topo. |
| `Exemplo4_MultiplosErros.java` com `--recuperar` | Três erros; ainda reconhece `a = 7;` e chega ao final. Programa rejeitado. |
| `Exemplo5_ErroLexico.java` | Erro léxico em `@`; análise sintática não executada. |

