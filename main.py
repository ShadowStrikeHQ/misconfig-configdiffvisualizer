import argparse
import difflib
import json
import logging
import os
import subprocess
import sys
import yaml
from diff_match_patch import diff_match_patch

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def setup_argparse():
    """
    Sets up the argument parser for the CLI.

    Returns:
        argparse.ArgumentParser: The argument parser object.
    """
    parser = argparse.ArgumentParser(description='Generates a human-readable diff between two configuration files.')
    parser.add_argument('file1', help='Path to the first configuration file.')
    parser.add_argument('file2', help='Path to the second configuration file.')
    parser.add_argument('-o', '--output', help='Path to the output file (HTML). If not specified, output to stdout.', default=None)
    parser.add_argument('-t', '--type', choices=['yaml', 'json', 'text'], help='Specify the file type (yaml, json, or text). If not specified, attempt to autodetect.', default=None)
    parser.add_argument('--ignore-whitespace', action='store_true', help='Ignore whitespace differences.')
    parser.add_argument('--no-validation', action='store_true', help='Skip validation of configuration files.') # Added no-validation option
    return parser


def validate_file(file_path, file_type):
    """
    Validates the configuration file using yamllint or jsonlint.

    Args:
        file_path (str): The path to the configuration file.
        file_type (str): The type of the configuration file (yaml or json).

    Returns:
        bool: True if the file is valid, False otherwise.
    """
    try:
        if file_type == 'yaml':
            try:
                subprocess.run(['yamllint', file_path], check=True, capture_output=True, text=True)
                return True
            except FileNotFoundError:
                logging.warning("yamllint not found. Skipping YAML validation. Please install yamllint to enable validation.")
                return True
            except subprocess.CalledProcessError as e:
                logging.error(f"YAML validation failed for {file_path}:\n{e.stderr}")
                return False
        elif file_type == 'json':
            try:
                subprocess.run(['jsonlint', file_path], check=True, capture_output=True, text=True)
                return True
            except FileNotFoundError:
                logging.warning("jsonlint not found. Skipping JSON validation. Please install jsonlint to enable validation.")
                return True
            except subprocess.CalledProcessError as e:
                logging.error(f"JSON validation failed for {file_path}:\n{e.stderr}")
                return False
        else:
            logging.warning(f"No validator available for file type: {file_type}. Skipping validation.")
            return True
    except Exception as e:
        logging.error(f"Error during validation for {file_path}: {e}")
        return False


def read_file(file_path, file_type):
    """
    Reads the configuration file and returns its content as a string.

    Args:
        file_path (str): The path to the configuration file.
        file_type (str): The type of the configuration file (yaml, json, or text).

    Returns:
        str: The content of the file as a string, or None if an error occurred.
    """
    try:
        with open(file_path, 'r') as f:
            if file_type == 'yaml':
                try:
                    data = yaml.safe_load(f)
                    return yaml.dump(data, indent=2)
                except yaml.YAMLError as e:
                    logging.error(f"Error parsing YAML file {file_path}: {e}")
                    return None
            elif file_type == 'json':
                try:
                    data = json.load(f)
                    return json.dumps(data, indent=2)
                except json.JSONDecodeError as e:
                    logging.error(f"Error parsing JSON file {file_path}: {e}")
                    return None
            else:  # Text file
                return f.read()
    except FileNotFoundError:
        logging.error(f"File not found: {file_path}")
        return None
    except Exception as e:
        logging.error(f"Error reading file {file_path}: {e}")
        return None


def detect_file_type(file_path):
    """
    Detects the file type based on the file extension.

    Args:
        file_path (str): The path to the file.

    Returns:
        str: The file type (yaml, json, or text), or None if the type cannot be detected.
    """
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    if ext in ['.yaml', '.yml']:
        return 'yaml'
    elif ext == '.json':
        return 'json'
    else:
        return 'text' # Default to text if extension is unknown

def generate_diff_html(text1, text2, ignore_whitespace=False):
    """
    Generates an HTML diff between two strings.

    Args:
        text1 (str): The first string.
        text2 (str): The second string.
        ignore_whitespace (bool): Whether to ignore whitespace differences.

    Returns:
        str: The HTML diff.
    """
    if ignore_whitespace:
        text1 = '\n'.join(line.strip() for line in text1.splitlines())
        text2 = '\n'.join(line.strip() for line in text2.splitlines())

    dmp = diff_match_patch()
    diff = dmp.diff_main(text1, text2)
    dmp.diff_cleanupSemantic(diff)
    return dmp.diff_prettyHtml(diff)

def main():
    """
    Main function to execute the configuration diff tool.
    """
    parser = setup_argparse()
    args = parser.parse_args()

    # Input validation - Ensure files exist
    if not os.path.exists(args.file1):
        logging.error(f"File not found: {args.file1}")
        sys.exit(1)
    if not os.path.exists(args.file2):
        logging.error(f"File not found: {args.file2}")
        sys.exit(1)


    # Determine file type
    file_type = args.type
    if not file_type:
        file_type = detect_file_type(args.file1)
        if file_type != detect_file_type(args.file2):
            logging.warning("File types of the two files appear to be different. Please specify the file type using the -t option for more accurate comparison.")

    # Validation step
    if not args.no_validation:
        if file_type in ('yaml', 'json'):
            if not validate_file(args.file1, file_type):
                sys.exit(1)
            if not validate_file(args.file2, file_type):
                sys.exit(1)

    # Read files
    config1 = read_file(args.file1, file_type)
    config2 = read_file(args.file2, file_type)

    if config1 is None or config2 is None:
        sys.exit(1)

    # Generate and output diff
    try:
        diff_html = generate_diff_html(config1, config2, args.ignore_whitespace)

        if args.output:
            try:
                with open(args.output, 'w') as f:
                    f.write(f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Configuration Diff</title>
<style>
del {{ background:#ffe6e6; }}
ins {{ background:#e6ffe6; }}
</style>
</head>
<body>
{diff_html}
</body>
</html>""")
                logging.info(f"Diff saved to {args.output}")
            except Exception as e:
                logging.error(f"Error writing to output file: {e}")
                sys.exit(1)
        else:
            print(f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>Configuration Diff</title>
<style>
del {{ background:#ffe6e6; }}
ins {{ background:#e6ffe6; }}
</style>
</head>
<body>
{diff_html}
</body>
</html>""")
    except Exception as e:
        logging.error(f"Error generating diff: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()