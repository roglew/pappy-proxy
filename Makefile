
docs:
	pandoc --from=markdown --to=rst --output=docs/source/overview.rst README.md
	cd docs; make html

.PHONY: docs
