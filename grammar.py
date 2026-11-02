"""Cálculo por ponto fixo de FIRST/FOLLOW e construção manual da tabela LL(1)."""
from pathlib import Path

EPSILON = "ε"
EOF = "$"


class Grammar:
    def __init__(self, text: str):
        self.productions: dict[str, list[tuple[str, ...]]] = {}
        for line_number, raw in enumerate(text.splitlines(), 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            if "->" not in line:
                raise ValueError(f"Produção inválida na linha {line_number}")
            lhs, rhs = map(str.strip, line.split("->", 1))
            if not lhs or len(lhs.split()) != 1 or lhs in (EPSILON, EOF):
                raise ValueError(f"Não-terminal inválido: {lhs!r}")
            for alternative in rhs.split("|"):
                symbols = tuple(alternative.split())
                if not symbols or (EPSILON in symbols and symbols != (EPSILON,)) or EOF in symbols:
                    raise ValueError(f"Produção inválida na linha {line_number}: use ε para vazio")
                self.productions.setdefault(lhs, []).append(() if symbols == (EPSILON,) else symbols)
        if not self.productions:
            raise ValueError("Gramática vazia")
        self.start = next(iter(self.productions))
        self.terminals = {s for rules in self.productions.values() for rhs in rules
                          for s in rhs if s not in self.productions} | {EOF}
        self.first = {nt: set() for nt in self.productions}
        self.follow = {nt: set() for nt in self.productions}
        self._compute_first()
        self._compute_follow()
        self.table: dict[tuple[str, str], tuple[str, ...]] = {}
        self._build_table()

    @classmethod
    def from_file(cls, path: Path):
        return cls(path.read_text(encoding="utf-8"))

    def first_of(self, sequence):
        result = set()
        for symbol in sequence:
            current = self.first[symbol] if symbol in self.productions else {symbol}
            result.update(current - {EPSILON})
            if EPSILON not in current:
                break
        else:
            result.add(EPSILON)
        return result

    def _compute_first(self):
        changed = True
        while changed:
            changed = False
            for lhs, alternatives in self.productions.items():
                for rhs in alternatives:
                    before = len(self.first[lhs])
                    self.first[lhs].update(self.first_of(rhs))
                    changed |= len(self.first[lhs]) != before

    def _compute_follow(self):
        self.follow[self.start].add(EOF)
        changed = True
        while changed:
            changed = False
            for lhs, alternatives in self.productions.items():
                for rhs in alternatives:
                    for index, symbol in enumerate(rhs):
                        if symbol not in self.productions:
                            continue
                        suffix = self.first_of(rhs[index + 1:])
                        before = len(self.follow[symbol])
                        self.follow[symbol].update(suffix - {EPSILON})
                        if EPSILON in suffix:
                            self.follow[symbol].update(self.follow[lhs])
                        changed |= len(self.follow[symbol]) != before

    def _build_table(self):
        for lhs, alternatives in self.productions.items():
            for rhs in alternatives:
                first = self.first_of(rhs)
                lookaheads = first - {EPSILON}
                if EPSILON in first:
                    lookaheads |= self.follow[lhs]
                for terminal in sorted(lookaheads):
                    key = (lhs, terminal)
                    if key in self.table and self.table[key] != rhs:
                        raise ValueError(f"Conflito LL(1) em M[{lhs}, {terminal}]: "
                                         f"{self.table[key]} e {rhs}")
                    self.table[key] = rhs


def production(lhs, rhs):
    return f"{lhs} → {' '.join(rhs) if rhs else EPSILON}"
