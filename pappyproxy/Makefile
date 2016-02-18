
install-third-party:
	pip install -e ..

test:
	py.test -rw --twisted --cov-config .coveragerc --cov=. tests/

test-verbose:
	py.test -v -rw --twisted --cov-config .coveragerc --cov-report term-missing --cov=. tests/

test-macros:
	py.test -v -rw --twisted tests/test_macros.py
