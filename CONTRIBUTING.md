# Contributing to Python Tools Collection

Thank you for considering contributing to this project! We welcome contributions from everyone.

## How to Contribute

### Reporting Issues
- Use the [GitHub Issues](https://github.com/Ayush442842q/Python-tools/issues) page
- Check if the issue already exists before creating a new one
- Include as much detail as possible:
  - Steps to reproduce
  - Expected vs actual behavior
  - Python version and OS
  - Screenshots if applicable

### Suggesting Features
- Open an issue with the label "enhancement"
- Clearly describe the feature and its benefits
- Consider if it fits the scope of general-purpose Python utilities

### Submitting Pull Requests
1. Fork the repository
2. Create a new branch from `main`: `git checkout -b feature/your-feature-name`
3. Make your changes
4. Ensure your code follows the project's style guidelines
5. Add or update tests if applicable
6. Commit your changes: `git commit -m "Add: brief description of changes"`
7. Push to your fork: `git push origin feature/your-feature-name`
8. Open a Pull Request against the `main` branch

## Development Guidelines

### Code Style
- Follow [PEP 8](https://pep8.org/) for Python code
- Use descriptive variable and function names
- Add docstrings to all public functions and classes
- Keep functions focused and under 50 lines when possible
- Use type hints for function parameters and return values

### Tool Structure
Each tool should:
1. Be a standalone Python script in the `tools/` directory
2. Start with a proper shebang: `#!/usr/bin/env python3`
3. Include a comprehensive docstring at the top
4. Use `argparse` for command-line argument parsing
5. Include a `main()` function
6. Have the standard `if __name__ == "__main__":` guard
7. Be executable (`chmod +x filename.py`)
8. Handle errors gracefully with informative messages
9. Provide meaningful exit codes (0 for success, non-zero for errors)

### Documentation
- Update the README.md if adding/removing/changing tools
- Ensure each tool has clear usage instructions
- Include examples in the docstring when helpful
- List any external dependencies in the tool's docstring

### Testing
- Test your tool thoroughly before submitting
- Consider edge cases and error conditions
- If your tool modifies files, test with sample data first
- Provide usage examples in the documentation

## Code of Conduct
Please note that this project is released with a Contributor Code of Conduct. By participating in this project you agree to abide by its terms.

## Getting Help
If you need help with your contribution, feel free to ask in the issue thread or reach out to the maintainers.

Thank you for contributing to make this collection of Python tools better!