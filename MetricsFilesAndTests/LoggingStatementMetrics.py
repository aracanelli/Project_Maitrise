import re
from collections import Counter


def parse_logging_statement(statement):
    # Find the static text and variables in the logging statement
    pattern = r'(?<=[(,])\s*("[^"]*"|\'[^\']*\'|[^\s,)]+)\s*'
    content = re.findall(pattern, statement)[0]
    static_text = re.split(r'\{[^\{\}]*\}', content)
    variables = re.findall(r'\{[^\{\}]*\}', content)

    # Get the length of the static text and number of variables
    static_text_length = sum(len(s) for s in static_text)
    num_variables = len(variables)

    # Count the frequency of each token in the content
    content_tokens = [token for t in zip(static_text, variables) for token in t if token]
    token_frequencies = Counter(content_tokens)

    return static_text_length, num_variables, token_frequencies