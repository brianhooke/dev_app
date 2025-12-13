# Dev App

A Django-based construction project management application with Xero integration.

## Tech Stack

- **Backend:** Django 4.x, Python 3.11+
- **Database:** PostgreSQL (AWS RDS in production)
- **Frontend:** jQuery, Bootstrap 5
- **File Storage:** AWS S3
- **Hosting:** AWS Elastic Beanstalk
- **Integrations:** Xero API (invoicing, contacts)

## Quick Start

### Local Development

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Set environment variables
cp .env.example .env  # Edit with your values

# Run migrations
python manage.py migrate

# Start development server
python manage.py runserver
```

### Environment Variables

Required for production:
- `SECRET_KEY` - Django secret key
- `DATABASE_URL` - PostgreSQL connection string
- `AWS_ACCESS_KEY_ID` - S3 access
- `AWS_SECRET_ACCESS_KEY` - S3 secret
- `EMAIL_API_SECRET_KEY` - Email receiving API auth

## Project Structure

```
dev_app/
├── core/                    # Main application
│   ├── models.py           # Database models
│   ├── views/              # View modules (bills, quotes, pos, etc.)
│   ├── services/           # Business logic services
│   ├── templates/core/     # Core templates
│   └── static/core/js/     # JavaScript modules
├── dashboard/              # Dashboard app
│   ├── views/              # Dashboard views
│   └── templates/dashboard/
├── dev_app/settings/       # Environment-specific settings
│   ├── base.py            # Shared settings
│   ├── local.py           # Local development
│   └── production_aws.py  # AWS production
└── tests/                  # Test suite
```

## Documentation

- [Deployment Guide](DEPLOYMENT_GUIDE.md)
- [AWS Deployment](AWS_DEPLOYMENT_GUIDE.md)
- [Email Setup](EMAIL_RECEIVING_SETUP.md)
- [Model-Service Mapping](MODEL_SERVICE_MAPPING.md)

## Development

### Running Tests
```bash
python manage.py test
```

### Code Style
- Python: PEP 8
- JavaScript: ES6+
- Templates: Django template best practices

## License

Proprietary - All rights reserved
