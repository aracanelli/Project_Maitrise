import re
import javalang
import lizard
import pymetrics

import radon
from radon.complexity import cc_visit
from radon.raw import analyze
from codemaat import analyze
from radon.metrics import mi_visit

def get_logging_statement_metrics(statement):
    # extract content within brackets
    content = re.search(r'\((.*?)\)', statement)
    if content is None:
        return None, None, None

    content = content.group(1)

    static_text = ""
    freq_tokens = {}
    num_variables = 0

    # split content into tokens based on commas or plus signs, but only if they're outside of quotes
    parts = re.findall(r'[^\'"\s]*[\'"](?:\\.|[^\\\'"])*[\'"]|[^\s,]+', content)
    tokens = []
    for part in parts:
        if part[0] in ('"', "'"):
            tokens.append(part)
        else:
            sub_tokens = re.split(r'[+,]', part.strip())
            for sub_token in sub_tokens:
                if sub_token.strip():
                    tokens.append(sub_token.strip())

    for token in tokens:
        # remove whitespace
        token = token.strip()

        # ignore empty tokens
        if not token:
            continue

        # check if token is a variable (not enclosed in quotes)
        if '"' not in token and "'" not in token:
            num_variables += 1
            freq_tokens[token] = freq_tokens.get(token, 0) + 1
        else:
            # check if token is static text (within quotes)
            quote_match = re.search(r'(["\'])(.*?)\1', token)
            if quote_match is not None:
                static_text += quote_match.group(2) + " "
                freq_tokens[token] = freq_tokens.get(token, 0) + 1
            else:
                # add to frequency dictionary
                freq_tokens[token] = freq_tokens.get(token, 0) + 1

    # remove trailing whitespace from static text
    static_text = static_text.strip()

    return len(static_text), num_variables, freq_tokens

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
    # if containing_block is None:
        # return None, None, None

    # containing_block_lines = containing_block.position[1] - containing_block.position[0] + 1
    return block_type, exception_type

def search_code_for_text(text_to_search, java_source_code):

    # Parse Java source code into AST (Abstract Syntax Tree)
    ast = javalang.parse.parse(java_source_code)

    # Traverse AST and search for text
    for path, node in ast:
        if isinstance(node, javalang.tree.Statement) and not isinstance(node, javalang.tree.BlockStatement):
            # Traverse parent nodes until we find a BlockStatement
            try:
                parent = node.parent
                while not isinstance(parent, javalang.tree.BlockStatement):
                    parent = parent.parent
            except AttributeError:
                # Skip nodes that do not have a parent
                continue

            # If we found a BlockStatement and it contains the search text, return its information
            if isinstance(parent, javalang.tree.BlockStatement):
                block_lines = java_source_code[parent.position[0]:parent.position[1]].split('\n')
                if text_to_search in java_source_code[node.position[0]:node.position[1]]:
                    return parent, len(block_lines)

    # If text is not found, return None
    return None, None

def new_find_containing_block_and_type(source_code: str, text: str):
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
    block_depth = 0
    num_lines_in_block = 0

    if line_number is not None:
        # Parse the Java source code
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
                    if node_line >= line_number and block_depth <= path.count(javalang.tree.BlockStatement):
                        containing_block = node
                        block_type = block_compare
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

                        block_depth = path.count(javalang.tree.BlockStatement)
                        num_lines_in_block = calculate_lines(node)

    return block_type, exception_type, num_lines_in_block

def calculate_lines(node):
    if node is None or node.position is None:
        return 0
    start_line = node.position.line
    end_line = start_line
    for token in node.tokens:
        if token.position is not None:
            end_line = max(end_line, token.position.line)
    return end_line - start_line + 1
def get_containing_block(source_code, text):
    tree = javalang.parse.parse(source_code)
    for path, node in tree:
        if isinstance(node, javalang.tree.Node):
            try:
                if text in node.source:
                    for parent in reversed(list(tree.parents(node))):
                        if isinstance(parent, (javalang.tree.ClassDeclaration, javalang.tree.InterfaceDeclaration, javalang.tree.EnumDeclaration, javalang.tree.BlockStatement)):
                            return parent.name
                        elif isinstance(parent, javalang.tree.IfStatement):
                            return "if statement"
                        elif isinstance(parent, javalang.tree.WhileStatement):
                            return "while loop"
                        elif isinstance(parent, javalang.tree.ForStatement):
                            return "for loop"
                        elif isinstance(parent, javalang.tree.SwitchStatement):
                            return "switch case"
                        elif isinstance(parent, javalang.tree.TryStatement):
                            return "try block"
                        elif isinstance(parent, javalang.tree.CatchClause):
                            return "catch block"
                        elif isinstance(parent, javalang.tree.DoStatement):
                            return "do while loop"
            except AttributeError:
                pass
    return None



def get_file_metrics(source):
    # Define the file path to be analyzed
    file_path = '/path/to/file.java'

    # Define the metric functions to be used (e.g., SLOC, McCabe complexity, and fan-in)
    metric_fns = [analyze.sloc, analyze.mccabe_complexity, analyze.fan_in]

    # Use the analyzer to extract the metrics
    metrics = analyze.analyze_file(file_path, metric_fns)
    sloc =  metrics['sloc']
    mccabe_complexity = metrics['mccabe_complexity']
    fan_in = metrics['fan_in']

    return sloc, mccabe_complexity, fan_in