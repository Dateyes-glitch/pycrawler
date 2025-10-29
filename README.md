# SanctionsWatch 🔍

A comprehensive, modular framework for crawling sanctions data from international government sources. Built with Python, this project demonstrates professional web scraping, data processing, and ETL pipeline skills.

## 🎯 Purpose

This project showcases expertise in data engineering for compliance and sanctions monitoring. It's designed to collect, process, and analyze sanctions data from multiple international sources including:

- **EU Sanctions** (European Union)
- **OFAC** (US Treasury Department) 
- **UN Security Council** Sanctions
- **UK HM Treasury** Sanctions

## 🚀 Features

### Core Framework
- **Modular Architecture**: Easily extensible crawler framework
- **Robust Error Handling**: Retry logic, rate limiting, and graceful failures
- **Data Validation**: Pydantic models for data integrity
- **Async Support**: High-performance concurrent crawling
- **CLI Interface**: Easy-to-use command-line tools

### Data Processing
- **Entity Normalization**: Standardized entity formats across sources
- **Deduplication**: Smart matching to identify duplicate entries
- **Data Enrichment**: Enhanced entity information and relationships
- **Multiple Exports**: JSON, CSV, Excel, and database formats

### Monitoring & Observability
- **Structured Logging**: Comprehensive audit trails
- **Progress Tracking**: Real-time crawling progress
- **Data Quality Metrics**: Validation and completeness reporting
- **Configuration Management**: Environment-based settings

## 📦 Installation

### Prerequisites
- Python 3.8+
- Git

### Setup

```bash
# Clone the repository
git clone https://github.com/yourusername/sanctions-watch.git
cd sanctions-watch

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Install in development mode
pip install -e .
```

## 🔧 Usage

### Command Line Interface

```bash
# Crawl all sources
sanctions-watch crawl --all

# Crawl specific source
sanctions-watch crawl --source eu-sanctions

# Export data
sanctions-watch export --format json --output sanctions_data.json

# Check data quality
sanctions-watch validate --source all

# Get help
sanctions-watch --help
```


## 🧪 Testing

```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=sanctions_watch

# Run specific test file
pytest tests/test_crawlers.py
```

## 📈 Performance

- **Throughput**: ~1000 entities/minute (EU sanctions)
- **Memory Usage**: <200MB for typical datasets
- **Concurrent Sources**: Up to 4 simultaneous crawlers
- **Error Rate**: <0.1% with retry logic

## 🔒 Compliance & Ethics

- **Rate Limiting**: Respectful crawling practices
- **Legal Compliance**: Only public government data
- **Data Privacy**: No personal data storage beyond sanctions lists
- **Attribution**: Proper source attribution and licensing

## 🙏 Acknowledgments

- Built for compliance and transparency in financial services

*This project demonstrates practical skills in web scraping, data engineering, and compliance technology suitable for roles in fintech, regtech, and data engineering.*
