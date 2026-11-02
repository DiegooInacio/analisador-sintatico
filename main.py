"""Interface de linha de comando, sem dependências externas (Python 3.10+)."""
import argparse
from pathlib import Path
import sys

from grammar import Grammar, production
from parser import PredictiveParser, tokenize


def table(headers, rows):
    rows = [tuple(map(str, row)) for row in rows]
    widths = [max(len(header), *(len(row[i]) for row in rows)) if rows else len(header)
              for i, header in enumerate(headers)]
    def line(row):
        return " | ".join(cell.ljust(width) for cell, width in zip(row, widths))
    return "\n".join([line(headers), "-+-".join("-" * w for w in widths)] + [line(row) for row in rows])


def theory_report(grammar):
    sections = ["GRAMÁTICA", *[production(lhs, rhs) for lhs, rules in grammar.productions.items() for rhs in rules]]
    sections += ["\nCONJUNTOS FIRST E FOLLOW", table(
        ("Não-terminal", "FIRST", "FOLLOW"),
        [(nt, "{ " + ", ".join(sorted(grammar.first[nt])) + " }",
          "{ " + ", ".join(sorted(grammar.follow[nt])) + " }") for nt in grammar.productions])]
    sections += ["\nTABELA PREDITIVA M (células preenchidas; demais células = erro)", table(
        ("Não-terminal", "Entrada", "Produção"),
        [(nt, terminal, production(nt, grammar.table[nt, terminal]))
         for nt in grammar.productions for terminal in sorted(grammar.terminals)
         if (nt, terminal) in grammar.table])]
    return "\n".join(sections)


def main(argv=None):
    cli = argparse.ArgumentParser(description="Analisador sintático Java simplificado, manual e LL(1)")
    cli.add_argument("arquivo", type=Path, help="código-fonte .java")
    cli.add_argument("--gramatica", type=Path, default=Path(__file__).with_name("gramatica.txt"))
    cli.add_argument("--recuperar", action="store_true", help="ativar recuperação em modo pânico")
    cli.add_argument("--arvore", action="store_true", help="exibir árvore em pré-ordem")
    cli.add_argument("--tokens", action="store_true", help="exibir tokens e sua adaptação para a gramática")
    cli.add_argument("--sem-teoria", action="store_true", help="omitir FIRST, FOLLOW e M")
    cli.add_argument("--sem-trace", action="store_true", help="omitir rastreamento")
    cli.add_argument("--saida", type=Path, help="salvar relatório UTF-8 em arquivo")
    args = cli.parse_args(argv)
    if args.arquivo.suffix.lower() != ".java":
        cli.error("a entrada deve possuir extensão .java")
    try:
        grammar = Grammar.from_file(args.gramatica)
        source = args.arquivo.read_text(encoding="utf-8")
    except (OSError, ValueError) as error:
        cli.error(str(error))
    sections = [f"Arquivo: {args.arquivo}"]
    if not args.sem_teoria:
        sections.append(theory_report(grammar))
    tokens, lexical_errors = tokenize(source)
    if args.tokens:
        sections += ["\nTOKENS", table(("Linha", "Coluna", "Tipo léxico", "Lexema", "Terminal"),
                     [(t.token.linha, t.token.coluna, t.token.tipo, repr(t.token.lexema), t.symbol) for t in tokens])]
    if lexical_errors:
        sections.append("\nANÁLISE INTERROMPIDA: erro(s) léxico(s)")
        sections.extend(f"Linha {t.linha}, coluna {t.coluna}: {t.lexema!r}: {t.atributo}" for t in lexical_errors)
        sections.append("Veredito: programa rejeitado por erro léxico; análise sintática não executada.")
        accepted = False
    else:
        result = PredictiveParser(grammar).parse(tokens, recover=args.recuperar)
        if not args.sem_trace:
            sections += ["\nTRACE (pilha: base à esquerda, topo à direita; estado ANTES da ação)",
                         table(("Passo", "Pilha", "Entrada", "Ação"),
                               [(s.number, s.stack, s.remaining, s.action) for s in result.trace])]
        if args.arvore:
            sections += ["\nÁRVORE DE DERIVAÇÃO EM PRÉ-ORDEM" + (" (parcial/recuperada)" if result.errors else ""),
                         *result.tree.preorder()]
        sections += ["\nERROS SINTÁTICOS", *(result.errors or ["Nenhum."])]
        accepted = result.accepted
        sections.append("\nVeredito: Aceito com Sucesso." if accepted
                        else f"\nVeredito: programa rejeitado; {len(result.errors)} erro(s) sintático(s).")
    report = "\n".join(sections) + "\n"
    if args.saida:
        try:
            args.saida.write_text(report, encoding="utf-8")
        except OSError as error:
            cli.error(f"não foi possível salvar o relatório: {error}")
        print(f"Relatório salvo em {args.saida}")
        print(sections[-1].strip())
    else:
        print(report, end="")
    return 0 if accepted else 1


if __name__ == "__main__":
    sys.exit(main())
