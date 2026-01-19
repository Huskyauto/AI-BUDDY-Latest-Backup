/**
 * PWA Initialization Script for AI-BUDDY
 * Handles service worker registration, installation prompts, and PWA-specific behavior
 */

// Variables to store references
let deferredPrompt;
let installButton = document.getElementById('install-button');
let notificationButton = document.getElementById('notification-permission-button');

// Register service worker with forced update for PWA wellness check-in fix (May 6, 2025)
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    // First, unregister any existing service workers to ensure clean installation
    navigator.serviceWorker.getRegistrations().then(registrations => {
      const unregisterPromises = registrations.map(registration => {
        console.log('Unregistering old service worker:', registration.scope);
        return registration.unregister();
      });
      
      Promise.all(unregisterPromises).then(() => {
        console.log('All old service workers unregistered, registering new one...');
        
        // Now register the new service worker with cache-busting query parameter
        const cacheBuster = Date.now();
        navigator.serviceWorker.register(`/static/js/service-worker.js?v=${cacheBuster}`, {
          updateViaCache: 'none' // Prevent browser from using cached version
        })
        .then(registration => {
          console.log('AI-BUDDY Service Worker registered successfully:', registration.scope);
          
          // Force an immediate update check
          registration.update();
          
          // Check if service worker is controlling the page
          if (navigator.serviceWorker.controller) {
            console.log('AI-BUDDY is now available offline!');
          }
          
          // Setup message handler for service worker communication
          navigator.serviceWorker.addEventListener('message', event => {
            if (event.data && event.data.type === 'SYNC_WELLNESS_CHECKIN') {
              console.log('Received request to sync wellness checkin data');
              syncWellnessCheckinData();
            } else if (event.data && event.data.type === 'WELLNESS_CHECKIN_SSL_ERROR') {
              console.error('SSL error detected in wellness check-in:', event.data.error);
              // Potentially show a user-friendly message here
            }
          });
          
          // Periodically check for updates
          setInterval(() => {
            registration.update();
            console.log('Checking for service worker updates...');
          }, 60000); // Check every minute
        })
        .catch(error => {
          console.error('AI-BUDDY Service Worker registration failed:', error);
        });
      });
    });
  });
}

// Listen for beforeinstallprompt event to detect when the app can be installed
window.addEventListener('beforeinstallprompt', event => {
  // Prevent Chrome 76+ from showing the mini-infobar
  event.preventDefault();
  
  // Store the event for later use
  deferredPrompt = event;
  
  // Show the install button
  if (installButton) {
    installButton.classList.remove('d-none');
    installButton.addEventListener('click', installApp);
  }
});

// Handle app installation
function installApp() {
  if (!deferredPrompt) return;
  
  // Show the installation prompt
  deferredPrompt.prompt();
  
  // Wait for the user to respond to the prompt
  deferredPrompt.userChoice.then(choiceResult => {
    if (choiceResult.outcome === 'accepted') {
      console.log('User accepted the install prompt');
      // Hide the install button after installation
      if (installButton) {
        installButton.classList.add('d-none');
      }
    } else {
      console.log('User dismissed the install prompt');
    }
    
    // Clear the saved prompt
    deferredPrompt = null;
  });
}

// When the app is installed, hide the install button
window.addEventListener('appinstalled', event => {
  console.log('AI-BUDDY was installed');
  if (installButton) {
    installButton.classList.add('d-none');
  }
  
  // Show notification permission button after installation
  if (notificationButton) {
    notificationButton.classList.remove('d-none');
  }
});

// Handle notification permission requests
document.addEventListener('DOMContentLoaded', () => {
  // Re-acquire references since the page may have just loaded
  installButton = document.getElementById('install-button');
  notificationButton = document.getElementById('notification-permission-button');
  
  // Check if we can request notification permissions
  if ('Notification' in window) {
    if (Notification.permission === 'default') {
      // Show the notification permission button if not yet decided
      if (notificationButton) {
        notificationButton.classList.remove('d-none');
        notificationButton.addEventListener('click', requestNotificationPermission);
      }
    } else if (Notification.permission === 'granted') {
      // Already granted, no need to show the button
      if (notificationButton) {
        notificationButton.classList.add('d-none');
      }
    }
  }
  
  // Check for form submissions in PWA context
  setupFormHandlers();
});

// Request notification permission
function requestNotificationPermission() {
  Notification.requestPermission().then(permission => {
    if (permission === 'granted') {
      console.log('Notification permission granted');
      if (notificationButton) {
        notificationButton.classList.add('d-none');
      }
      
      // Send a test notification
      if ('serviceWorker' in navigator && navigator.serviceWorker.controller) {
        const title = 'AI-BUDDY Notifications Enabled';
        const options = {
          body: 'You will now receive reminders and wellness alerts',
          icon: '/static/icons/icon-192x192.png',
          badge: '/static/icons/icon-72x72.png'
        };
        
        // Use the Notification API directly for the first notification
        new Notification(title, options);
      }
    } else {
      console.log('Notification permission denied');
    }
  });
}

// Handle form submissions in PWA context
function setupFormHandlers() {
  // Find all forms on the page
  const forms = document.querySelectorAll('form');
  
  forms.forEach(form => {
    // Store the original form action
    const originalAction = form.getAttribute('action');
    
    // Add a special handler for wellness check-in form
    if (originalAction && originalAction.includes('wellness_check_in_submit')) {
      form.addEventListener('submit', function(event) {
        // Let the form submit normally, but add special handling for PWA context
        if (navigator.standalone || window.matchMedia('(display-mode: standalone)').matches) {
          console.log('Form submitted in PWA context:', originalAction);
          
          // You could add additional handling here if needed
          // But the default form submission should work fine
        }
      });
    }
  });
  
  // Special handling for the wellness check-in page
  if (window.location.pathname.includes('/self_care/wellness_check_in')) {
    // Add extra logging for debugging
    console.log('Wellness check-in page detected in PWA context');
    
    // Ensure forms on this page have proper CSRF protection
    ensureCSRFTokens();
  }
}

// Ensure CSRF tokens are present in a PWA context
function ensureCSRFTokens() {
  // Find all forms that might need CSRF tokens
  const forms = document.querySelectorAll('form');
  
  forms.forEach(form => {
    // Check if the form already has a CSRF token
    const hasCSRF = Array.from(form.elements).some(el => 
      el.name === 'csrf_token' || el.getAttribute('name') === 'csrf_token'
    );
    
    if (!hasCSRF) {
      console.warn('Form missing CSRF token in PWA context, this may cause submission issues');
      // Note: In a real implementation, you might want to fetch a valid CSRF token
      // or handle the submission in another way
    }
  });
}

// Function to sync wellness check-in data that might have been submitted offline
function syncWellnessCheckinData() {
  // In a real implementation, this would retrieve locally stored check-ins
  // and submit them to the server
  console.log('Synchronizing wellness check-in data with server...');
}