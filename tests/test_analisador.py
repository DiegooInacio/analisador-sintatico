from pathlib import Path
import unittest

from grammar import EPSILON, Grammar
from parser import PredictiveParser, tokenize

ROOT = Path(__file__).resolve().parents[1]


class AnalyzerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.grammar = Grammar.from_file(ROOT / "gramatica.txt")
        cls.parser = PredictiveParser(cls.grammar)

    def analyze(self, source, recover=False):
        tokens, errors = tokenize(source)
        self.assertFalse(errors)
        return self.parser.parse(tokens, recover)

    def program(self, body):
        return "public class Teste { public static void main() { " + body + " } }"

    def test_first_and_follow_all_nonterminals(self):
        starts = {"int", "float", "char", "id", "if"}
        expressions = {"(", "id", "num"}
        relational = {"==", "!=", "<", ">"}
        end_expression = {";", ")"} | relational
        after_command = starts | {"}"}
        expected_first = {
            "PROG": {"public"}, "CMDS": starts | {EPSILON}, "CMD": starts,
            "DECL": {"int", "float", "char"}, "TIPO": {"int", "float", "char"},
            "ATRIB": {"id"}, "IF_STMT": {"if"}, "SENAO": {"else", EPSILON},
            "COND": expressions, "OP_REL": relational, "E": expressions,
            "E'": {"+", "-", EPSILON}, "T": expressions,
            "T'": {"*", "/", EPSILON}, "F": expressions,
        }
        expected_follow = {
            "PROG": {"$"}, "CMDS": {"}"}, "CMD": after_command,
            "DECL": after_command, "TIPO": {"id"}, "ATRIB": after_command,
            "IF_STMT": after_command, "SENAO": after_command,
            "COND": {")"}, "OP_REL": expressions,
            "E": end_expression, "E'": end_expression,
            "T": end_expression | {"+", "-"}, "T'": end_expression | {"+", "-"},
            "F": end_expression | {"+", "-", "*", "/"},
        }
        self.assertEqual(self.grammar.first, expected_first)
        self.assertEqual(self.grammar.follow, expected_follow)
        self.assertEqual(self.grammar.table["CMDS", "}"], ())
        self.assertNotIn(("T", ")"), self.grammar.table)

    def test_required_examples(self):
        result = self.analyze((ROOT / "exemplos/Exemplo1_Sucesso.java").read_text())
        self.assertTrue(result.accepted)
        self.assertEqual(result.trace[-1].stack, "$")
        self.assertEqual(result.trace[-1].remaining, "$")
        leaves, pending = [], [result.tree]
        while pending:
            node = pending.pop()
            if node.children:
                pending.extend(reversed(node.children))
            elif node.symbol != EPSILON:
                leaves.append(node.symbol)
        tokens, _ = tokenize((ROOT / "exemplos/Exemplo1_Sucesso.java").read_text())
        self.assertEqual(leaves, [t.symbol for t in tokens[:-1]])
        for name, message, token in [
            ("Exemplo2_ErroTabela.java", "Tabela M[T, )]", ")"),
            ("Exemplo3_ErroPilha.java", "esperava-se ')' no topo da pilha", ";"),
        ]:
            with self.subTest(name=name):
                result = self.analyze((ROOT / "exemplos" / name).read_text())
                self.assertFalse(result.accepted)
                self.assertEqual(len(result.errors), 1)
                self.assertIn(message, result.errors[0])
                self.assertEqual(result.trace[-1].remaining.split()[0], token)

    def test_accepted_constructs(self):
        for body in ["", "char c;", "a = 1;", "if (a == 1) {}", "if (a != 2) {} else {}",
                     "if (a < b) { if (a > 0) {} else {} }",
                     "a = 8 / 2 * (3 - 1) + 2.5;", "/* comentário */ int a; // fim\n"]:
            with self.subTest(body=body):
                self.assertTrue(self.analyze(self.program(body)).accepted)

    def test_rejected_constructs(self):
        for body in ["int = a;", "int a", "a = 1 + * 2;", "else {}", "a = ;",
                     "a = -1;", "a = 'c';", "a = \"texto\";", "if (a <= 2) {}",
                     "int a = 1;", "while (a > 1) {}"]:
            with self.subTest(body=body):
                self.assertFalse(self.analyze(self.program(body)).accepted)
        for source in ["", self.program("")[:-2], self.program("") + " int a;",
                       self.program("").replace("static void", "void static")]:
            self.assertFalse(self.analyze(source).accepted)

    def test_token_adapter_and_lexical_errors(self):
        tokens, errors = tokenize("Teste main variavel 10 2.5")
        self.assertFalse(errors)
        self.assertEqual([t.symbol for t in tokens], ["id", "id", "id", "num", "num", "$"])
        for source in [self.program("a = @;"), self.program("") + "\0 lixo", "/* aberto"]:
            self.assertTrue(tokenize(source)[1])

    def test_panic_reports_multiple_errors_and_finishes(self):
        source = (ROOT / "exemplos/Exemplo4_MultiplosErros.java").read_text()
        result = self.analyze(source, recover=True)
        self.assertFalse(result.accepted)
        self.assertEqual(len(result.errors), 3)
        self.assertIn("Casar $ com $", result.trace[-1].action)
        self.assertTrue(any("Casar 'num' com '7'" in s.action for s in result.trace))
        for source in ["", "else } ;", self.program("a ="), self.program("") + " else {}"]:
            with self.subTest(source=source):
                result = self.analyze(source, recover=True)
                self.assertFalse(result.accepted)
                self.assertIn("Casar $ com $", result.trace[-1].action)

    def test_dynamic_grammar_and_conflicts(self):
        grammar = Grammar("S -> A B\nA -> a | ε\nB -> b | ε")
        self.assertEqual(grammar.first["S"], {"a", "b", EPSILON})
        self.assertEqual(grammar.follow["A"], {"b", "$"})
        self.assertEqual(grammar.table["S", "$"], ("A", "B"))
        for text in ["S -> a A | a B\nA -> x\nB -> y", "S -> A a\nA -> a | ε"]:
            with self.assertRaisesRegex(ValueError, "Conflito LL"):
                Grammar(text)


if __name__ == "__main__":
    unittest.main()
