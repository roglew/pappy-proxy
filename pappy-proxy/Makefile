
install-third-party:
	pip install -r requirements.txt

test:
	py.test -rw --twisted --cov-config .coveragerc --cov=. tests/

test-verbose:
	py.test -v -rw --twisted --cov-config .coveragerc --cov-report term-missing --cov=. tests/
