
all: locale

check:
	black --line-length 120 --check apps/ muni_exam/ bin/
	isort --check-only --diff apps/ muni_exam/ bin/
	pylint -rn -sn --disable=import-error apps muni_exam
	pip-compile requirements.in -o requirements.txt

upgrade:
	pip-compile -U requirements.in -o requirements.txt

translate:
	python manage.py makemessages -a -i "venv/*"
	python manage.py compilemessages -i "venv/*"

deploy:
	ansible-playbook release.yaml -i config/hosts.ini

