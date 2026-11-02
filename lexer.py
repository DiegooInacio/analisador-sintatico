from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass
from typing import Any, Iterator


KEYWORDS = frozenset(
    {
        "abstract", "assert", "boolean", "break", "byte", "case", "catch",
        "char", "class", "const", "continue", "default", "do", "double",
        "else", "enum", "extends", "final", "finally", "float", "for",
        "goto", "if", "implements", "import", "instanceof", "int",
        "interface", "long", "new", "package", "private", "protected",
        "public", "return", "short", "static", "strictfp", "super",
        "switch", "synchronized", "this", "throw", "throws", "transient",
        "try", "void", "volatile", "while",
    }
)

BOOLEAN_NULL_LITERALS = frozenset({"true", "false", "null"})

OPERATORS = {
    ">>>=": "OPERADOR_ATRIBUICAO",
    "<<=": "OPERADOR_ATRIBUICAO",
    ">>=": "OPERADOR_ATRIBUICAO",
    "==": "OPERADOR_RELACIONAL",
    "!=": "OPERADOR_RELACIONAL",
    "<=": "OPERADOR_RELACIONAL",
    ">=": "OPERADOR_RELACIONAL",
    "&&": "OPERADOR_LOGICO",
    "||": "OPERADOR_LOGICO",
    "++": "OPERADOR_INCREMENTO",
    "--": "OPERADOR_DECREMENTO",
    "+=": "OPERADOR_ATRIBUICAO",
    "-=": "OPERADOR_ATRIBUICAO",
    "*=": "OPERADOR_ATRIBUICAO",
    "/=": "OPERADOR_ATRIBUICAO",
    "%=": "OPERADOR_ATRIBUICAO",
    "&=": "OPERADOR_ATRIBUICAO",
    "|=": "OPERADOR_ATRIBUICAO",
    "^=": "OPERADOR_ATRIBUICAO",
    "<<": "OPERADOR_DESLOCAMENTO",
    ">>": "OPERADOR_DESLOCAMENTO",
    ">>>": "OPERADOR_DESLOCAMENTO",
    "+": "OPERADOR_ARITMETICO",
    "-": "OPERADOR_ARITMETICO",
    "*": "OPERADOR_ARITMETICO",
    "/": "OPERADOR_ARITMETICO",
    "%": "OPERADOR_ARITMETICO",
    "<": "OPERADOR_RELACIONAL",
    ">": "OPERADOR_RELACIONAL",
    "!": "OPERADOR_LOGICO",
    "=": "OPERADOR_ATRIBUICAO",
}

DELIMITERS = {
    ";": "DELIMITADOR",
    ",": "DELIMITADOR",
    ".": "DELIMITADOR",
    "(": "DELIMITADOR",
    ")": "DELIMITADOR",
    "{": "DELIMITADOR",
    "}": "DELIMITADOR",
    "[": "DELIMITADOR",
    "]": "DELIMITADOR",
    ":": "DELIMITADOR",
    "?": "DELIMITADOR",
}

OPERATOR_STARTS = frozenset(operator[0] for operator in OPERATORS)
SORTED_OPERATORS = tuple(sorted(OPERATORS, key=len, reverse=True))
ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "b": "\b", "f": "\f", "\\": "\\", "'": "'", '"': '"'}


@dataclass(frozen=True)
class Token:
    tipo: str
    lexema: str
    atributo: Any | None
    linha: int
    coluna: int


class TwoBufferReader:

    SENTINEL = "\0"

    def __init__(self, source: str, buffer_size: int = 64) -> None:
        if buffer_size < 2:
            raise ValueError("buffer_size deve ser pelo menos 2")
        self.source = source
        self.buffer_size = buffer_size
        self.begin = 0
        self.forward = 0
        self._next_load_offset = 0
        self._buffers = ["", ""]
        self._starts = [0, 0]
        self._active = 0
        self._load(0)
        self._load(1)
        self._line_starts = [0]
        self._line_starts.extend(index + 1 for index, char in enumerate(source) if char == "\n")

    @property
    def buffer_atual(self) -> int:
        return self._active

    @property
    def indice_no_buffer(self) -> int:
        return self.forward - self._starts[self._active]

    def _load(self, slot: int) -> None:
        start = self._next_load_offset
        chunk = self.source[start : start + self.buffer_size]
        self._starts[slot] = start
        self._buffers[slot] = chunk + self.SENTINEL
        self._next_load_offset += len(chunk)

    def _slot_for(self, position: int) -> int | None:
        for slot, start in enumerate(self._starts):
            length = len(self._buffers[slot]) - 1
            if start <= position < start + length:
                return slot
        return None

    def _ensure_forward_buffer(self) -> None:
        if self.forward >= len(self.source):
            return
        slot = self._slot_for(self.forward)
        if slot is not None:
            self._active = slot
            return

        replacement = 1 - self._active
        self._load(replacement)
        self._active = replacement

    def peek(self, distance: int = 0) -> str:
        position = self.forward + distance
        if position >= len(self.source):
            return self.SENTINEL
        slot = self._slot_for(position)
        if slot is None and position >= self._next_load_offset:
            self._load(1 - self._active)
            slot = self._slot_for(position)
        if slot is not None:
            return self._buffers[slot][position - self._starts[slot]]
        return self.source[position]

    def advance(self) -> str:
        char = self.peek()
        if char == self.SENTINEL:
            return char
        self.forward += 1
        self._ensure_forward_buffer()
        return char

    def retract(self, amount: int = 1) -> None:
        self.forward = max(self.begin, self.forward - amount)
        slot = self._slot_for(self.forward)
        if slot is not None:
            self._active = slot

    def start_lexeme(self) -> None:
        self.begin = self.forward

    def lexeme(self) -> str:
        return self.source[self.begin : self.forward]

    def position(self, offset: int | None = None) -> tuple[int, int]:
        target = self.begin if offset is None else offset
        line_index = bisect_right(self._line_starts, target) - 1
        return line_index + 1, target - self._line_starts[line_index] + 1


class Lexer:

    def __init__(self, source: str, buffer_size: int = 64) -> None:
        self.reader = TwoBufferReader(source, buffer_size)
        self.symbols: dict[str, int] = {}
        self._occurrences: Counter[str] = Counter()

    @staticmethod
    def _is_identifier_start(char: str) -> bool:
        return char.isascii() and (char.isalpha() or char == "_")

    @staticmethod
    def _is_identifier_part(char: str) -> bool:
        return char.isascii() and (char.isalnum() or char == "_")

    def _emit(self, tipo: str, atributo: Any | None = None) -> Token:
        line, column = self.reader.position()
        return Token(tipo, self.reader.lexeme(), atributo, line, column)

    def _identifier_or_keyword(self) -> Token:
        while self._is_identifier_part(self.reader.peek()):
            self.reader.advance()
        lexeme = self.reader.lexeme()
        if lexeme in KEYWORDS:
            return self._emit("PALAVRA_CHAVE")
        if lexeme in BOOLEAN_NULL_LITERALS:
            value = {"true": True, "false": False, "null": None}[lexeme]
            return self._emit("LITERAL_BOOLEANO_NULO", value)
        if lexeme not in self.symbols:
            self.symbols[lexeme] = len(self.symbols) + 1
        self._occurrences[lexeme] += 1
        return self._emit("IDENTIFICADOR", self.symbols[lexeme])

    def _number(self) -> Token:
        while self.reader.peek().isdigit():
            self.reader.advance()

        if self.reader.peek() == "," and self.reader.peek(1).isdigit():
            self.reader.advance()
            while self.reader.peek().isdigit():
                self.reader.advance()
            return self._emit("ERROR", "vírgula não é separador decimal; use ponto")

        if self._is_identifier_start(self.reader.peek()):
            while self._is_identifier_part(self.reader.peek()):
                self.reader.advance()
            return self._emit("ERROR", "identificador não pode iniciar com número")

        if self.reader.peek() == ".":
            self.reader.advance()
            if not self.reader.peek().isdigit():
                return self._emit("ERROR", "real malformado: faltam dígitos após o ponto")
            while self.reader.peek().isdigit():
                self.reader.advance()
            if self._is_identifier_start(self.reader.peek()):
                while self._is_identifier_part(self.reader.peek()):
                    self.reader.advance()
                return self._emit("ERROR", "literal numérico malformado")
            lexeme = self.reader.lexeme()
            return self._emit("LITERAL_REAL", float(lexeme))

        lexeme = self.reader.lexeme()
        return self._emit("LITERAL_INTEIRO", int(lexeme))

    def _string(self) -> Token:
        self.reader.advance()  
        decoded: list[str] = []
        while True:
            char = self.reader.peek()
            if char == self.reader.SENTINEL or char in "\r\n":
                return self._emit("ERROR", "string não terminada")
            if char == '"':
                self.reader.advance()
                return self._emit("LITERAL_STRING", "".join(decoded))
            if char == "\\":
                self.reader.advance()
                escape = self.reader.peek()
                if escape not in ESCAPES:
                    if escape != self.reader.SENTINEL:
                        self.reader.advance()
                    return self._emit("ERROR", "sequência de escape inválida")
                decoded.append(ESCAPES[escape])
                self.reader.advance()
                continue
            decoded.append(char)
            self.reader.advance()

    def _character(self) -> Token:
        self.reader.advance()  
        char = self.reader.peek()
        if char == self.reader.SENTINEL or char in "\r\n":
            return self._emit("ERROR", "literal de caractere não terminado")
        if char == "\\":
            self.reader.advance()
            escape = self.reader.peek()
            if escape not in ESCAPES:
                if escape != self.reader.SENTINEL:
                    self.reader.advance()
                return self._consume_invalid_character("sequência de escape inválida")
            value = ESCAPES[escape]
            self.reader.advance()
        elif char == "'":
            self.reader.advance()
            return self._emit("ERROR", "literal de caractere vazio")
        else:
            value = char
            self.reader.advance()

        if self.reader.peek() != "'":
            return self._consume_invalid_character("literal de caractere deve conter um único caractere")
        self.reader.advance()
        return self._emit("LITERAL_CARACTERE", value)

    def _consume_invalid_character(self, reason: str) -> Token:
        while self.reader.peek() not in ("'", "\r", "\n", self.reader.SENTINEL):
            self.reader.advance()
        if self.reader.peek() == "'":
            self.reader.advance()
        return self._emit("ERROR", reason)

    def _comment_or_slash(self) -> Token | None:
        if self.reader.peek(1) == "/":
            self.reader.advance()
            self.reader.advance()
            while self.reader.peek() not in ("\r", "\n", self.reader.SENTINEL):
                self.reader.advance()
            return None
        if self.reader.peek(1) == "*":
            self.reader.advance()
            self.reader.advance()
            while True:
                if self.reader.peek() == self.reader.SENTINEL:
                    return self._emit("ERROR", "comentário de bloco não terminado")
                if self.reader.peek() == "*" and self.reader.peek(1) == "/":
                    self.reader.advance()
                    self.reader.advance()
                    return None
                self.reader.advance()
        return self._operator()

    def _operator(self) -> Token:
        for operator in SORTED_OPERATORS:
            if all(self.reader.peek(index) == char for index, char in enumerate(operator)):
                for _ in operator:
                    self.reader.advance()
                return self._emit(OPERATORS[operator])
        self.reader.advance()
        return self._emit("ERROR", "operador inválido ou incompleto")

    def tokens(self) -> Iterator[Token]:
        while self.reader.peek() != self.reader.SENTINEL:
            while self.reader.peek().isspace():
                self.reader.advance()
            if self.reader.peek() == self.reader.SENTINEL:
                break

            self.reader.start_lexeme()
            char = self.reader.peek()
            if self._is_identifier_start(char):
                yield self._identifier_or_keyword()
            elif char.isdigit():
                yield self._number()
            elif char == '"':
                yield self._string()
            elif char == "'":
                yield self._character()
            elif char == "/":
                token = self._comment_or_slash()
                if token is not None:
                    yield token
            elif char in OPERATOR_STARTS or char in "&|^":
                yield self._operator()
            elif char in DELIMITERS:
                self.reader.advance()
                yield self._emit(DELIMITERS[char])
            else:
                self.reader.advance()
                yield self._emit("ERROR", "caractere desconhecido")

    def analyze(self) -> list[Token]:
        return list(self.tokens())

    @property
    def symbol_table(self) -> list[tuple[int, str, int]]:
        return [(index, name, self._occurrences[name]) for name, index in self.symbols.items()]
