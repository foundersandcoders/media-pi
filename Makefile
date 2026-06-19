.PHONY: fmt-check lint-py lint-sh fmt-sh check

fp:
	pre-commit run black --all-files

lp:
	pre-commit run ruff --all-files

lsh:
	pre-commit run shellcheck --all-files

fsh:
	pre-commit run shfmt --all-files

check: fp lp lsh fsh
