# Health and Wellness Platform

## Fork Setup Instructions

### 1. Initial Setup
1. Create a new Repl
2. Import this repository
3. Enable "Always On" to ensure continuous operation

### 2. Database Setup
The application requires a PostgreSQL database. In your new Repl:
1. Go to "Tools" > "Secrets"
2. Add the following secrets:
   - DATABASE_URL (will be automatically created when you enable the database)
   - FLASK_SECRET_KEY (generate a random string)
   - GOOGLE_MAPS_API_KEY (required for location wellness features)

### 3. Google Maps API Setup
1. Visit the Google Cloud Console
2. Create a new project or select an existing one
3. Enable the following APIs:
   - Maps JavaScript API
   - Places API
   - Geocoding API
4. Create credentials (API key)
5. Add the API key to your Repl's secrets as GOOGLE_MAPS_API_KEY

### 4. Dependencies
All required packages are listed in `pyproject.toml`. They will be automatically installed when you run the application.

### 5. Environment Configuration
Required environment variables:
- DATABASE_URL (automatically set up)
- FLASK_SECRET_KEY (for session management)
- GOOGLE_MAPS_API_KEY (for location wellness features)

### 6. Starting the Application
1. The main application file is `main.py`
2. The Flask server will automatically start and run on port 5000

### 7. Database Initialization
The database tables will be automatically created when the application starts.

### 8. Features
- User authentication
- Food tracking
- Mood tracking
- Water intake monitoring
- Journal entries
- Chat history
- Weight logging
- Wellness quotes
- Location-based wellness tracking
- Meditation tracking
- Smart notifications

### 9. Backup System
The application includes an automated backup system that:
- Performs regular backups of the database
- Maintains backup history
- Ensures data integrity

### 10. Troubleshooting
If you encounter any issues:
1. Check the logs in the Shell tab
2. Verify all environment variables are set
3. Ensure the database is properly initialized
4. Check if the Flask server is running on port 5000

### 11. API Keys Required
1. Google Maps API key for location services
   - Required for location-based wellness tracking
   - Add to secrets as GOOGLE_MAPS_API_KEY
   - Enable required APIs in Google Cloud Console

### 12. Security Notes
- Never commit sensitive information or API keys
- Use environment variables for all sensitive data
- Keep your FLASK_SECRET_KEY private
- Regularly update dependencies for security patches

### 13. Development Guidelines
1. Use Flask's development server (debug mode enabled)
2. Follow the existing project structure
3. Use SQLAlchemy for database operations
4. Implement proper error handling
5. Add logging for debugging
6. Test thoroughly before deploying changes

For any additional questions or issues, please refer to the documentation or create an issue in the repository.