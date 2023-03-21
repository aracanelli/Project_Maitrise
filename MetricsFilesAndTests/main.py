# This is a sample Python script.

# Press Shift+F10 to execute it or replace it with your code.
# Press Double Shift to search everywhere for classes, files, tool windows, actions, and settings.
import ContainingBlockMetrics
import tests
import tests2
import LoggingStatementMetrics
import HistoricalMetrics
import csv
import git

def save_results_to_csv(inputs, outputs, csv_file_path):
    # Open the CSV file and write the headers
    with open(csv_file_path, 'w', newline='') as csv_file:
        writer = csv.writer(csv_file)
        writer.writerow(['file_path', 'github_url', 'logging_statement', 'commit_id',
                         'length_of_static_text', 'num_variables', 'tokens',
                         # 'block_type', 'exception_type', 'block_lines',
                         'sloc', 'mccabe', 'fan_in'
                         ])

        # Iterate over the inputs and outputs and write them to the CSV file
        for i, o in zip(inputs, outputs):
            writer.writerow([i[0], i[1], i[2], i[3],
                             o['length_of_static_text'], o['num_variables'], o['tokens'],
                             # o['block_type'], o['exception_type'], o['block_lines'],
                             o['sloc'], o['mccabe'], o['fan_in']
                             ])


# Press the green button in the gutter to run the script.
if __name__ == '__main__':
    csv_file_path = './data.csv'
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
                commited_id = parent_id
            else:
                repo.git.checkout('--force', commit_id)
                commited_id = commit_id

            # Read the contents of the file
            try:
                with open(repo_path + str(i) + '/' + file_path, 'r', encoding='utf-8') as f:
                    file_contents = f.read()
            except UnicodeDecodeError:
                with open(repo_path + str(i) + '/' + file_path, 'r', encoding='iso-8859-1') as f:
                    file_contents = f.read()

                #
                    # print(file_path)

            static_text_length, num_variables, token_frequencies = tests.get_logging_statement_metrics(logging_statement)
            sloc, mccabe, fan_in = tests.get_file_metrics(file_contents)
            # block_type, exception_type = tests.find_containing_block_and_type(file_contents, logging_statement)
            # block_type,  block_lines = tests2.find_block(file_contents, logging_statement)
            # block_type = tests.get_containing_block(file_contents, logging_statement)
            # print(logging_statement + ": " + str(static_text_length) + ", " + str(num_variables))
            # containing_block_lines, containing_block_type, exception_type = ContainingBlockMetrics.find_containing_block_and_type(file_contents, logging_statement)
            # file_history = HistoricalMetrics.get_file_history(file_path, github_url, commit_id, parent_id)
            # num_revisions = HistoricalMetrics.count_revisions(file_history)
            # num_lines_of_code = HistoricalMetrics.count_lines_of_code(file_history)

            metrics.append({
                "length_of_static_text": static_text_length,
                "num_variables": num_variables,
                "tokens": token_frequencies,
                # "block_type": block_type,
                # "exception_type": exception_type,
                # "block_lines": block_lines,
                "sloc": sloc,
                "mccabe": mccabe,
                "fan_in": fan_in,
            })

            save_results_to_csv(inputs, metrics, csv_output_path)

# See PyCharm help at https://www.jetbrains.com/help/pycharm/
