## Description

Brief summary of the changes proposed in this Pull Request.

## Type of Change

- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds quantitative capability)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Documentation update

## Quantitative & Verification Checklist

- [ ] My code strictly adheres to zero look-ahead bias (backward-looking scaling only).
- [ ] I have verified that transaction costs (spread + slippage) are properly modeled.
- [ ] I have added unit tests in `tests/` covering my changes.
- [ ] All 45+ existing tests pass locally with `pytest tests/ -v`.
- [ ] Type annotations are complete and checked.
