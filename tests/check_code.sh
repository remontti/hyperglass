  #!/bin/sh

setup_git() {
  git config --global user.email "travis@travis-ci.org"
  git config --global user.name "Travis CI"
}

check_format() {
  black hyperglass
  git checkout origin/master
  git add hyperglass/ *.py
  git commit --message "Black Formatting - travis #$TRAVIS_BUILD_NUMBER"
  echo "Completed Black Formatting"
}

check_pylint() {
  PYLINT_SCORE=$(python3 manage.py pylint-badge --integer-only True)
  echo "Pylint score: $PYLINT_SCORE"
  git checkout origin/master
  git add pylint.svg
  git commit --message "Pylint Badge - travis #$TRAVIS_BUILD_NUMBER"
  echo "Completed Pylint Check & Badge Creation"
}

setup_git
check_format
check_pylint