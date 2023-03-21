import csv
import ast
import git
import re
import javalang

from collections import Counter

def get_logging_metrics(csv_file_path):
    metrics = []
    inputs = []
    csv_output_path = './metrics.csv'
    i = 0
    repo_path = 'C:/Users/racan/Desktop/tmp/repo'
    prev_url = ''

    # Open the CSV file and read the rows
    with open(csv_file_path, 'r') as csv_file:
        reader = csv.reader(csv_file)

        # Iterate over each row in the CSV file
        for row in reader:
            file_path = row[0]
            github_url = row[1]
            logging_statement = row[2]
            commit_id = row[3]
            parent_id = row[4]
            change_type = row[5]

            # Save the inputs
            inputs.append((file_path, github_url, logging_statement, commit_id))

            # Clone the repository and checkout the specified commit
            if prev_url != github_url:
                i = i + 1
                repo = git.Repo.clone_from(github_url + '.git', repo_path + str(i))
                prev_url = github_url
            else:
                repo = git.Repo(repo_path + str(i))

            # Get the right commit
            change = change_type.split('_')
            if change[0] == 'DELETED':
                repo.git.checkout('--force', parent_id)
            else:
                repo.git.checkout('--force', commit_id)

            # Read the contents of the file
            with open(repo_path + str(i) + '/' + file_path, 'r') as f:
                try:
                    file_contents = f.read()
                except UnicodeDecodeError:
                    print(file_path)

            # Find the containing block for the logging statement
            containing_block, containing_block_type, exception_type = find_containing_block_and_type(file_contents, logging_statement)

            if containing_block is not None:
                # Find the number of source lines of code in the containing block
                # num_lines_of_code = len(containing_block.body)

                # Find the number of logging statements in the containing file
                num_logging_statements = file_contents.count(logging_statement)

                # Find the number of logging statements divided by the number of lines of code in the containing file
                # logging_statement_density = num_logging_statements / num_lines_of_code

                # Find the average level of other logging statements in the containing file
                '''
                logging_statements = re.findall(r"logging\((.*?)\)", file_contents)
                logging_levels = []
                for logging_stmt in logging_statements:
                    m = re.search(r"level=(\d+)", logging_stmt)
                    if m:
                        logging_levels.append(int(m.group(1)))
                avg_logging_level = sum(logging_levels) / len(logging_levels)
                '''

                # Find the average length of the static text of the logging statements in the containing file
                # logging_statement_lengths = [len(logging_stmt) for logging_stmt in logging_statements]
                # avg_logging_statement_length = sum(logging_statement_lengths) / len(logging_statement_lengths)

                # Find the number of source lines of code in the containing file
                num_lines_of_code_in_file = len(file_contents.split("\n"))

                # Use McCabe's cyclomatic complexity to measure the complexity of the containing file
                # mccabe_complexity = McCabeMetric().measure_file(repo_path + str(i) + '/' + file_path)

                # Find the number of classes that depend on the containing class
                # num_dependent_classes = get_dependent_classes(repo_path + str(i) + '/' + file_path)

                # Append the metrics for this logging statement to the list
                metrics.append({
                    "length_of_static_text": len(logging_statement),
                    "num_variables": logging_statement.count("{}"),
                    "tokens": len(re.split(r'[+,]', logging_statement)),
                    "containing_block_type": containing_block_type,
                    "exception_type": exception_type,
                    "num_logging_statements": num_logging_statements,
                    "num_lines_of_code_in_file": num_lines_of_code_in_file,
                })

        save_results_to_csv(inputs, metrics, csv_output_path)
        return metrics

def get_dependent_classes(file_path):
    # Read the contents of the file
    with open(file_path, 'r') as f:
        file_contents = f.read()

    # Parse the Java source code
    tree = javalang.parse.parse(file_contents)

    # Find all of the classes in the file
    classes = []
    for path, node in tree:
        if isinstance(node, javalang.parser.tree.ClassDeclaration):
            classes.append(node.name)

    # Find the number of classes that depend on the given class
    num_dependent_classes = 0
    for path, node in tree:
        if isinstance(node, javalang.parser.tree.FieldDeclaration):
            if node.type.name in classes:
                num_dependent_classes += 1

    return num_dependent_classes


class McCabeMetric:
    def measure_file(self, file_path):
        # Read the contents of the file
        with open(file_path, 'r') as f:
            file_contents = f.read()

        # Use the AST module to parse the file
        tree = ast.parse(file_contents)

        # Find the number of branches in the file
        num_branches = 0
        for node in ast.walk(tree):
            if isinstance(node, ast.If) or isinstance(node, ast.For) or isinstance(node, ast.While):
                num_branches += 1

        # Return the complexity, which is the number of branches plus 1
        return num_branches + 1

def save_results_to_csv(inputs, outputs, csv_file_path):
    # Open the CSV file and write the headers
    with open(csv_file_path, 'w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(['file_path', 'github_url', 'logging_statement', 'commit_id', 'length_of_static_text', 'num_variables', 'tokens', 'containing_block_type', 'exception_type', 'num_logging_statements', 'num_lines_of_code_in_file'])

        # Iterate over the inputs and outputs and write them to the CSV file
        for i, o in zip(inputs, outputs):
            writer.writerow([i[0], i[1], i[2], i[3],
                             o['length_of_static_text'],
                             o['num_variables'],
                             o['tokens'],
                             o['containing_block_type'],
                             o['exception_type'],
                             o['num_logging_statements'],
                             o['num_lines_of_code_in_file']])

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

    return containing_block, block_type, exception_type
