import javalang
import ast
import re

def find_containing_block_and_type(source_code: str, text: str):
    # Type of statements we are looking for
    block_types = ['IfStatement',
                   'WhileStatement',
                   'DoStatement',
                   'ForStatement',
                   'TryStatement',
                   'SwitchStatement',
                   'MethodDeclaration',
                   'CatchClause',
                   'SynchronizedStatement']

    # Split the source code into lines
    lines = source_code.split("\n")
    texts = text.replace(' ', '').split('\\n')
    text_to_compare = texts[0]
    # Find the line number of the text
    line_number = None
    for i, line in enumerate(lines):
        line_to_compare = line.replace(' ', '')
        if text_to_compare in line_to_compare:
            line_number = i + 1
            break

    # Find the containing block and its type
    containing_block = None
    block_type = None
    exception_type = 'None'
    # block_line_count = 0
    node_line = 0
    if line_number is not None:
        # Parse the Java source code
        # print(text)
        try:
            tree = javalang.parse.parse(source_code)
        except (javalang.parser.JavaSyntaxError, ValueError):
            print(text)
        else:
            for path, node in tree:
                block_compare = type(node).__name__

                if block_compare in block_types:
                    if node.position is None:
                        node_line = node_line + 1
                    else:
                        node_line = node.position.line
                    if node_line >= line_number:
                        break
                    containing_block = node
                    block_type = type(node).__name__
                    exception_type = 'None'
                    if block_type == 'TryStatement':
                        if containing_block.catches is None:
                            exception_type = 'None'
                        else:
                            for catch in containing_block.catches:
                                for catch_type in catch.parameter.types:
                                    exception_type = ','.join(catch_type)
                    if block_type == 'CatchClause':
                        if containing_block.parameter.types is None:
                            exception_type = 'None'
                        else:
                            for catch_type in containing_block.parameter.types:
                                exception_type = ','.join(catch_type)

                    '''
                        block_line_count = len(containing_block.block.statements)
                    elif block_type == 'CatchClause':
                        block_line_count = len(containing_block.block.statements)
                    elif block_type == 'MethodDeclaration':
                        block_line_count = 1
                    else:
                        block_line_count = len(containing_block.statement.block.statements)
                    '''
    if containing_block is None:
        return None, None, None

    containing_block_lines = containing_block.position[1] - containing_block.position[0] + 1
    return containing_block_lines, block_type, exception_type

def find_block_info(source_code, text):
    tree = javalang.parse.parse(source_code)

    # Find the node containing the specified text
    for path, node in tree:
        if isinstance(node, javalang.tree.Node) and node.position:
            if text in nodeToString(node, source_code):
                start_line, end_line = node.position.line, node.position.end.line
                containing_block_type = get_containing_block_type(tree, path)
                num_lines_in_block = end_line - start_line + 1
                exception_type = get_containing_catch_block_exception_type(tree, path)
                return start_line, containing_block_type, num_lines_in_block, exception_type

    return None

def nodeToString(node, source_code):
    return str(source_code[node.position.start:node.position.end])

def get_containing_block_type(tree, path):
    for _, parent_node in reversed(path):
        if isinstance(parent_node, javalang.tree.BlockStatement):
            return type(parent_node)

    return None

def get_containing_catch_block_exception_type(tree, path):
    for _, parent_node in reversed(path):
        if isinstance(parent_node, javalang.tree.CatchClause):
            return str(parent_node.parameter.type)

    return None

def get_containing_block_info(source_code, target_line):
    # Parse the source code into a syntax tree
    try:
        tree = javalang.parse.parse(source_code)
    except javalang.parser.JavaSyntaxError:
        # handle the syntax error here
        return None, None, 'JavaSyntaxError'

    # Find the containing block of the target line
    containing_block = None
    for path, node in tree:
        if isinstance(node, javalang.ast.Node) and hasattr(node, 'line') and node.line <= target_line <= node.position[0]:
            containing_block = node
            break

    if containing_block is None:
        return None, None, None

    # Count the number of lines in the containing block
    containing_block_lines = containing_block.position[1] - containing_block.position[0] + 1

    # Determine the containing block type and the exception type of the containing catch block
    containing_block_type = type(containing_block).__name__
    exception_type = None
    if containing_block_type == 'CatchClause':
        exception_type = containing_block.parameter.type.name

    return containing_block_type, containing_block_lines, exception_type