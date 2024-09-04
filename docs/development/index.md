# Development


## Setting up the Environment

To set up the environment for development, install  and run the following command:


```bash
pdm install -G :all
```

This will install all the dependencies required for development.

## User Scripts

The following user scripts are available to make development easier:

    * pre-commit: Run pre-commit hooks on all files.
    * serve-document: Serve the documentation locally.
    * document: Build the documentation.
    * test: Run tests with coverage reporting.
    * format: Format code using ruff and isort.
    * release: Run pre-commit, tests, and build documentation (composite script).

These scripts can be run using the following command:

`pdm run <script_name>`

Replace `<script_name>` with the name of the script you want to run.

{{ git_page_authors }}