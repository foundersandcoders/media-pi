.PHONY: fmt-check lint-py lint-sh fmt-sh check db-init db-seed db-reset db-seed-constants

fp:
	pre-commit run black --all-files

lp:
	pre-commit run ruff --all-files

lsh:
	pre-commit run shellcheck --all-files

fsh:
	pre-commit run shfmt --all-files

check: fp lp lsh fsh

db-seed-constants:
	python3 scripts/seed_constants.py

db-init: db-seed-constants
	python3 scripts/init_db.py

db-seed:
	python3 scripts/seed.py

db-reset:
	rm -f data/media_pi_test.db && make db-init && make db-seed
