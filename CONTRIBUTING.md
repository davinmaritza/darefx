# Contributing to DareFX

Thank you for your interest in contributing to DareFX. As an institutional quantitative trading codebase, we maintain high standards of statistical rigor, code quality, and testing invariants.

---

## 1. Development Principles

1. **Zero Data Leakage:** Any new indicator or feature must be strictly backward-looking. Never compute global statistics (e.g. whole-dataset min/max, future ATR, or centered rolling windows). All scaling must use rolling backward-looking Z-scores.
2. **Realistic Friction Modeling:** Any backtesting contribution must include spread, slippage, and broker commission models. We reject idealized zero-cost strategies.
3. **Evidence Before Assertions:** All bug fixes or new features must be accompanied by automated unit tests in `tests/`. Verify with `pytest tests/ -v` before opening a pull request.
4. **Code Style:** Type annotations are required on all public functions, classes, and methods.

---

## 2. Local Setup Workflow

```bash
# Fork & clone the repo
git clone https://github.com/davinmaritza/darefx.git
cd darefx

# Create Python 3.12 virtual environment
uv venv --python 3.12 .venv
source .venv/bin/activate

# Install editable package with dev dependencies
uv pip install -e ".[dev]"

# Run full test suite
pytest tests/ -v
```

---

## 3. Pull Request Process

1. Create a descriptive branch:
   - `feat/feature-name`
   - `fix/bug-description`
   - `refactor/subsystem-name`
2. Ensure all 45+ tests pass locally.
3. Submit a Pull Request targeting `main`. Include an explanation of the quantitative hypothesis, methodology, and empirical test results.
