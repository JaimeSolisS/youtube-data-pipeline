# YouTube Data Pipeline

## Prerequisites

- `curl`
- `unzip`
- `make`

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/JaimeSolisS/youtube-data-pipeline.git
cd youtube-data-pipeline
```

### 2. Download the dataset

```bash
make download-kaggle
```

This will download and extract the dataset into a `data/` folder. The dataset includes trending video CSVs and category JSON files for 10 countries: CA, DE, FR, GB, IN, JP, KR, MX, RU, US.
