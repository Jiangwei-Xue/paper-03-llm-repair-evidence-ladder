.PHONY: replay analysis harness docker-metadata prompt-audits all-offline verify-archive

replay:
	python3 replay_all.py

analysis:
	python3 reproduce.py

harness:
	python3 experiment_code/verify_snapshot.py

docker-metadata:
	python3 docker/verify_metadata.py

prompt-audits:
	python3 prompt_audits/verify_reports.py

all-offline: replay analysis harness docker-metadata prompt-audits

verify-archive:
	@test -n "$(ARCHIVE)" || (echo "Set ARCHIVE=/path/to/release.tar.gz"; exit 2)
	python3 tools/VERIFY_ARCHIVE.py verify --archive "$(ARCHIVE)" --public
