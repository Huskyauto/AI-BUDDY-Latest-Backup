/**
 * PWA Cache Buster
 * Version: 1.0.0
 * Created: May 6, 2025
 * 
 * This script forcibly updates the PWA cache by:
 * 1. Checking the server for updated version information
 * 2. Triggering cache invalidation based on version changes
 * 3. Forcing service worker updates
 */

(function() {
    // Current client-side build ID
    const CLIENT_BUILD_ID = '20250524115800';
    
    // Check for PWA updates
    async function checkForPWAUpdates() {
        try {
            console.log('Checking for PWA updates...');
            const response = await fetch('/pwa-version?v=' + Date.now());
            
            if (!response.ok) {
                throw new Error('Failed to check for updates');
            }
            
            const data = await response.json();
            console.log('Server version info:', data);
            
            // Compare build IDs to detect version mismatch
            if (data.build_id && data.build_id !== CLIENT_BUILD_ID) {
                console.log(`PWA update detected! Current: ${CLIENT_BUILD_ID}, Server: ${data.build_id}`);
                forceCacheUpdate();
            } else {
                console.log('PWA is up to date');
            }
        } catch (error) {
            console.error('Error checking for PWA updates:', error);
        }
    }
    
    // Force cache update by unregistering and reregistering the service worker
    async function forceCacheUpdate() {
        if ('serviceWorker' in navigator) {
            try {
                // Get all service worker registrations
                const registrations = await navigator.serviceWorker.getRegistrations();
                
                // Unregister each service worker
                for (const registration of registrations) {
                    await registration.unregister();
                    console.log('Service worker unregistered');
                }
                
                // Clear all caches
                const cacheKeys = await caches.keys();
                await Promise.all(
                    cacheKeys.map(key => {
                        console.log(`Clearing cache: ${key}`);
                        return caches.delete(key);
                    })
                );
                
                console.log('All caches cleared');
                
                // Reload the page to load fresh assets
                window.location.reload(true);
            } catch (error) {
                console.error('Failed to update cache:', error);
            }
        }
    }
    
    // Run on page load with a slight delay to prioritize page rendering
    setTimeout(checkForPWAUpdates, 2000);
    
    // Also check on visibility change (when user returns to the app)
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') {
            checkForPWAUpdates();
        }
    });
})();