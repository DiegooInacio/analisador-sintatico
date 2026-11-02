from dataclasses import dataclass, field

from grammar import EOF, EPSILON, Grammar, production
from lexer import Lexer, Token


@dataclass
class InputToken:
    symbol: str
    token: Token


def tokenize(source: str):
    raw = Lexer(source).analyze()
    if "\0" in source:
        offset = source.index("\0")
        line = source.count("\n", 0, offset) + 1
        column = offset - source.rfind("\n", 0, offset)
        raw.append(Token("ERROR", "\0", "caractere NUL no código-fonte", line, column))
    errors = [t for t in raw if t.tipo == "ERROR"]
    mapped = []
    for token in raw:
        if token.tipo == "IDENTIFICADOR":
            symbol = "id"
        elif token.tipo in ("LITERAL_INTEIRO", "LITERAL_REAL"):
            symbol = "num"
        elif token.tipo == "PALAVRA_CHAVE" or token.tipo.startswith("OPERADOR_") or token.tipo == "DELIMITADOR":
            symbol = token.lexema
        else:
            symbol = token.tipo  # strings/caracteres não se tornam id ou num
        mapped.append(InputToken(symbol, token))
    line = source.count("\n") + 1
    column = len(source.rsplit("\n", 1)[-1]) + 1
    mapped.append(InputToken(EOF, Token("EOF", EOF, None, line, column)))
    return mapped, errors


@dataclass
class Node:
    symbol: str
    lexeme: str | None = None
    children: list = field(default_factory=list)
    recovered: bool = False

    def preorder(self):
        pending = [(self, 0)]
        while pending:
            node, depth = pending.pop()
            label = node.symbol
            if node.lexeme is not None:
                label += f" ({node.lexeme!r})"
            if node.recovered:
                label += " [recuperado]"
            yield "  " * depth + label
            pending.extend((child, depth + 1) for child in reversed(node.children))


@dataclass
class Step:
    number: int
    stack: str
    remaining: str
    action: str


@dataclass
class ParseResult:
    accepted: bool
    errors: list[str]
    trace: list[Step]
    tree: Node


class PredictiveParser:
    def __init__(self, grammar: Grammar):
        self.grammar = grammar

    def parse(self, tokens: list[InputToken], recover=False):
        if not tokens or tokens[-1].symbol != EOF or any(t.symbol == EOF for t in tokens[:-1]):
            raise ValueError("A entrada deve conter exatamente um $ ao final")
        grammar = self.grammar
        root = Node(grammar.start)
        stack = [(EOF, None), (grammar.start, root)]
        index = 0
        errors, trace = [], []

        def record(action):
            trace.append(Step(len(trace) + 1, " ".join(s for s, _ in stack),
                              " ".join(t.symbol for t in tokens[index:]), action))

        while stack:
            top, node = stack[-1]
            current = tokens[index]
            lookahead = current.symbol
            token = current.token
            if top in grammar.productions:
                rhs = grammar.table.get((top, lookahead))
                if rhs is not None:  # () é uma produção ε válida
                    record(production(top, rhs))
                    stack.pop()
                    node.children = [Node(s) for s in rhs] if rhs else [Node(EPSILON)]
                    stack.extend((child.symbol, child) for child in reversed(node.children) if child.symbol != EPSILON)
                    continue
                expected = sorted(t for nt, t in grammar.table if nt == top)
                message = (f"Erro Sintático na Tabela M[{top}, {lookahead}]: token {token.lexema!r} "
                           f"inesperado; esperava-se {', '.join(repr(t) for t in expected)} para derivar {top}")
            elif top == lookahead:
                record("Casar $ com $; pilha vazia; reconhecimento concluído" if top == EOF
                       else f"Casar {top!r} com {token.lexema!r}")
                stack.pop()
                if node is not None:
                    node.lexeme = token.lexema
                index += 1
                continue
            else:
                message = (f"Erro Sintático no topo da pilha: encontrado {token.lexema!r}, "
                           f"mas esperava-se {top!r} no topo da pilha")

            message = f"Linha {token.linha}, coluna {token.coluna}: {message}"
            errors.append(message)
            if not recover:
                record(message)
                break

            if top in grammar.productions:
                sync = grammar.first[top] | grammar.follow[top] | {";", "}", EOF}
                end = index
                while tokens[end].symbol not in sync:
                    end += 1
                resume = tokens[end].symbol
                if end > index:
                    record(message + f"; pânico: descartar {end - index} token(s)")
                    index = end
                else:
                    record(message + f"; pânico: remover {top} da pilha")
                if (top, resume) not in grammar.table:
                    stack.pop()
                    node.recovered = True
            elif top == EOF:
                record(message + "; pânico: descartar token excedente")
                index += 1
            else:
                record(message + f"; recuperação: inserir {top!r} ausente")
                stack.pop()
                node.recovered = True

        return ParseResult(not errors and not stack and index == len(tokens), errors, trace, root)
