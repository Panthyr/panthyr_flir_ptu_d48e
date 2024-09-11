.PHONY: install prep ui cleanup_git update_docs

install:
	python -m pip install --upgrade pip
	python -m pip install -e .

prep:
	pre-commit run --all-files

## Create list of local branches in a temporary file.
## Afterwards remove all branches from file.
cleanup_git:
	@echo "*****************************************************************************"
	@echo ">> Creating list of all merged branches without current, master or develop"
	@echo ">> Will fail if no branches are to be deleted"
	@echo "*****************************************************************************"

	@git branch --merged | grep -iv "master\|develop\|*" >/tmp/merged-branches
	@echo ">> Edit list so that it only contains branches to be deleted, then save."
	@echo ">> Hit <CTRL> + C to cancel."
	@vi /tmp/merged-branches && xargs git branch -d </tmp/merged-branches

update_docs:
	sphinx-apidoc.exe --force --output-dir ./docs/source ./panthyr_flir_ptu_d48e
	sphinx-build -b html docs/source/ docs/build/