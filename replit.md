# Overview

AI-BUDDY is a comprehensive health and wellness platform built with Flask that combines personal wellness tracking with AI-powered support. The platform provides users with tools to monitor their physical and mental health through food tracking, mood monitoring, water intake logging, journaling, meditation programs, and an AI chat companion. The application features both individual wellness tracking and social features like challenges and forums, with a focus on creating a supportive wellness community.

# User Preferences

Preferred communication style: Simple, everyday language.

# System Architecture

## Frontend Architecture
- **Template Engine**: Jinja2 templates with custom filters for enhanced text formatting (nl2br filter for line breaks)
- **Static Assets**: Organized in `/static` folder with JavaScript, CSS, and image resources
- **Progressive Web App (PWA)**: Full PWA implementation with service worker, web manifest, and offline capabilities
- **Responsive Design**: Mobile-first approach with support for "Add to Home Screen" functionality
- **Interactive Components**: Real-time chat interface, mood tracking visualizations, and meditation timers

## Backend Architecture
- **Framework**: Flask with application factory pattern for modular design
- **Blueprint Structure**: Modular routing system with dedicated blueprints for:
  - Authentication (`auth.py`)
  - Dashboard and analytics (`dashboard.py`)
  - Chat and AI interactions (`chat.py`)
  - Food tracking (`food_tracker.py`)
  - Meditation and challenges (`challenge_routes.py`)
  - Fasting programs (`fasting.py`)
  - Admin functionality (`admin_dashboard.py`, `admin_reports.py`)
- **Database Layer**: SQLAlchemy ORM with optimized connection pooling and migration support
- **Session Management**: Flask-Login for user authentication with persistent sessions
- **Background Processing**: Asynchronous processing for wellness check-ins and AI response generation

## Data Storage Solutions
- **Primary Database**: PostgreSQL with Drizzle ORM support
- **Connection Pool**: Optimized SQLAlchemy engine with pre-ping, connection recycling, and pool size management
- **Migration System**: Flask-Migrate for database schema versioning
- **Data Models**: Comprehensive user data tracking including:
  - User profiles with wellness preferences
  - Mood and wellness check-ins with timezone handling
  - Food logs with nutritional data
  - Water intake and weight tracking
  - Meditation sessions and challenge participation
  - Journal entries and forum interactions
  - Chat history with AI conversations

## Authentication and Authorization
- **User Management**: Custom user model with email-based registration
- **Password Security**: Werkzeug password hashing with salt
- **Admin Access Control**: Role-based admin dashboard with specific user verification
- **Session Security**: Flask session management with configurable secret keys
- **Email Validation**: Built-in email format validation and duplicate prevention

## AI Integration Architecture
- **OpenAI Integration**: GPT-4o-mini model for conversational AI and wellness insights
- **API Management**: Centralized API client with usage logging and error handling
- **Response Processing**: Asynchronous AI response generation with visual feedback
- **Context Awareness**: Emotion-aware AI responses based on user mood selections
- **Usage Tracking**: Comprehensive API call logging for monitoring and analytics

## Wellness Features
- **Mood Tracking**: Multi-dimensional mood logging with energy and stress levels
- **CBT Integration**: Cognitive Behavioral Therapy principles in mood pattern analysis
- **Nutrition Tracking**: Edamam API integration for comprehensive food database
- **Meditation Programs**: Structured meditation challenges with progress tracking
- **Fasting Support**: Both intermittent and extended fasting program management
- **Location Wellness**: Google Maps API integration for location-based wellness features

# External Dependencies

## Third-Party APIs
- **OpenAI API**: GPT-4o-mini for AI chat functionality and wellness insights generation
- **Edamam Food Database API**: Nutritional data lookup and food logging capabilities
- **Google Maps API**: Location-based wellness features with Places and Geocoding services
- **Smart Ring Integrations**: Optional Oura and UltraHuman API support for biometric data

## Database Services
- **PostgreSQL**: Primary database with connection pooling and optimization
- **SQLAlchemy**: ORM with migration support through Flask-Migrate

## Email Services
- **Flask-Mail**: Email notification system for user communication and admin reports

## Development and Deployment
- **Flask Extensions**: Login management, database migrations, and mail services
- **PWA Technologies**: Service Worker API for offline functionality and push notifications
- **Report Generation**: ReportLab for PDF generation in admin dashboard
- **Environment Management**: Python-dotenv for configuration management

## Frontend Libraries
- **Chart Visualization**: JavaScript charting libraries for mood pattern analysis
- **Responsive Framework**: CSS framework for mobile-responsive design
- **PWA Manifest**: Web App Manifest for native app-like experience