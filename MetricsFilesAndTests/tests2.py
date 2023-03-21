import plyj.parser as plyj
import plyj.model as m


def find_block(code, search_text):
    parser = plyj.Parser()
    tree = parser.parse_string(code)

    for decl in tree.type_declarations:
        if not isinstance(decl, m.ClassDeclaration):
            continue

        for method in decl.body:
            if not isinstance(method, m.MethodDeclaration):
                continue

            for stmt in method.body:
                block = find_block_helper(stmt, search_text)
                if block:
                    return block


def find_block_helper(stmt, search_text):
    if isinstance(stmt, m.TryStatement):
        block = find_block_helper(stmt.body, search_text)
        if block:
            return ('try', len(stmt.body))

        for catch in stmt.catch_clauses:
            block = find_block_helper(catch.body, search_text)
            if block:
                return ('catch', len(catch.body))

        if stmt.finally_block:
            block = find_block_helper(stmt.finally_block, search_text)
            if block:
                return ('finally', len(stmt.finally_block))

    elif isinstance(stmt, m.IfStatement):
        block = find_block_helper(stmt.then_statement, search_text)
        if block:
            return ('if', len(stmt.then_statement))

        if stmt.else_statement:
            block = find_block_helper(stmt.else_statement, search_text)
            if block:
                return ('else', len(stmt.else_statement))

    elif isinstance(stmt, m.SwitchStatement):
        for case in stmt.cases:
            block = find_block_helper(case.statements, search_text)
            if block:
                return ('switch', len(case.statements))

    elif isinstance(stmt, m.WhileStatement):
        block = find_block_helper(stmt.body, search_text)
        if block:
            return ('while', len(stmt.body))

    elif isinstance(stmt, m.ForStatement):
        block = find_block_helper(stmt.body, search_text)
        if block:
            return ('for', len(stmt.body))

    elif isinstance(stmt, m.Block):
        if search_text in stmt.to_source().lower():
            return ('block', len(stmt.statements))

        for sub_stmt in stmt.statements:
            block = find_block_helper(sub_stmt, search_text)
            if block:
                return block

    elif isinstance(stmt, m.MethodInvocation):
        if search_text in stmt.to_source().lower():
            return ('method', 1)

    return None
