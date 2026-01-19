# AI-BUDDY Changelog

## [1.0.5] - 2025-05-05
### Progressive Web App Implementation
- Added Progressive Web App (PWA) support for improved mobile and offline experience
  - Created Web App Manifest (`static/manifest.json`)
  - Implemented service worker for offline caching and background synchronization
  - Added PWA installation prompt and notification permission request
  - Created app icons in multiple sizes for various devices and platforms
  - Added meta tags for improved mobile experience
- Enhanced browser integration
  - Support for "Add to Home Screen" functionality on mobile devices
  - Offline access to critical app features
  - Push notification capability for wellness reminders
  - Background sync for data uploads during connectivity issues

## [1.0.4] - 2025-05-05
### Timestamp and UI Improvements
- Fixed timezone handling for all timestamps displayed in wellness check-in and journal entries
  - All timestamps now display in user's local timezone
  - Time format standardized to 12-hour AM/PM format across the application
  - Journal entries properly show time in user's local timezone
- Implemented asynchronous processing for wellness check-in submissions
  - Added visual feedback with a modal popup during processing
  - Background thread for recommendation generation to prevent UI delays
  - Improved error handling in background processing
- Added comprehensive documentation for timestamp handling and asynchronous processing
  - Created detailed implementation guide at `docs/wellness_checkin_timestamp_and_processing_improvements.md`
  - Added journal timestamp documentation at `docs/journal_timestamp_timezone_fix.md`

## [1.0.3] - 2025-01-09
### Chat History Optimization
- Limited chat history to 6 most recent conversations for improved performance
- Reorganized chat display to show newest messages at the bottom
- Implemented chronological ordering for better conversation flow
- Added automatic cleanup of older conversations

## [1.0.2] - 2025-01-07
### Documentation Improvements
- Added comprehensive fork setup guide (`docs/fork_setup_guide.md`)
  - Detailed instructions for initial repository setup
  - API key configuration steps for smart rings and Google services
  - Database setup and configuration guide
  - Authentication setup process
  - Troubleshooting guidelines
- Updated documentation structure for better maintainability
  - Standardized documentation templates
  - Added version-specific fix documentation

## [1.0.1] - 2025-01-07
### Enhanced Location Wellness Feature
#### Location Detection Improvements
- Added deceleration detection for better parking lot and drive-thru identification
  - New threshold: -5 km/h/s for detecting slowing down
  - Increased detection radius to 150 meters
  - Added speed buffer size to 5 measurements for more accurate detection
- Adjusted speed thresholds:
  - Parking lot: 10 km/h (increased from 8 km/h)
  - Drive-thru: 20 km/h (increased from 15 km/h)
- Improved GPS accuracy checks
  - Set minimum accuracy threshold to 30 meters
  - Added detailed logging for troubleshooting

#### Healthy Alternative Suggestions
- Enhanced nearby place detection:
  - Added 2km radius search for parks and outdoor activities
  - Added 1.5km radius search for walking trails and fitness areas
  - Implemented place type detection for contextual suggestions
- Improved suggestion system:
  - Added specific activity recommendations based on place type
  - Included walking trails and nature areas in suggestions
  - Enhanced voice alerts with natural pauses and better phrasing
  - Added fallback suggestions when no nearby places are found

#### Technical Details
- Location tracking intervals: 5 seconds
- Alert cooldown: 30 seconds
- Speed measurement buffer: 5 recent measurements
- GPS accuracy requirement: 30 meters or better
- Place search radius: 
  - Primary: 150m for food places
  - Secondary: 2km for parks/outdoor
  - Tertiary: 1.5km for walking trails

### Testing Notes
- Location detection can be verified by:
  1. Driving near fast food locations
  2. Testing different approach speeds
  3. Checking for suggestions when slowing down
- GPS accuracy affects detection quality
- Voice alerts should trigger when:
  1. Slowing down near food places
  2. Entering parking lots
  3. Approaching drive-thrus