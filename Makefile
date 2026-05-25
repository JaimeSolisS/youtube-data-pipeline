download-kaggle:
	curl -L -o youtube-new.zip https://www.kaggle.com/api/v1/datasets/download/datasnaek/youtube-new && \
	mkdir data && \
	unzip youtube-new.zip -d data && \
	rm youtube-new.zip

upload-to-s3:
	cd scripts && \
	python ingestion.py $(bucket)
