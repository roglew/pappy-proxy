
install-third-party:
	pip install -e ..

test:
	py.test -rw --twisted --cov-config .coveragerc --cov=. tests/

test-verbose:
	py.test -v -rw --twisted --cov-config .coveragerc --cov-report term-missing --cov=. tests/

test-macros:
	py.test -v -rw --twisted tests/test_macros.py

test-proxy:
	py.test -v -rw --twisted tests/test_proxy.py

test-comm:
	py.test -v -rw --twisted tests/test_comm.py

test-crypto:
	py.test -v -rw --twisted tests/test_crypto.py
      
