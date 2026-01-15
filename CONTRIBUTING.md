# Contributing to AgentBlackBoxRecorder

First off, thank you for considering contributing to AgentBlackBoxRecorder! 

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [How to Contribute](#how-to-contribute)
- [Pull Request Process](#pull-request-process)
- [Style Guidelines](#style-guidelines)

## Code of Conduct

This project and everyone participating in it is governed by our Code of Conduct. By participating, you are expected to uphold this code.

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- Poetry (for Python package management)
- pnpm (recommended) or npm

### Development Setup

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/AgentBlackBoxRecorder.git
   cd AgentBlackBoxRecorder
   ```

2. **Set up the Python SDK**
   ```bash
   cd packages/python
   poetry install
   poetry shell
   ```

3. **Set up the Web UI**
   ```bash
   cd packages/web
   npm install
   ```

4. **Run tests**
   ```bash
   # Python tests
   cd packages/python
   pytest tests/ -v

   # Frontend tests
   cd packages/web
   npm test
   ```

## How to Contribute

### Reporting Bugs

- Use the GitHub issue tracker
- Check if the issue already exists
- Include steps to reproduce
- Include your environment details

### Suggesting Features

- Open a GitHub issue with the "feature request" label
- Describe the use case
- Explain why this feature would be useful

### Code Contributions

1. Create a new branch from `main`
2. Make your changes
3. Write/update tests
4. Update documentation if needed
5. Submit a pull request

## Pull Request Process

1. Update the README.md with details of changes if applicable
2. Update the documentation with any new features
3. Add tests for new functionality
4. Ensure all tests pass
5. Request review from maintainers

## Style Guidelines

### Python

- Follow PEP 8
- Use type hints
- Run `ruff check` and `ruff format` before committing
- Run `mypy` for type checking

### TypeScript/React

- Follow the existing code style
- Use functional components with hooks
- Run `npm run lint` before committing

### Commit Messages

- Use conventional commits format
- Example: `feat(sdk): add LangGraph adapter`
- Types: `feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`

## Questions?

Feel free to open an issue or reach out to the maintainers!

---

Thank you for contributing! 
