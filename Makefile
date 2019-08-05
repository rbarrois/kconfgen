PACKAGE=kconfgen
TESTS_DIR=tests
DOC_DIR=docs
SRC_DIR=src
SETUP_PY=setup.py

# Use current python binary instead of system default.
COVERAGE = python $(shell which coverage)
FLAKE8 = flake8
MYPY = mypy
MUTPY = mut.py

MUTPY_REPORTS = reports/mutpy/
COVERAGE_REPORTS = reports/coverage


all: default


default:


# Package management
# ==================


# DOC: Remove temporary or compiled files
clean:
	find . -type f -name '*.pyc' -delete
	find . -type f -path '*/__pycache__/*' -delete
	find . -type d -empty -delete
	@rm -rf tmp_test/


# DOC: Install and/or upgrade dependencies
update:
	pip install --upgrade pip setuptools
	pip install --upgrade -r requirements_dev.txt
	pip freeze


release:
	fullrelease


.PHONY: clean update release


# Tests and quality
# =================


# DOC: Run tests for all supported versions (creates a set of virtualenvs)
testall:
	tox

# DOC: Run tests for the currently installed version
test:
	python -Wdefault -m unittest discover

# DOC: Run mutation testing
mutation-test:
	$(MUTPY) --report-html $(MUTPY_REPORTS) --target $(PACKAGE) --unit-test $(TESTS_DIR)



# DOC: Perform code quality tasks
lint: flake8 check-manifest mypy

# DOC: Perform source code quality checks
flake8:
	$(FLAKE8) --config .flake8 $(SRC_DIR) $(SETUP_PY) $(TESTS_DIR)

# DOC: Validate type hints
mypy:
	$(MYPY) $(SRC_DIR) $(TESTS_DIR)

# DOC: Ensure MANIFEST.in / repository consistency
check-manifest:
	check-manifest

coverage:
	$(COVERAGE) erase
	$(COVERAGE) run "--include=$(SRC_DIR)/*.py,$(TESTS_DIR)/*.py" --branch $(SETUP_PY) test
	$(COVERAGE) report "--include=$(SRC_DIR)/*.py,$(TESTS_DIR)/*.py"
	$(COVERAGE) html --dir $(COVERAGE_REPORTS) "--include=$(SRC_DIR)/*.py,$(TESTS_DIR)/*.py"


.PHONY: test testall mutation-test lint flake8 check-manifest mypy coverage


# Documentation
# =============


# DOC: Compile the documentation
doc:
	$(MAKE) -C $(DOC_DIR) SPHINXOPTS=-W html

linkcheck:
	$(MAKE) -C $(DOC_DIR) linkcheck

# DOC: Show this help message
help:
	@grep -A1 '^# DOC:' Makefile \
	 | awk '    					\
	    BEGIN { FS="\n"; RS="--\n"; opt_len=0; }    \
	    {    					\
		doc=$$1; name=$$2;    			\
		sub("# DOC: ", "", doc);    		\
		sub(":", "", name);    			\
		if (length(name) > opt_len) {    	\
		    opt_len = length(name)    		\
		}    					\
		opts[NR] = name;    			\
		docs[name] = doc;    			\
	    }    					\
	    END {    					\
		pat="%-" (opt_len + 4) "s %s\n";    	\
		asort(opts);    			\
		for (i in opts) {    			\
		    opt=opts[i];    			\
		    printf pat, opt, docs[opt]    	\
		}    					\
	    }'


.PHONY: doc linkcheck help
