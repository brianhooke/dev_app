import os
import re

# List of dependencies from your requirements.txt
dependencies = [
    "absl-py", "abstract-singleton", "aiofiles", "aiohttp", "aiosignal", "ajsonrpc", "annotated-types", "anyio",
    "appnope", "asgiref", "asttokens", "async-timeout", "attrs", "authlib", "auto-gpt-plugin-template", "awsebcli",
    "backcall", "beautifulsoup4", "bleach", "blessed", "boto3", "botocore", "bottle", "cachetools", "cement",
    "certifi", "cffi", "chardet", "charset-normalizer", "click", "colorama", "contourpy", "cryptography", "cycler",
    "decorator", "defusedxml", "distlib", "distro", "dj-database-url", "django", "django-environ", "django-storages",
    "docopt", "executing", "fastjsonschema", "filelock", "fonttools", "fpdf", "frozenlist", "google-api-core",
    "google-auth", "google-cloud-speech", "googleapis-common-protos", "grpcio", "grpcio-status", "gunicorn", "h11",
    "httpcore", "httpx", "idna", "ifaddr", "ifcopenshell", "immutabledict", "ipython", "isodate", "jedi", "jinja2",
    "jmespath", "jsonschema", "jsonschema-specifications", "jupyter-client", "jupyter-core", "jupyterlab-pygments",
    "kiwisolver", "lark", "markupsafe", "marshmallow", "mathutils", "matplotlib", "matplotlib-inline", "mistune",
    "multidict", "nbclient", "nbconvert", "nbformat", "numpy", "oauthlib", "openai", "opencv-python-headless",
    "ortools", "packaging", "pandas", "pandocfilters", "parso", "pathspec", "pdf2image", "pdfminer-six", "pdfplumber",
    "pdfrw", "pexpect", "pickleshare", "pillow", "pipdeptree", "pipenv", "pipreqs", "platformdirs", "platformio",
    "prompt-toolkit", "proto-plus", "protobuf", "psycopg2-binary", "ptyprocess", "pure-eval", "pyasn1",
    "pyasn1-modules", "pycparser", "pydantic", "pydantic-core", "pydub", "pyelftools", "pygments", "pyparsing",
    "pypdf2", "pypdfium2", "pyserial", "pytesseract", "python-dateutil", "python-dotenv", "pytz", "pyyaml", "pyzmq",
    "ratelimit", "referencing", "requests", "requests-oauthlib", "rpds-py", "rsa", "s3transfer", "scipy",
    "semantic-version", "shapely", "six", "sniffio", "soupsieve", "speechrecognition", "sqlparse", "stack-data",
    "starlette", "tabulate", "termcolor", "tesseract", "tinycss2", "tornado", "tqdm", "traitlets", "typing-extensions",
    "tzdata", "urllib3", "uvicorn", "virtualenv", "wand", "wcwidth", "webencodings", "wheel", "whitenoise",
    "wsproto", "xero-python", "yarg", "yarl", "zeroconf"
]

# Convert package names to importable module names (simplified)
def package_to_module(package_name):
    return package_name.replace("-", "_")

# Get a list of all Python files in the dev_app directory
def get_python_files(directory):
    python_files = []
    for dirpath, _, filenames in os.walk(directory):
        for filename in filenames:
            if filename.endswith(".py"):
                python_files.append(os.path.join(dirpath, filename))
    return python_files

# Search for import statements in Python files
def search_imports(files, modules):
    imported_modules = set()
    import_pattern = re.compile(r"^\s*(import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)")

    for file in files:
        with open(file, "r") as f:
            for line in f:
                match = import_pattern.match(line)
                if match:
                    module = match.group(2).split('.')[0]
                    if module in modules:
                        imported_modules.add(module)
    return imported_modules

# Main function
def main():
    directory = "dev_app"
    python_files = get_python_files(directory)
    modules = {package_to_module(dep) for dep in dependencies}
    imported_modules = search_imports(python_files, modules)
    
    # Print the list of imported modules that match the dependencies
    print("\nImported dependencies:")
    for module in sorted(imported_modules):
        print(module)

    # Prepare the list for requirements.txt format
    with open("requirements.txt", "r") as f:
        lines = f.readlines()
    
    print("\nUpdated requirements.txt content:")
    for line in lines:
        package = line.split("==")[0]
        module = package_to_module(package)
        if module in imported_modules:
            print(line.strip())

if __name__ == "__main__":
    main()
