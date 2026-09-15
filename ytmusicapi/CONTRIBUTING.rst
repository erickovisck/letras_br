Contributing to ytmusicapi
##########################

Issues
-------
Please make sure to include sufficient details for reproducing your issue.
This includes the version of the library used as well as detailed instructions for reproduction.
If needed, please include the YouTube Music API response as well by debugging the API (responses
may differ based on the user account, so this helps with reproducing new issues).


Pull requests
--------------
Please open an issue before submitting, unless it's just a typo or some other small error.

Before making changes to the code, install the development requirements using

.. code-block::

    pip install pipx
    pipx install pdm pre-commit
    pdm install

Before committing, stage your files and run style and linter checks:

.. code-block::

    git add .
    pre-commit run

pre-commit will unstage any files that do not pass. Fix the issues until all checks pass and commit.

Code structure
---------------
The folder ``ytmusicapi`` contains the main library which is distributed to the users.
Each main library function in ``ytmusic.py`` is covered by a test in the ``tests`` folder.
If you want to contribute a new function, please create a corresponding unittest.

Youtube Music FE request body compression
-----------------------------------------
Youtube music FE has recently started to compress their POST request body with GZIP, which might make it harder for contributor to find out what needs to be passed into the request body.
In order to decrypt the request, the following will need to be done

1. Make the corresponding request in the youtube music FE.
2. Download the specific request into a HAR file using your browser.
3. Run the following python script with the name of the HAR file being the first command line argument and the name of output file being the second command line argument.

.. code-block::

    import gzip
    import json
    import sys

    fname = sys.argv[1]
    to_save = sys.argv[2]

    with open(fname, encoding='utf8') as f:
    request: dict = json.load(f)


    request_body = request["log"]["entries"][0]["request"]["postData"]["text"]


    raw = request_body.encode("latin1")


    decompressed = gzip.decompress(raw)
    with open(to_save, "w") as f:
    json.dump(json.loads(decompressed.decode("utf-8")), f, indent=2, ensure_ascii=False)
